PROJECT := lending
COMPOSE := docker compose -f lending-compose.yaml --project-name $(PROJECT)
IMAGE   := lending-local:v16

.PHONY: help build up down down-v site scheduler verify-branches rebuild ps logs restart

help:
	@echo "make build            build $(IMAGE) (--no-cache)"
	@echo "make up               start the stack (docker compose up -d)"
	@echo "make down             stop the stack, KEEP volumes"
	@echo "make down-v           stop the stack and DESTROY volumes (db, redis, sites) - asks for confirmation"
	@echo "make site             create the lending.localhost site"
	@echo "make scheduler        enable the bench scheduler"
	@echo "make verify-branches  print each app's git branch from the image"
	@echo "make rebuild          full pipeline: build, down-v, up, verify-branches, site, scheduler"
	@echo "make ps               show container status"
	@echo "make logs             tail logs for all services"
	@echo "make restart          down (no volume loss) then up"

build:
	docker build \
	  --no-cache \
	  --secret id=apps_json,src=apps.json \
	  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
	  --build-arg=FRAPPE_BRANCH=version-16 \
	  --build-arg=PYTHON_VERSION=3.14 \
	  --build-arg=NODE_VERSION=24 \
	  --tag=$(IMAGE) \
	  --file=images/custom/Containerfile .

up:
	$(COMPOSE) up -d --pull missing

down:
	$(COMPOSE) down

down-v:
	@echo "WARNING: this destroys the db-data, redis-queue-data and sites volumes - ALL site data will be lost."
	@read -p "Type 'yes' to continue: " confirm; \
	if [ "$$confirm" != "yes" ]; then echo "Aborted."; exit 1; fi
	$(COMPOSE) down -v

site:
	$(COMPOSE) exec backend bench new-site lending.localhost \
	  --mariadb-root-password changeit123 \
	  --admin-password admin \
	  --db-root-username root \
	  --install-app erpnext \
	  --install-app payments \
	  --install-app lending \
	  --set-default

scheduler:
	$(COMPOSE) exec backend bench --site lending.localhost enable-scheduler

verify-branches:
	$(COMPOSE) exec backend cat /home/frappe/frappe-bench/BRANCHES.txt

rebuild: build down-v up verify-branches site scheduler
	@echo "Stack rebuilt. Open http://lending.localhost:8080 (Administrator / admin)"

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

restart: down up
