"""V2 adapter and real-membership HTTP tests with fake sources, never Snowflake."""

from copy import deepcopy
from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import ciq_api.seed as identity_seed
from ciq_api.auth import issue_local_token
from ciq_api.main import create_app
from ciq_api.models import Membership
from ciq_api.snowflake_reads import SourceCase, SourceReadUnavailable
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.source_cases import ALPHA_REFERENCES, SourceCaseRepository
from ciq_api.source_contracts import MissingSourceRecommendation, SavedSourceRecommendation

TPA1, TPA3 = SOURCE_TENANTS
SCOPES = {t.tenant_id: t.tpa_id for t in SOURCE_TENANTS}


@pytest.fixture
def sources():
    metadata, inspection = MagicMock(), MagicMock()
    records, details = {}, {}
    for tenant in SOURCE_TENANTS:
        records[tenant.tenant_id] = []
        ids = ("GOL001",) if tenant == TPA1 else ("GOL024", "GOL027")
        for request_id in ids:
            reference = ALPHA_REFERENCES[request_id]
            records[tenant.tenant_id].append(
                SourceCase(
                    request_id=request_id,
                    policy_id=reference.policy_id,
                    tpa_id=tenant.tpa_id,
                    product_id=reference.product_id,
                    product_name="Synthetic test product",
                    policy_version="TEST",
                    continuous_cover_since=date(2023, 1, 1),
                    admission_date=date(2026, 10, 2),
                    estimated_total_inr=100_000,
                )
            )
            context = {"request_id": request_id, "tpa_id": tenant.tpa_id}
            details[request_id] = {
                "member": [
                    {
                        **context,
                        "policy_id": reference.policy_id,
                        "member_id": reference.member_id,
                        "sum_insured_inr": 500_000,
                        "cumulative_bonus_inr": 0,
                        "status": "ACTIVE",
                        "claim_count": 0,
                        "total_paid_inr": 0,
                        "last_admission_date": None,
                    }
                ],
                "conditions": [
                    {
                        **context,
                        "icd10_code": "I10",
                        "condition_name": "Synthetic condition",
                        "first_diagnosed_on": date(2020, 1, 1),
                        "declared_at_proposal": True,
                    }
                ],
                "decision": [],
                "evidence": [
                    {
                        **context,
                        "product_id": reference.product_id,
                        "clause_id": "COPAY",
                        "heading": "Synthetic co-pay",
                        "page": 5,
                        "source_url": "https://example.com/policy.pdf",
                    }
                ],
            }
    decision = {
        "request_id": "GOL001",
        "outcome": "APPROVE_WITH_DEDUCTIONS",
        "total_claimed_inr": 100_000,
        "total_payable_inr": 95_000,
        "lines": [
            {
                "item": "Sensitive synthetic item",
                "claimed_inr": 100_000,
                "payable_inr": 95_000,
                "deduction_inr": 5_000,
                "reason": "Sensitive synthetic prose",
                "calc": "Saved trace",
                "citations": [{"type": "clause", "id": "COPAY"}],
            }
        ],
        "queries": [],
        "refer_reasons": [],
        "summary": "Restricted synthetic narrative",
        "sla": {"elapsed_min": 0, "state": "GREEN"},
    }
    details["GOL001"]["decision"] = [
        {
            "request_id": "GOL001",
            "tpa_id": "TPA001",
            "outcome": decision["outcome"],
            "payable_inr": 95_000,
            "decision_json": decision,
        }
    ]
    metadata.read_cases.side_effect = lambda tenant: deepcopy(records[tenant])
    inspection.inspect.side_effect = lambda tenant, request: deepcopy(details[request])
    repository = SourceCaseRepository(metadata, inspection, SCOPES)
    return repository, metadata, inspection, records, details


def test_queue_is_metadata_only_bounded_and_sorted(sources):
    repository, _, inspection, _, _ = sources
    result = repository.list_cases(TPA3.tenant_id, "gol", 2, 1)
    assert result.schema_version == 2
    assert result.total == 2 and result.items[0].request_id == "GOL027"
    assert result.recommendations_loaded is False
    assert "outcome" not in result.items[0].model_dump()
    assert repository.list_cases(TPA3.tenant_id, "absent", 1, 20).total == 0
    inspection.inspect.assert_not_called()


