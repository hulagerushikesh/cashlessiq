# Disposable CI supervisor only. Never used in product Compose or cloud bundles.
FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /opt/ciq
RUN pip install --no-cache-dir uv==0.11.25
COPY apps/api/pyproject.toml apps/api/uv.lock ./apps/api/
COPY apps/api/src ./apps/api/src
COPY packages/domain ./packages/domain
COPY src/cashlessiq/decision_schema.py src/cashlessiq/source_decision.py src/cashlessiq/source_history.py src/cashlessiq/source_recommendation.py ./src/cashlessiq/
COPY src/cashlessiq/rules ./src/cashlessiq/rules
RUN uv sync --project apps/api --frozen
COPY apps/api/tests/receipt_peer_child.py apps/api/tests/test_agent_receipt_peer_linux.py apps/api/tests/test_agent_receipt_verifier_offline.py apps/api/tests/test_agent_custody_submission_offline.py ./apps/api/tests/
CMD ["apps/api/.venv/bin/python", "-m", "pytest", "-p", "no:cacheprovider", "apps/api/tests/test_agent_receipt_peer_linux.py"]
