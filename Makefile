# ================================================
# RAG Microservice v1.0 - Enhanced Makefile
# ================================================

.DEFAULT_GOAL := help

# ================================================
# CONFIGURACIÓN
# ================================================

# Variables configurables
COMPOSE_FILE ?= docker-compose.yml
API_SERVICE ?= api
REDIS_SERVICE ?= redis
QDRANT_SERVICE ?= qdrant
JAEGER_SERVICE ?= jaeger

# Colores para output
RESET = \033[0m
BOLD = \033[1m
RED = \033[31m
GREEN = \033[32m
YELLOW = \033[33m
BLUE = \033[34m
CYAN = \033[36m

# ================================================
# AYUDA Y DOCUMENTACIÓN
# ================================================

.PHONY: help
help: ## 📋 Mostrar todos los comandos disponibles
	@echo ""
	@echo "$(BOLD)$(BLUE)🚀 RAG Microservice v1.0 - Comandos Disponibles$(RESET)"
	@echo ""
	@echo "$(BOLD)$(CYAN)🐳 Docker & Compose:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep "🐳\|📦\|🔄" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)$(CYAN)🧪 Testing & Quality:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep "🧪\|✅\|🔍\|📊" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)$(CYAN)📊 Observability & Monitoring:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep "📈\|🎯\|👁️\|📋" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)$(CYAN)🚀 Development & Utils:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep "🛠️\|🔧\|🧹\|💾\|🔑" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)$(YELLOW)Ejemplos de uso:$(RESET)"
	@echo "  make up          # Levantar todo el stack"
	@echo "  make test-all    # Ejecutar todos los tests"
	@echo "  make monitor     # Abrir interfaces de monitoreo"
	@echo "  make dev         # Modo desarrollo con hot-reload"
	@echo ""

# ================================================
# 🐳 DOCKER & COMPOSE
# ================================================

.PHONY: up down restart ps status
up: ## 🐳 Construir y levantar stack completo
	@echo "$(BOLD)$(GREEN)🚀 Levantando RAG Microservice stack...$(RESET)"
	docker compose up --build -d
	@echo "$(GREEN)✅ Stack levantado. Servicios disponibles en:$(RESET)"
	@echo "  🌐 API: http://localhost:8000"
	@echo "  📊 Jaeger: http://localhost:16686"
	@echo "  📋 API Docs: http://localhost:8000/docs"

down: ## 🐳 Detener y quitar contenedores
	@echo "$(YELLOW)⏹️  Deteniendo stack...$(RESET)"
	docker compose down

restart: down up ## 🔄 Reiniciar stack completo (down + up)

ps: ## 📦 Ver estado de todos los servicios
	@echo "$(BOLD)$(BLUE)📦 Estado de servicios:$(RESET)"
	docker compose ps

status: ps ## 📦 Alias para ps

# ================================================
# 🛠️ BUILD & DEVELOPMENT
# ================================================

.PHONY: build rebuild dev dev-logs
build: ## 🔨 Construir solo imagen del API
	@echo "$(BOLD)$(BLUE)🔨 Construyendo imagen API...$(RESET)"
	docker build -t rag-api:latest -f api/Dockerfile api

rebuild: ## 🔄 Rebuild completo sin cache
	@echo "$(BOLD)$(YELLOW)🔄 Rebuild sin cache...$(RESET)"
	docker compose build --no-cache
	docker compose up -d

dev: ## 🛠️ Modo desarrollo con hot-reload
	@echo "$(BOLD)$(GREEN)🛠️  Iniciando modo desarrollo...$(RESET)"
	docker compose -f docker-compose.dev.yml up --build

dev-logs: ## 📝 Logs en modo desarrollo
	docker compose -f docker-compose.dev.yml logs -f

# ================================================
# 🧪 TESTING & QUALITY
# ================================================

.PHONY: test test-unit test-integration test-performance test-sse test-coverage lint format security
test: ## 🧪 Ejecutar tests básicos
	@echo "$(BOLD)$(BLUE)🧪 Ejecutando tests...$(RESET)"
	cd api && python -m pytest tests/test_basic.py -v

test-unit: ## ✅ Tests unitarios
	@echo "$(BOLD)$(BLUE)✅ Tests unitarios...$(RESET)"
	cd api && python -m pytest tests/ -v -m "not integration and not performance and not slow"

test-integration: ## 🔗 Tests de integración
	@echo "$(BOLD)$(BLUE)🔗 Tests de integración...$(RESET)"
	cd api && python -m pytest tests/ -v -m integration

test-performance: ## 📊 Tests de performance
	@echo "$(BOLD)$(BLUE)📊 Tests de performance...$(RESET)"
	cd api && python -m pytest tests/ -v -m performance

test-sse: ## 📡 Tests de Server-Sent Events
	@echo "$(BOLD)$(BLUE)📡 Tests SSE...$(RESET)"
	cd api && python -m pytest tests/test_sse_reconnection.py -v

test-all: ## 🎯 Ejecutar TODOS los tests
	@echo "$(BOLD)$(GREEN)🎯 Ejecutando suite completa de tests...$(RESET)"
	cd api && python -m pytest tests/ -v --tb=short

test-coverage: ## 📈 Tests con coverage report
	@echo "$(BOLD)$(BLUE)📈 Tests con coverage...$(RESET)"
	cd api && python -m pytest tests/ --cov=app --cov-report=html --cov-report=term

lint: ## 🔍 Lint y type checking
	@echo "$(BOLD)$(BLUE)🔍 Linting código...$(RESET)"
	cd api && python -m flake8 app/
	cd api && python -m mypy app/

format: ## ✨ Formatear código
	@echo "$(BOLD)$(BLUE)✨ Formateando código...$(RESET)"
	cd api && python -m black app/ tests/
	cd api && python -m isort app/ tests/

security: ## 🔒 Security scan
	@echo "$(BOLD)$(BLUE)🔒 Security scan...$(RESET)"
	cd api && python -m bandit -r app/

quality: lint format security ## 🏆 Ejecutar todas las verificaciones de calidad

# ================================================
# 📊 OBSERVABILITY & MONITORING
# ================================================

.PHONY: monitor metrics health logs-all trace-ui open-jaeger open-docs
monitor: ## 📈 Abrir todas las interfaces de monitoreo
	@echo "$(BOLD)$(GREEN)📈 Abriendo interfaces de monitoreo...$(RESET)"
	@echo "🌐 API: http://localhost:8000"
	@echo "📊 Jaeger: http://localhost:16686"
	@echo "📋 Docs: http://localhost:8000/docs"
	@echo "📈 Metrics: http://localhost:8000/metrics"
	@if command -v open >/dev/null 2>&1; then \
		open http://localhost:8000 & \
		open http://localhost:16686 & \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://localhost:8000 & \
		xdg-open http://localhost:16686 & \
	fi

metrics: ## 📊 Ver métricas de la aplicación
	@echo "$(BOLD)$(BLUE)📊 Métricas de aplicación:$(RESET)"
	@curl -s http://localhost:8000/metrics | jq . 2>/dev/null || curl -s http://localhost:8000/metrics

health: ## 👁️ Health check completo
	@echo "$(BOLD)$(BLUE)👁️ Health check:$(RESET)"
	@echo "$(CYAN)API Health:$(RESET)"
	@curl -s http://localhost:8000/health | jq . 2>/dev/null || echo "❌ API no disponible"
	@echo "$(CYAN)Readiness:$(RESET)"
	@curl -s http://localhost:8000/ready | jq . 2>/dev/null || echo "❌ API no ready"
	@echo "$(CYAN)Liveness:$(RESET)"
	@curl -s http://localhost:8000/live | jq . 2>/dev/null || echo "❌ API no alive"

logs-all: ## 📋 Ver logs de todos los servicios
	docker compose logs -f

trace-ui: open-jaeger ## 🎯 Abrir Jaeger UI

open-jaeger: ## 🔍 Abrir Jaeger UI
	@if command -v open >/dev/null 2>&1; then \
		open http://localhost:16686; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://localhost:16686; \
	else \
		echo "Jaeger UI: http://localhost:16686"; \
	fi

open-docs: ## 📖 Abrir documentación API
	@if command -v open >/dev/null 2>&1; then \
		open http://localhost:8000/docs; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://localhost:8000/docs; \
	else \
		echo "API Docs: http://localhost:8000/docs"; \
	fi

# ================================================
# 🔧 DEBUGGING & TROUBLESHOOTING
# ================================================

.PHONY: logs logs-api logs-redis logs-qdrant logs-jaeger shell shell-api shell-redis debug-redis debug-qdrant
logs: logs-api ## 📝 Ver logs del API (alias)

logs-api: ## 📝 Ver logs del API
	docker compose logs -f $(API_SERVICE)

logs-redis: ## 📝 Ver logs de Redis
	docker compose logs -f $(REDIS_SERVICE)

logs-qdrant: ## 📝 Ver logs de Qdrant
	docker compose logs -f $(QDRANT_SERVICE)

logs-jaeger: ## 📝 Ver logs de Jaeger
	docker compose logs -f $(JAEGER_SERVICE)

shell: shell-api ## 🐚 Shell en contenedor API (alias)

shell-api: ## 🐚 Shell dentro del contenedor API
	docker compose exec $(API_SERVICE) bash

shell-redis: ## 🐚 Shell dentro del contenedor Redis
	docker compose exec $(REDIS_SERVICE) sh

shell-qdrant: ## 🐚 Shell dentro del contenedor Qdrant
	docker compose exec $(QDRANT_SERVICE) bash

debug-redis: ## 🔧 Debug Redis - ver conexiones y datos
	@echo "$(BOLD)$(BLUE)🔧 Redis Debug Info:$(RESET)"
	docker compose exec $(REDIS_SERVICE) redis-cli info
	@echo "\n$(CYAN)Active Jobs:$(RESET)"
	docker compose exec $(REDIS_SERVICE) redis-cli smembers jobs:active

debug-qdrant: ## 🔧 Debug Qdrant - ver colecciones
	@echo "$(BOLD)$(BLUE)🔧 Qdrant Debug Info:$(RESET)"
	@curl -s http://localhost:6333/collections | jq . 2>/dev/null || curl -s http://localhost:6333/collections

# ================================================
# 🧹 CLEANUP & MAINTENANCE
# ================================================

.PHONY: clean clean-all prune reset backup restore
clean: ## 🧹 Parar y limpiar contenedores (conservar volúmenes)
	@echo "$(BOLD)$(YELLOW)🧹 Limpiando contenedores...$(RESET)"
	docker compose down

clean-all: ## 🗑️ Limpieza completa (incluye volúmenes)
	@echo "$(BOLD)$(RED)🗑️ Limpieza completa (CUIDADO: se pierden datos)...$(RESET)"
	@read -p "¿Estás seguro? Esto eliminará todos los datos (y/N): " confirm && [ "$$confirm" = "y" ]
	docker compose down -v
	docker compose rm -f

prune: ## 🧽 Limpiar recursos Docker no utilizados
	@echo "$(BOLD)$(BLUE)🧽 Limpiando recursos Docker...$(RESET)"
	docker system prune -f
	docker volume prune -f

reset: clean-all up ## 🔄 Reset completo (clean-all + up)

backup: ## 💾 Backup de volúmenes (Redis + Qdrant)
	@echo "$(BOLD)$(BLUE)💾 Creando backup...$(RESET)"
	@mkdir -p ./backups
	docker run --rm -v rsm-rag-service_redis_data:/data -v $(PWD)/backups:/backup alpine tar czf /backup/redis-$(shell date +%Y%m%d-%H%M%S).tar.gz -C /data .
	docker run --rm -v rsm-rag-service_qdrant_data:/data -v $(PWD)/backups:/backup alpine tar czf /backup/qdrant-$(shell date +%Y%m%d-%H%M%S).tar.gz -C /data .
	@echo "$(GREEN)✅ Backup completado en ./backups/$(RESET)"

restore: ## 📦 Restaurar desde backup (especificar BACKUP_DATE=YYYYMMDD-HHMMSS)
	@echo "$(BOLD)$(YELLOW)📦 Restaurando backup...$(RESET)"
	@if [ -z "$(BACKUP_DATE)" ]; then echo "$(RED)❌ Especifica BACKUP_DATE=YYYYMMDD-HHMMSS$(RESET)"; exit 1; fi
	docker compose down -v
	docker volume create rsm-rag-service_redis_data
	docker volume create rsm-rag-service_qdrant_data
	docker run --rm -v rsm-rag-service_redis_data:/data -v $(PWD)/backups:/backup alpine tar xzf /backup/redis-$(BACKUP_DATE).tar.gz -C /data
	docker run --rm -v rsm-rag-service_qdrant_data:/data -v $(PWD)/backups:/backup alpine tar xzf /backup/qdrant-$(BACKUP_DATE).tar.gz -C /data
	docker compose up -d
	@echo "$(GREEN)✅ Restore completado$(RESET)"

# ================================================
# 🚀 DEPLOYMENT & PRODUCTION
# ================================================

.PHONY: prod prod-up prod-down prod-logs prod-status deploy-check
prod: ## 🚀 Modo producción
	@echo "$(BOLD)$(GREEN)🚀 Iniciando en modo producción...$(RESET)"
	docker compose -f docker-compose.prod.yml up -d

prod-up: prod ## 🚀 Alias para prod

prod-down: ## ⏹️ Detener producción
	docker compose -f docker-compose.prod.yml down

prod-logs: ## 📝 Logs de producción
	docker compose -f docker-compose.prod.yml logs -f

prod-status: ## 📊 Status de producción
	docker compose -f docker-compose.prod.yml ps

deploy-check: ## ✅ Verificar si está listo para deploy
	@echo "$(BOLD)$(BLUE)✅ Verificando readiness para deploy...$(RESET)"
	@echo "$(CYAN)Tests:$(RESET)"
	@cd api && python -m pytest tests/test_basic.py::test_health -q && echo "✅ Tests OK" || echo "❌ Tests FAILED"
	@echo "$(CYAN)Code Quality:$(RESET)"
	@cd api && python -m black app/ --check && echo "✅ Format OK" || echo "❌ Format FAILED"
	@echo "$(CYAN)Security:$(RESET)"
	@cd api && python -m bandit -r app/ -f json -o /dev/null && echo "✅ Security OK" || echo "❌ Security ISSUES"
	@echo "$(CYAN)Build:$(RESET)"
	@docker build -t rag-api:test -f api/Dockerfile api >/dev/null 2>&1 && echo "✅ Build OK" || echo "❌ Build FAILED"

# ================================================
# 🔑 QUICK ACTIONS & UTILITIES
# ================================================

.PHONY: quick-test demo load-test example-ingest example-query install-deps
quick-test: up ## ⚡ Quick test del sistema completo
	@echo "$(BOLD)$(GREEN)⚡ Quick test...$(RESET)"
	@sleep 5
	@echo "$(CYAN)Health check:$(RESET)"
	@curl -s http://localhost:8000/health >/dev/null && echo "✅ API OK" || echo "❌ API DOWN"
	@echo "$(CYAN)Test ingest:$(RESET)"
	@curl -s -X POST http://localhost:8000/ingest -H 'Content-Type: application/json' -d '{"content":"Test doc","document_type":"text"}' | jq -r .job_id > /tmp/job_id
	@echo "$(CYAN)Test query:$(RESET)"
	@sleep 3
	@curl -s -X POST "http://localhost:8000/query" -H 'Content-Type: application/json' -d '{"question":"test"}' >/dev/null && echo "✅ Query OK" || echo "❌ Query FAILED"

demo: ## 🎬 Demo completo con datos reales
	@echo "$(BOLD)$(GREEN)🎬 Ejecutando demo completo...$(RESET)"
	@echo "$(CYAN)Ingesting PEP 8...$(RESET)"
	@curl -s -X POST http://localhost:8000/ingest -H 'Content-Type: application/json' -d '{"content":"https://peps.python.org/pep-0008/","document_type":"html"}' | jq .
	@sleep 10
	@echo "$(CYAN)Querying about Python conventions...$(RESET)"
	@curl -s -X POST "http://localhost:8000/query?retriever=hybrid&top_k=3" -H 'Content-Type: application/json' -d '{"question":"What are Python naming conventions?"}' | jq .

load-test: ## 🔥 Load test básico
	@echo "$(BOLD)$(BLUE)🔥 Load test (requiere 'hey' tool)...$(RESET)"
	@if ! command -v hey >/dev/null 2>&1; then echo "❌ Instala 'hey': go install github.com/rakyll/hey@latest"; exit 1; fi
	hey -n 50 -c 5 -m POST -T application/json -d '{"question":"test"}' http://localhost:8000/query

example-ingest: ## 📄 Ejemplo de ingest
	@echo "$(BOLD)$(BLUE)📄 Ejemplo de ingest:$(RESET)"
	curl -X POST http://localhost:8000/ingest \
		-H 'Content-Type: application/json' \
		-d '{"content":"https://peps.python.org/pep-0008/","document_type":"html"}'

example-query: ## ❓ Ejemplo de query
	@echo "$(BOLD)$(BLUE)❓ Ejemplo de query:$(RESET)"
	curl -X POST "http://localhost:8000/query?retriever=hybrid&top_k=3" \
		-H 'Content-Type: application/json' \
		-d '{"question":"What are Python naming conventions?"}'

install-deps: ## 📦 Instalar dependencias locales
	@echo "$(BOLD)$(BLUE)📦 Instalando dependencias...$(RESET)"
	cd api && pip install -r requirements.txt

# ================================================
# 🎯 DEVELOPMENT WORKFLOW
# ================================================

.PHONY: dev-setup dev-test dev-clean pre-commit ci-local
dev-setup: install-deps ## 🛠️ Setup completo de desarrollo
	@echo "$(BOLD)$(GREEN)🛠️ Setup de desarrollo...$(RESET)"
	@if [ ! -f .env ]; then cp .env.example .env; echo "📄 .env creado desde .env.example"; fi
	@echo "✅ Listo para desarrollo!"

dev-test: format lint test-unit ## 🔄 Workflow de testing en desarrollo

dev-clean: ## 🧹 Limpiar archivos de desarrollo
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf api/.coverage api/htmlcov api/.pytest_cache

pre-commit: quality test-unit ## ✅ Pre-commit checks

ci-local: clean up test-all ## 🎯 Simular CI localmente
	@echo "$(BOLD)$(GREEN)🎯 Simulando CI completo...$(RESET)"

# ================================================
# INFO & DEBUG
# ================================================

.PHONY: info version env-info docker-info
info: ## ℹ️ Información del sistema
	@echo "$(BOLD)$(BLUE)ℹ️ RAG Microservice Info:$(RESET)"
	@echo "Version: v1.0"
	@echo "Compose file: $(COMPOSE_FILE)"
	@echo "Services: $(API_SERVICE), $(REDIS_SERVICE), $(QDRANT_SERVICE), $(JAEGER_SERVICE)"

version: ## 📋 Versiones de herramientas
	@echo "$(BOLD)$(BLUE)📋 Tool Versions:$(RESET)"
	@echo "Docker: $$(docker --version 2>/dev/null || echo 'Not installed')"
	@echo "Docker Compose: $$(docker compose version 2>/dev/null || echo 'Not installed')"
	@echo "Python: $$(python --version 2>/dev/null || echo 'Not installed')"
	@echo "Make: $$(make --version | head -n1 2>/dev/null || echo 'Not installed')"

env-info: ## 🌍 Información del entorno
	@echo "$(BOLD)$(BLUE)🌍 Environment Info:$(RESET)"
	@echo "OS: $$(uname -s)"
	@echo "Architecture: $$(uname -m)"
	@echo "Shell: $$SHELL"
	@echo "User: $$USER"
	@echo "PWD: $$PWD"

docker-info: ## 🐳 Información de Docker
	@echo "$(BOLD)$(BLUE)🐳 Docker Info:$(RESET)"
	docker system df
	@echo "\n$(CYAN)Running Containers:$(RESET)"
	docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"