FROM python:3.11-slim-bookworm AS build
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy
WORKDIR /build/apps/membership
RUN pip install --no-cache-dir uv==0.11.25
COPY apps/membership/pyproject.toml apps/membership/uv.lock ./
COPY apps/membership/src ./src
COPY apps/worker/pyproject.toml /build/apps/worker/
COPY apps/worker/src /build/apps/worker/src
COPY packages/domain /build/packages/domain
COPY src/cashlessiq/decision_schema.py src/cashlessiq/source_decision.py src/cashlessiq/source_history.py src/cashlessiq/source_recommendation.py /build/src/cashlessiq/
COPY apps/api/src/ciq_api/__init__.py apps/api/src/ciq_api/contracts.py apps/api/src/ciq_api/source_contracts.py apps/api/src/ciq_api/source_identity.py apps/api/src/ciq_api/source_models.py apps/api/src/ciq_api/source_alpha.py apps/api/src/ciq_api/source_scopes.py apps/api/src/ciq_api/validation_worker.py apps/api/src/ciq_api/worker_authority.py apps/api/src/ciq_api/worker_delegation.py apps/api/src/ciq_api/worker_replay.py apps/api/src/ciq_api/worker_clock.py apps/api/src/ciq_api/worker_transport.py apps/api/src/ciq_api/worker_membership.py apps/api/src/ciq_api/worker_membership_store.py /build/apps/api/src/ciq_api/
COPY apps/api/src/ciq_api/worker_health.py apps/api/src/ciq_api/worker_guard_state.py apps/api/src/ciq_api/worker_guard_health.py apps/api/src/ciq_api/worker_guard_authority.py apps/api/src/ciq_api/worker_guard_transport.py /build/apps/api/src/ciq_api/
RUN uv sync --frozen --no-dev --no-editable --no-cache

FROM python:3.11-slim-bookworm AS runtime-base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:$PATH
COPY --from=build /opt/venv /opt/venv
USER 10001:10001
WORKDIR /tmp
CMD ["python", "-m", "ciq_membership_runtime"]

# Explicit disposable DB test target; absent from the default artifact.
FROM runtime-base AS db-test
COPY apps/membership/tests/db_probe.py /opt/venv/lib/python3.11/site-packages/ciq_membership_runtime/db_probe.py

# Explicit composition test only; worker images never receive the DB adapter.
FROM db-test AS mtls-test
COPY apps/worker/tests/mtls_probe.py /opt/venv/lib/python3.11/site-packages/ciq_worker_runtime/mtls_probe.py

# Separate synthetic six-worker membership composition; no fallback store.
FROM db-test AS composition-test
COPY apps/membership/tests/composition_service.py /opt/venv/lib/python3.11/site-packages/ciq_membership_runtime/composition_service.py
ENTRYPOINT ["python", "-m", "ciq_membership_runtime.composition_service"]

FROM runtime-base AS candidate
