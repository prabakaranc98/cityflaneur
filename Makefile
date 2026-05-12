.PHONY: api-dev api-test docker-up docker-down seed-snapshot simulation web-dev web-build

api-dev:
	cd apps/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

api-test:
	cd apps/api && pytest

seed-snapshot:
	cd apps/api && python scripts/seed_catalog.py

simulation:
	cd apps/api && python scripts/run_simulation.py

web-dev:
	cd apps/web && npm run dev

web-build:
	cd apps/web && npm run build

docker-up:
	docker compose up --build

docker-down:
	docker compose down

