FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /app
RUN pip install --no-cache-dir uv==0.11.25
COPY apps/api/pyproject.toml apps/api/uv.lock ./
COPY apps/api/src ./src
RUN uv sync --frozen --no-dev
COPY apps/api/alembic.ini ./
COPY apps/api/migrations ./migrations
RUN useradd --create-home ciq
USER ciq
EXPOSE 8000
CMD [".venv/bin/uvicorn", "ciq_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
