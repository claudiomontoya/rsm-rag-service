.DEFAULT_GOAL := help

.PHONY: help up down restart build rebuild test ps logs logs-qdrant shell shell-qdrant clean prune

help:
	@echo "Targets disponibles:"
	@echo "  up            — Construir y levantar en segundo plano (detached)"
	@echo "  down          — Detener y quitar contenedores"
	@echo "  restart       — Reiniciar stack (down + up)"
	@echo "  build         — Construir imagen del API (Dockerfile local)"
	@echo "  rebuild       — Rebuild compose (sin cache) y levantar"
	@echo "  test          — Ejecutar tests (pytest)"
	@echo "  ps            — Ver estado de servicios"
	@echo "  logs          — Ver logs del API"
	@echo "  logs-qdrant   — Ver logs de Qdrant"
	@echo "  shell         — Shell dentro del contenedor API"
	@echo "  shell-qdrant  — Shell dentro del contenedor Qdrant"
	@echo "  clean         — Down con volúmenes"
	@echo "  prune         — Limpiar recursos dangling"

up:
	docker compose up --build -d

down:
	docker compose down

restart: down up

build:
	docker build -t rag-api:v0.1 -f api/Dockerfile api

rebuild:
	docker compose build --no-cache
	docker compose up -d

test:
	cd api && python -m pytest -v

ps:
	docker compose ps

logs:
	docker compose logs -f api

logs-qdrant:
	docker compose logs -f qdrant

shell:
	docker compose exec api bash

shell-qdrant:
	docker compose exec qdrant bash

clean:
	docker compose down -v

prune:
	docker system prune -f
