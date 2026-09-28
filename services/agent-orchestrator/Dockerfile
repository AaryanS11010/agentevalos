FROM python:3.11-slim

WORKDIR /srv

# Build context is the repo root (see docker-compose.yml / .github/workflows/docker-build.yml)
# since this service depends on the local packages/agentevalos-sdk package, which Docker
# can't COPY from outside the build context.
COPY packages/agentevalos-sdk /packages/agentevalos-sdk
COPY services/agent-orchestrator /srv

RUN pip install --no-cache-dir -e /packages/agentevalos-sdk && \
    pip install --no-cache-dir -e .

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