@pytest.mark.parametrize("tenant", [identity_seed.TENANT_ID, uuid4()])
def test_unknown_or_demo_tenant_never_reads_source(sources, tenant):
    repository, metadata, inspection, _, _ = sources
    assert repository.list_cases(tenant, "", 1, 20).total == 0
    assert repository.get_case(tenant, "GOL001") is None
    metadata.read_cases.assert_not_called()
    inspection.inspect.assert_not_called()


@pytest.mark.parametrize("request_id", ["GOL024", "GOL027", "UNKNOWN", "' OR 1=1 --"])
def test_unowned_request_never_reads_source(sources, request_id):
    repository, metadata, inspection, _, _ = sources
    assert repository.get_case(TPA1.tenant_id, request_id) is None
    metadata.read_cases.assert_not_called()
    inspection.inspect.assert_not_called()


def test_saved_decision_validates_and_returns_no_raw_clinical_prose(sources):
    repository, _, _, _, _ = sources
    result = repository.get_case(TPA1.tenant_id, "GOL001")
    assert isinstance(result.recommendation, SavedSourceRecommendation)
    assert result.recommendation.payable_inr == 95_000
    assert result.member_history.conditions is None
    payload = result.model_dump_json()
    assert "Sensitive" not in payload and "Restricted synthetic" not in payload
    assert "decision_json" not in payload and "schema_valid" not in payload


@pytest.mark.parametrize("request_id", ["GOL024", "GOL027"])
def test_missing_recommendation_never_copies_demo_outcomes(sources, request_id):
    repository, _, _, _, _ = sources
    result = repository.get_case(TPA3.tenant_id, request_id)
    assert isinstance(result.recommendation, MissingSourceRecommendation)
    assert result.recommendation.model_dump() == {"state": "MISSING"}
    assert result.case.estimated_total_inr == 100_000
    assert result.evidence_kind == "product_clause_register"
    assert result.member_history.conditions_visible is False


def test_condition_disclosure_is_per_read_not_mutating_source(sources):
    repository, _, _, _, _ = sources
    visible = repository.get_case(TPA3.tenant_id, "GOL024", include_conditions=True)
    assert visible.member_history.conditions[0].icd10_code == "I10"
    hidden = repository.get_case(TPA3.tenant_id, "GOL024")
    assert hidden.member_history.conditions is None


@pytest.mark.parametrize(
    "fault",
    [
        "owner",
        "policy",
        "product",
        "duplicate",
        "foreign_request",
        "member",
        "conditions",
        "empty_evidence",
        "foreign_evidence",
        "duplicate_evidence",
        "bad_page",
        "unsafe_url",
        "bad_total",
        "foreign_citation",
        "record_citation",
        "malformed_decision",
        "two_decisions",
    ],
)
def test_bad_source_data_fails_closed_never_missing_or_snapshot(sources, fault):
    repository, _, _, records, details = sources
    record = records[TPA1.tenant_id][0]
    rows = details["GOL001"]
    if fault in {"owner", "policy", "product", "foreign_request"}:
        key, value = {
            "owner": ("tpa_id", "TPA003"),
            "policy": ("policy_id", "POL0024"),
            "product": ("product_id", "FOREIGN"),
            "foreign_request": ("request_id", "GOL024"),
        }[fault]
        records[TPA1.tenant_id] = [record.model_copy(update={key: value})]
    elif fault == "duplicate":
        records[TPA1.tenant_id].append(record)
    elif fault == "member":
        rows["member"][0]["member_id"] = "MEM0024"
    elif fault == "conditions":
        rows["conditions"][0]["tpa_id"] = "TPA003"
    elif fault == "empty_evidence":
        rows["evidence"] = []
    elif fault == "foreign_evidence":
        rows["evidence"][0]["product_id"] = "FOREIGN"
    elif fault == "duplicate_evidence":
        rows["evidence"].append(deepcopy(rows["evidence"][0]))
    elif fault == "bad_page":
        rows["evidence"][0]["page"] = 5.1
    elif fault == "unsafe_url":
        rows["evidence"][0]["source_url"] = "javascript:alert(1)"
    elif fault == "bad_total":
        rows["decision"][0]["decision_json"]["total_payable_inr"] = 94_999
    elif fault in {"foreign_citation", "record_citation"}:
        citation = rows["decision"][0]["decision_json"]["lines"][0]["citations"][0]
        citation.update(type="record" if fault == "record_citation" else "clause", id="FOREIGN")
    elif fault == "malformed_decision":
        rows["decision"] = [{}]
    elif fault == "two_decisions":
        rows["decision"].append(deepcopy(rows["decision"][0]))
    with pytest.raises(SourceReadUnavailable):
        repository.get_case(TPA1.tenant_id, "GOL001")


