FROM python:3.11-slim-bookworm AS build
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy
WORKDIR /build/apps/worker
RUN pip install --no-cache-dir uv==0.11.25
COPY apps/worker/pyproject.toml apps/worker/uv.lock ./
COPY apps/worker/src ./src
COPY packages/domain /build/packages/domain
COPY src/cashlessiq/decision_schema.py src/cashlessiq/source_decision.py src/cashlessiq/source_history.py src/cashlessiq/source_recommendation.py /build/src/cashlessiq/
COPY apps/api/src/ciq_api/__init__.py apps/api/src/ciq_api/contracts.py apps/api/src/ciq_api/source_contracts.py apps/api/src/ciq_api/source_identity.py apps/api/src/ciq_api/source_models.py apps/api/src/ciq_api/source_alpha.py apps/api/src/ciq_api/source_scopes.py apps/api/src/ciq_api/validation_worker.py apps/api/src/ciq_api/worker_authority.py apps/api/src/ciq_api/worker_delegation.py apps/api/src/ciq_api/worker_replay.py apps/api/src/ciq_api/worker_clock.py apps/api/src/ciq_api/worker_transport.py apps/api/src/ciq_api/worker_membership.py /build/apps/api/src/ciq_api/
COPY apps/api/src/ciq_api/worker_health.py apps/api/src/ciq_api/worker_guard_state.py apps/api/src/ciq_api/worker_guard_health.py apps/api/src/ciq_api/worker_guard_authority.py apps/api/src/ciq_api/worker_guard_transport.py /build/apps/api/src/ciq_api/
RUN uv sync --frozen --no-dev --no-editable --no-cache

FROM python:3.11-slim-bookworm AS runtime-base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:$PATH
COPY --from=build /opt/venv /opt/venv
USER 10001:10001
WORKDIR /tmp
CMD ["python", "-m", "ciq_worker_runtime"]

# Explicit test target only: TCP reachability probes, not worker endpoints.
FROM runtime-base AS isolation-test
COPY apps/worker/tests/isolation_probe.py /opt/venv/lib/python3.11/site-packages/ciq_worker_runtime/isolation_probe.py
ENTRYPOINT ["python", "-m", "ciq_worker_runtime.isolation_probe"]

# Disposable PKI + synthetic application handlers; never the default artifact.
FROM runtime-base AS mtls-test
COPY apps/worker/tests/mtls_probe.py /opt/venv/lib/python3.11/site-packages/ciq_worker_runtime/mtls_probe.py
COPY apps/worker/tests/guard_mtls_fixture.py /opt/venv/lib/python3.11/site-packages/ciq_worker_runtime/guard_mtls_fixture.py
ENTRYPOINT ["python", "-m", "ciq_worker_runtime.mtls_probe"]

# Six independently runnable handlers, explicit synthetic integration target only.
FROM mtls-test AS composition-test
COPY apps/worker/tests/composition_service.py /opt/venv/lib/python3.11/site-packages/ciq_worker_runtime/composition_service.py
ENTRYPOINT ["python", "-m", "ciq_worker_runtime.composition_service"]
CMD []

# Network-free clock-domain probe; fabricated health is test-only.
FROM runtime-base AS clock-test
COPY apps/worker/tests/clock_probe.py /opt/venv/lib/python3.11/site-packages/ciq_worker_runtime/clock_probe.py

# Default target contains no test listener or automatic service startup.
FROM runtime-base AS guard-test
COPY apps/worker/tests/guard_probe.py /opt/venv/lib/python3.11/site-packages/ciq_worker_runtime/guard_probe.py

FROM runtime-base AS candidate
