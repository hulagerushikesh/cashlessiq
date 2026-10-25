"""PostgreSQL leases, fenced completion, bounded retries and transactional projection."""

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pypdf
from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ciq_api.assessment import calculate, fingerprint, regression
from ciq_api.config import Settings
from ciq_api.database import make_engine
from ciq_api.models import Tenant
from ciq_api.mvp_models import AnalyticsEvent, DocumentUpload, PolicyVersion, SubmittedCase, WorkJob
from ciq_api.review_models import ReviewOutbox


def enqueue(db, who, kind, subject, payload):
    job = WorkJob(
        id=uuid4(),
        tenant_id=who.tenant.id,
        actor_id=who.user.id,
        kind=kind,
        subject_id=str(subject),
        payload=payload,
        state="queued",
        attempts=0,
    )
    db.add(job)
    return job


def claim(engine):
    now = datetime.now(UTC)
    with Session(engine) as db, db.begin():
        available = or_(
            and_(WorkJob.state == "queued", WorkJob.available_at <= now),
            and_(WorkJob.state == "running", WorkJob.lease_until < now),
        )
        db.execute(
            update(WorkJob)
            .where(available, WorkJob.attempts >= 3)
            .values(state="dead", error_code="attempt_limit", lease_id=None, lease_until=None)
        )
        job = db.scalar(
            select(WorkJob)
            .join(Tenant, Tenant.id == WorkJob.tenant_id)
            .where(available, WorkJob.attempts < 3, Tenant.active.is_(True))
            .order_by(WorkJob.created_at, WorkJob.id)
            .with_for_update(skip_locked=True, of=WorkJob)
            .limit(1)
        )
        if job is None:
            return None
        job.state, job.lease_id = "running", uuid4()
        job.lease_until, job.attempts = now + timedelta(seconds=60), job.attempts + 1
        return job.id, job.lease_id


def compute(engine, job_id, lease):
    with Session(engine) as db:
        job = db.get(WorkJob, job_id)
        if job is None or job.lease_id != lease or job.state != "running":
            raise ValueError("Lost job lease")
        if job.kind == "assessment":
            case = db.get(SubmittedCase, (job.tenant_id, job.subject_id))
            policy = db.get(PolicyVersion, case.policy_id)
            if policy.tenant_id != job.tenant_id:
                raise ValueError("Policy tenant mismatch")
            result = calculate(case.request_id, job.payload["inputs"], policy.proposal)
            result["policy_id"] = str(policy.id)
            return result
        if job.kind == "regression":
            policy = db.get(PolicyVersion, UUID(job.subject_id))
            if policy.tenant_id != job.tenant_id:
                raise ValueError("Policy tenant mismatch")
            return regression(policy.proposal)
        if job.kind == "extraction":
            document = db.get(DocumentUpload, UUID(job.subject_id))
            if document.tenant_id != job.tenant_id:
                raise ValueError("Document tenant mismatch")
            # No database/auth environment or document path crosses into parser.
            process = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    "import runpy,sys; sys.path.insert(0,sys.argv[1]); "
                    "runpy.run_path(sys.argv[2],run_name='__main__')",
                    str(Path(pypdf.__file__).resolve().parent.parent),
                    str(Path(__file__).with_name("pdf_extract.py")),
                ],
                input=document.content,
                capture_output=True,
                timeout=10,
                env={},
                check=True,
            )
            if len(process.stdout) > 700000:
                raise ValueError("Parser output limit")
            result = json.loads(process.stdout)
            if (
                set(result) != {"state", "text", "pages"}
                or result["state"] not in {"extracted", "needs_manual_extraction", "rejected"}
                or type(result["text"]) is not str
                or len(result["text"]) > 100000
            ):
                raise ValueError("Invalid extraction result")
            return result
        raise ValueError("Unsupported job kind")


def complete(engine, job_id, lease, result=None, *, failed=False):
    now = datetime.now(UTC)
    with Session(engine) as db, db.begin():
        job = db.scalar(select(WorkJob).where(WorkJob.id == job_id).with_for_update())
        if job is None or job.state != "running" or job.lease_id != lease or job.lease_until <= now:
            return False  # An expired worker cannot publish or overwrite its successor.
        if failed:
            job.state = "dead" if job.attempts >= 3 else "queued"
            job.error_code = "processing_failed"
            job.available_at = now + timedelta(seconds=2**job.attempts)
        else:
            job.state, job.result, job.error_code = "succeeded", result, None
            if job.kind == "assessment":
                case = db.scalar(
                    select(SubmittedCase)
                    .where(
                        SubmittedCase.tenant_id == job.tenant_id,
                        SubmittedCase.request_id == job.subject_id,
                    )
                    .with_for_update()
                )
                if fingerprint(case.inputs) == result["input_digest"]:
                    case.record = result
            elif job.kind == "extraction":
                document = db.get(DocumentUpload, UUID(job.subject_id))
                document.state, document.extracted_text = result["state"], result["text"]
        job.lease_id, job.lease_until = None, None
        return True


def mirror_outbox(engine):
    with Session(engine) as db, db.begin():
        events = db.scalars(
            select(ReviewOutbox)
            .where(ReviewOutbox.published_at.is_(None))
            .order_by(ReviewOutbox.event_id)
            .with_for_update(skip_locked=True)
            .limit(100)
        ).all()
        for event in events:
            existing = db.get(AnalyticsEvent, event.event_id)
            if existing and (
                existing.tenant_id != event.tenant_id or existing.event != event.event
            ):
                raise ValueError("Analytics event identity mismatch")
            db.execute(
                insert(AnalyticsEvent)
                .values(event_id=event.event_id, tenant_id=event.tenant_id, event=event.event)
                .on_conflict_do_nothing()
            )
            event.published_at = datetime.now(UTC)
        return len(events)


def run_once(engine):
    mirror_outbox(engine)
    claimed = claim(engine)
    if claimed is None:
        return False
    try:
        result = compute(engine, *claimed)
    except Exception:
        complete(engine, *claimed, failed=True)
    else:
        complete(engine, *claimed, result)
    return True


def main():
    parser = argparse.ArgumentParser(description="Synthetic MVP worker; no paid gateways")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--drain", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if not settings.synthetic_workflows:
        raise SystemExit("Synthetic workflows are disabled")
    engine = make_engine(settings)
    try:
        while True:
            did_work = run_once(engine)
            if args.once or (args.drain and not did_work):
                break
            if not did_work:
                time.sleep(2)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
