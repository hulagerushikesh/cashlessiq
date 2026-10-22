FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY offline_supervisor.py supervisor_probe.py /probe/
WORKDIR /probe
USER 10001:10001
ENTRYPOINT ["python", "-I", "-c", "import sys,runpy; sys.path.insert(0,'/probe'); runpy.run_path('/probe/supervisor_probe.py',run_name='__main__')"]
