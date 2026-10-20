#!/usr/bin/env bash
set -euo pipefail

echo "=== Phase 1/6: build image (lending-local:v16, no-cache) ==="
docker build \
  --no-cache \
  --secret id=apps_json,src=apps.json \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH=version-16 \
  --build-arg=PYTHON_VERSION=3.14 \
  --build-arg=NODE_VERSION=24 \
  --tag=lending-local:v16 \
  --file=images/custom/Containerfile .

echo "=== Phase 2/6: recreate the stack ==="
echo "WARNING: 'down -v' destroys the db-data, redis-queue-data and sites volumes. All existing site data will be lost."
docker compose -f lending-compose.yaml --project-name lending down -v
docker compose -f lending-compose.yaml --project-name lending up -d --pull missing

echo "=== Phase 3/6: verify each app's git branch (from BRANCHES.txt, written at build time before .git was stripped) ==="
docker compose -f lending-compose.yaml --project-name lending exec backend \
  cat /home/frappe/frappe-bench/BRANCHES.txt

echo "=== Phase 4/6: create the site ==="
docker compose -f lending-compose.yaml --project-name lending exec backend \
  bench new-site lending.localhost \
    --mariadb-root-password changeit123 \
    --admin-password admin \
    --db-root-username root \
    --install-app erpnext \
    --install-app payments \
    --install-app lending \
    --set-default

echo "=== Phase 5/6: enable the scheduler ==="
docker compose -f lending-compose.yaml --project-name lending exec backend \
  bench --site lending.localhost enable-scheduler

echo "=== Phase 6/6: done ==="
echo "Open http://lending.localhost:8080  (Administrator / admin)"