def test_source_failure_and_absent_request_are_distinct(sources):
    repository, metadata, inspection, records, _ = sources
    inspection.inspect.side_effect = RuntimeError("secret diagnosis and token")
    with pytest.raises(SourceReadUnavailable, match=r"^Source case unavailable$"):
        repository.get_case(TPA1.tenant_id, "GOL001")
    records[TPA1.tenant_id] = []
    assert repository.get_case(TPA1.tenant_id, "GOL001") is None
    metadata.read_cases.side_effect = RuntimeError("secret diagnosis and token")
    with pytest.raises(SourceReadUnavailable, match=r"^Source cases unavailable$"):
        repository.list_cases(TPA1.tenant_id, "", 1, 20)


@pytest.fixture
def source_http(settings, engine, monkeypatch, sources):
    monkeypatch.setattr(identity_seed, "make_engine", lambda _: engine)
    identity_seed.seed(settings, include_source_tenants=True)
    with TestClient(create_app(settings, engine, source_repository=sources[0])) as http:
        yield http


def source_bearer(settings, tenant=TPA3, role="processor"):
    profile = next(p for p in tenant.profiles if p.role == role)
    return {
        "Authorization": "Bearer " + issue_local_token(settings, profile.subject, tenant.tenant_id)
    }


@pytest.mark.parametrize("path", ["/v2/cases", "/v2/cases/GOL024"])
def test_v2_auth_and_disabled_default(client, settings, path):
    assert client.get(path).status_code == 401
    headers = {
        "Authorization": "Bearer "
        + issue_local_token(settings, "processor", identity_seed.TENANT_ID)
    }
    response = client.get(path, headers=headers)
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert "not enabled" in response.json()["detail"]


@pytest.mark.parametrize("role", ["processor", "medical_officer", "auditor"])
def test_http_source_missing_and_role_disclosure(source_http, settings, role):
    headers = source_bearer(settings, role=role)
    result = source_http.get("/v2/cases/GOL024", headers=headers)
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    data = result.json()
    assert data["schema_version"] == 2 and data["data_mode"] == "synthetic_source"
    assert data["recommendation"] == {"state": "MISSING"}
    assert data["member_history"]["conditions_visible"] == (role == "medical_officer")
    assert (data["member_history"]["conditions"] is None) == (role != "medical_officer")


def test_http_tenant_scope_pagination_failure_and_no_writes(source_http, settings, sources):
    headers = source_bearer(settings) | {"X-Tenant-ID": str(TPA1.tenant_id), "X-TPA-ID": "TPA001"}
    queue = source_http.get("/v2/cases?page_size=1&page=2", headers=headers).json()
    assert queue["total"] == 2 and queue["items"][0]["request_id"] == "GOL027"
    assert queue["recommendations_loaded"] is False
    assert source_http.get("/v2/cases/GOL001", headers=headers).status_code == 404
    assert source_http.get("/v2/cases/UNKNOWN", headers=headers).status_code == 404
    sources[2].inspect.side_effect = RuntimeError("secret clinical connector diagnostic")
    error = source_http.get("/v2/cases/GOL024", headers=headers)
    assert error.status_code == 503 and "secret" not in error.text
    assert error.headers["cache-control"] == "no-store"
    for method in ("post", "put", "patch", "delete"):
        assert getattr(source_http, method)("/v2/cases/GOL024", headers=headers).status_code == 405


