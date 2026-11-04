#!/usr/bin/env bash
# Build lending-local:v16-ai (lending image + lending_assistant app) and install it on the site.
# Never runs 'down -v'. Existing site data is kept.
set -euo pipefail

COMPOSE=(docker compose -f lending-compose.yaml --project-name lending)
BASE=lending-local:v16
AI=lending-local:v16-ai

echo "=== Phase 1/3: base image ==="
if ! docker image inspect "$BASE" >/dev/null 2>&1; then
  echo "Base image $BASE missing. Building it (same command as run.sh phase 1, no stack changes)."
  docker build \
    --no-cache \
    --secret id=apps_json,src=apps.json \
    --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
    --build-arg=FRAPPE_BRANCH=version-16 \
    --build-arg=PYTHON_VERSION=3.14 \
    --build-arg=NODE_VERSION=24 \
    --tag="$BASE" \
    --file=images/custom/Containerfile .
else
  echo "Found $BASE, reusing."
fi

echo "=== Phase 2/3: layer lending_assistant ==="
docker build \
  --build-arg BASE_IMAGE="$BASE" \
  --tag "$AI" \
  --file images/lending-assistant/Containerfile .

echo "=== Phase 3/3: start stack ==="
# The compose 'init' service installs lending_assistant on an existing site and migrates.
# On a fresh volume it creates the site. Data is kept; no 'down -v'.
"${COMPOSE[@]}" up -d
"${COMPOSE[@]}" exec backend cat /home/frappe/frappe-bench/BRANCHES.txt

echo "Done. Open http://lending.localhost:8080/app/lending-assistant-settings and set the Anthropic API key."
