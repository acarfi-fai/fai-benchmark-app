FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir \
    "inspect-ai==0.3.224" \
    "adlfs==2026.5.0" \
    "azure-monitor-opentelemetry" \
    "opentelemetry-instrumentation-fastapi"

WORKDIR /app
COPY custom_results_viewer.py /app/custom_results_viewer.py

EXPOSE 8000

CMD ["python", "/app/custom_results_viewer.py"]
