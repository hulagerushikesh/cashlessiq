# Explicit fake-only engineering artifact, never included in product Compose.
FROM python:3.11-slim-bookworm AS candidate
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY apps/agent-transport/fake_transport.py /opt/ciq/fake_transport.py
USER 11002:11002
WORKDIR /tmp
ENTRYPOINT ["python", "-I", "/opt/ciq/fake_transport.py"]
