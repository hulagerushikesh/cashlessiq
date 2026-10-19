FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /app/apps/api
RUN pip install --no-cache-dir uv==0.11.25
COPY apps/api/pyproject.toml apps/api/uv.lock ./
COPY apps/api/src ./src
COPY packages/domain /app/packages/domain
COPY src/cashlessiq/decision_schema.py src/cashlessiq/source_decision.py src/cashlessiq/source_history.py src/cashlessiq/source_recommendation.py /app/src/cashlessiq/
RUN uv sync --frozen --no-dev
COPY apps/api/alembic.ini ./
COPY apps/api/migrations ./migrations
RUN useradd --create-home ciq
USER ciq
EXPOSE 8000
CMD [".venv/bin/uvicorn", "ciq_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