def test_http_revoked_membership_prevents_source_reads(source_http, settings, sources, engine):
    headers = source_bearer(settings)
    user = next(p for p in TPA3.profiles if p.role == "processor")
    with Session(engine) as session, session.begin():
        session.get(Membership, (TPA3.tenant_id, user.user_id)).active = False
    sources[1].reset_mock()
    assert source_http.get("/v2/cases", headers=headers).status_code == 403
    assert source_http.get("/v2/cases/GOL024", headers=headers).status_code == 403
    sources[1].read_cases.assert_not_called()


@pytest.mark.parametrize("outcome", ["QUERY", "REFER"])
def test_saved_uncomputed_decisions_are_not_missing(sources, outcome):
    repository, _, _, _, details = sources
    decision = deepcopy(details["GOL001"]["decision"][0])
    decision.update(outcome=outcome, payable_inr=0, request_id="GOL024", tpa_id="TPA003")
    decision["decision_json"].update(
        request_id="GOL024",
        outcome=outcome,
        total_claimed_inr=0,
        total_payable_inr=0,
        lines=[],
        queries=["Synthetic query"] if outcome == "QUERY" else [],
        refer_reasons=["Synthetic referral"] if outcome == "REFER" else [],
    )
    details["GOL024"]["decision"] = [decision]
    result = repository.get_case(TPA3.tenant_id, "GOL024")
    assert result.recommendation.state == "SAVED"
    assert result.recommendation.outcome == outcome
    assert result.recommendation.payable_inr is None
    assert result.recommendation.claimed_inr == 100_000


def test_v2_recommendation_contract_rejects_fabricated_missing_and_deny():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MissingSourceRecommendation(outcome="REFER", payable_inr=0)
    with pytest.raises(ValidationError):
        SavedSourceRecommendation(
            outcome="DENY",
            claimed_inr=100,
            payable_inr=0,
            amount_basis="saved_calculation",
        )
    with pytest.raises(ValidationError):
        SavedSourceRecommendation(
            outcome="REFER",
            claimed_inr=100,
            payable_inr=0,
            amount_basis="supplied_estimate",
        )


@pytest.mark.parametrize("query", ["page=0", "page_size=51", "search=" + "a" * 81])
def test_v2_invalid_filters(source_http, settings, query):
    assert source_http.get(f"/v2/cases?{query}", headers=source_bearer(settings)).status_code == 422


def test_v2_staging_injection_rejected(settings, engine, sources):
    with pytest.raises(ValueError, match="local/test only"):
        create_app(settings.model_copy(update={"environment": "staging"}), engine, sources[0])


def test_v2_capability_required_and_demo_not_bound(source_http, settings, sources):
    demo = {
        "Authorization": "Bearer "
        + issue_local_token(settings, "processor", identity_seed.TENANT_ID)
    }
    sources[1].reset_mock()
    assert source_http.get("/v2/cases", headers=demo).json()["items"] == []
    assert source_http.get("/v2/cases/GOL001", headers=demo).status_code == 404
    sources[1].read_cases.assert_not_called()
    # Simulate a resolved identity without the read capability, not a browser role hint.
    dependency = (
        next(route for route in source_http.app.routes if getattr(route, "path", "") == "/v1/me")
        .dependant.dependencies[0]
        .call
    )
    from ciq_api.contracts import MeResponse, TenantView, UserView

    source_http.app.dependency_overrides[dependency] = lambda: MeResponse(
        user=UserView(id=uuid4(), display_name="Synthetic test"),
        tenant=TenantView(id=TPA3.tenant_id, name="Synthetic test"),
        role="auditor",
        capabilities=[],
        identity_mode="local",
    )
    assert source_http.get("/v2/cases").status_code == 403
    assert source_http.get("/v2/cases/GOL024").status_code == 403
