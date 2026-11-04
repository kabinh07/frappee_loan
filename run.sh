#!/usr/bin/env bash
# One command to get the whole stack (Frappe + ERPNext + Lending + chat assistant) running.
#
#   ./run.sh              build what is missing, start everything, keep existing data
#   ./run.sh --rebuild    also rebuild the base image from scratch (slow, no cache)
#   ./run.sh --reset      DELETE all site data first (asks you to type 'yes')
#
# Then open  http://<this-machine-ip>:8080  (Administrator / admin).
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE=(docker compose -f lending-compose.yaml --project-name lending)
BASE=lending-local:v16
AI=lending-local:v16-ai
PORT=8080

REBUILD=0
RESET=0
for arg in "$@"; do
  case "$arg" in
    --rebuild) REBUILD=1 ;;
    --reset) RESET=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 1 ;;
  esac
done

echo "=== Phase 1/5: base image ($BASE) ==="
if [ "$REBUILD" = 1 ] || ! docker image inspect "$BASE" >/dev/null 2>&1; then
  NO_CACHE=()
  [ "$REBUILD" = 1 ] && NO_CACHE=(--no-cache)
  docker build \
    ${NO_CACHE[@]+"${NO_CACHE[@]}"} \
    --secret id=apps_json,src=apps.json \
    --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
    --build-arg=FRAPPE_BRANCH=version-16 \
    --build-arg=PYTHON_VERSION=3.14 \
    --build-arg=NODE_VERSION=24 \
    --tag="$BASE" \
    --file=images/custom/Containerfile .
else
  echo "Found $BASE, reusing (use --rebuild to rebuild it)."
fi

echo "=== Phase 2/5: chat assistant layer ($AI) ==="
docker build \
  --build-arg BASE_IMAGE="$BASE" \
  --tag="$AI" \
  --file=images/lending-assistant/Containerfile .

echo "=== Phase 3/5: start the stack ==="
if [ "$RESET" = 1 ]; then
  echo "WARNING: --reset runs 'down -v'. It destroys the db-data, redis-queue-data and sites volumes."
  echo "         All existing site data will be lost."
  read -r -p "Type 'yes' to continue: " answer
  [ "$answer" = "yes" ] || { echo "Aborted."; exit 1; }
  "${COMPOSE[@]}" down -v
fi
# 'init' creates the site on first run (installs erpnext, payments, lending, lending_assistant)
# and migrates on later runs. 'up -d' returns only after init succeeded and the rest started.
if ! "${COMPOSE[@]}" up -d; then
  echo "Start failed. Setup log:" >&2
  "${COMPOSE[@]}" logs --tail=60 init >&2 || true
  exit 1
fi

echo "=== Phase 4/5: verify each app's git branch (BRANCHES.txt, written at build time before .git was stripped) ==="
"${COMPOSE[@]}" exec -T backend cat /home/frappe/frappe-bench/BRANCHES.txt

echo "=== Phase 5/5: wait for the site to answer on port $PORT ==="
ready=0
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null "http://localhost:$PORT/api/method/ping"; then
    ready=1
    break
  fi
  sleep 3
done
if [ "$ready" != 1 ]; then
  echo "Site did not answer within 3 minutes. Check: ${COMPOSE[*]} logs --tail=100 backend frontend" >&2
  exit 1
fi

HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "Ready. Login: Administrator / admin"
echo "  This machine : http://localhost:$PORT"
[ -n "$HOST_IP" ] && echo "  By IP        : http://$HOST_IP:$PORT"
echo "Chat assistant: click the round button at the bottom-right of any page."
echo "  No API key yet? Add it at /app/lending-assistant-settings (or set ANTHROPIC_API_KEY in .env and re-run)."
