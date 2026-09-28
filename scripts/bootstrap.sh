#!/usr/bin/env bash
# Sets up local dev environment: per-service venvs + the shared SDK installed
# editable into each, plus console node_modules. Idempotent — safe to re-run.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

setup_python_service() {
  local dir="$1"
  echo "==> Bootstrapping $dir"
  cd "$ROOT_DIR/$dir"
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  if [ "$dir" != "packages/agentevalos-sdk" ]; then
    pip install -e "$ROOT_DIR/packages/agentevalos-sdk"
  fi
  pip install -e ".[dev]" 2>/dev/null || pip install -e .
  deactivate
}

setup_python_service "packages/agentevalos-sdk"
setup_python_service "services/agent-orchestrator"
setup_python_service "services/eval-engine"

if [ ! -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "==> Created .env from .env.example — fill in Snowflake/LLM credentials before running services"
fi

echo "==> Installing console dependencies"
cd "$ROOT_DIR/console"
npm install

echo "==> Done. Next steps:"
echo "    docker compose up -d postgres otel-collector phoenix"
echo "    (in a new shell) cd services/agent-orchestrator && source .venv/bin/activate && uvicorn app.main:app --reload --port 8001"
echo "    (in a new shell) cd services/eval-engine && source .venv/bin/activate && uvicorn app.main:app --reload --port 8002"
echo "    (in a new shell) cd console && npm run dev"
