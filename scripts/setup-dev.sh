#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v python3.13 >/dev/null 2>&1; then
  echo "Python 3.13 es obligatorio. Instálalo y vuelve a ejecutar este script."
  exit 1
fi

python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements-dev.txt
.venv/bin/python scripts/bootstrap_env.py

echo "Entorno listo. Actívalo con: source .venv/bin/activate"
