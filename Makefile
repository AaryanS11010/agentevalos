.PHONY: bootstrap up down test lint fmt seed-snowflake

bootstrap:
	./scripts/bootstrap.sh

up:
	docker compose up -d

down:
	docker compose down

test:
	cd packages/agentevalos-sdk && python -m pytest || true
	cd services/agent-orchestrator && python -m pytest
	cd services/eval-engine && python -m pytest

lint:
	ruff check packages services
	cd console && npm run lint

fmt:
	ruff format packages services
	cd console && npm run format || true

seed-snowflake:
	python scripts/seed_snowflake.py
