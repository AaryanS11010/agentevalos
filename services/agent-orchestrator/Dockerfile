FROM python:3.11-slim

WORKDIR /srv

# built from the repo root so we can copy the shared sdk package in too
COPY packages/agentevalos-sdk /packages/agentevalos-sdk
COPY services/agent-orchestrator /srv

RUN pip install --no-cache-dir -e /packages/agentevalos-sdk && \
    pip install --no-cache-dir -e .

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
