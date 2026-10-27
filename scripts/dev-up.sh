#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

bash scripts/setup-dev.sh
docker compose --env-file .env -f license-issuer/compose.yaml up -d --build
docker compose up -d --build --remove-orphans

echo "Emisor: http://localhost:8001/"
echo "CRM:    http://localhost/"
