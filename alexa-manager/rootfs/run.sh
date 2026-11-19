#!/command/with-contenv bash
set -euo pipefail

mkdir -p "${ALEXA_MANAGER_DATA_DIR:-/data}"

exec /opt/alexa-manager-venv/bin/uvicorn main:app \
    --app-dir /app \
    --host 0.0.0.0 \
    --port 8093
