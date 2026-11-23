# Disposable CI only; no host mounts, real credentials or product service wiring.
FROM postgres:17-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /opt/ciq
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv gnupg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11.25 /uv /usr/local/bin/uv
COPY apps/api/pyproject.toml apps/api/uv.lock ./apps/api/
COPY apps/api/src ./apps/api/src
COPY packages/domain ./packages/domain
COPY src/cashlessiq/decision_schema.py src/cashlessiq/source_decision.py src/cashlessiq/source_history.py src/cashlessiq/source_recommendation.py ./src/cashlessiq/
COPY src/cashlessiq/rules ./src/cashlessiq/rules
RUN uv sync --project apps/api --frozen
COPY apps/api/alembic.ini ./apps/api/alembic.ini
COPY apps/api/migrations ./apps/api/migrations
COPY deploy/agent-controller/*.sql ./deploy/agent-controller/
COPY apps/agent-transport/fake_transport.py ./apps/agent-transport/
COPY apps/agent-transport/tests/exchange_fixture.py ./apps/agent-transport/tests/
COPY apps/api/tests/conftest.py apps/api/tests/test_agent_contracts.py apps/api/tests/test_agent_ledger.py apps/api/tests/test_agent_controller_capture.py apps/api/tests/test_agent_controller_reservation.py apps/api/tests/test_agent_receipt_verifier.py apps/api/tests/test_agent_custody_submission.py apps/api/tests/test_agent_custody_dispatch.py apps/api/tests/test_agent_custody_publication.py apps/api/tests/test_agent_custody_recovery.py apps/api/tests/test_agent_receipt_verifier_offline.py apps/api/tests/test_agent_receipt_peer_linux.py apps/api/tests/receipt_peer_child.py apps/api/tests/peer_database_child.py apps/api/tests/test_agent_peer_database.py ./apps/api/tests/
COPY apps/api/tests/test_agent_ledger_recovery.py apps/api/tests/test_agent_custody_restore.py apps/api/tests/test_agent_peer_restore.py ./apps/api/tests/
COPY scripts/check_mvp_recovery.py scripts/mvp_recovery_probe.py scripts/mvp_backup_transfer.py scripts/verify_mvp_backup.py ./scripts/
ENTRYPOINT []
CMD ["apps/api/.venv/bin/python", "-m", "pytest", "-x", "--tb=short", "-p", "no:cacheprovider", "apps/api/tests/test_agent_peer_database.py", "apps/api/tests/test_agent_peer_restore.py"]
