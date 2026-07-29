#!/usr/bin/env bash
# Run this ON THE SERVER, inside the app dir, after pushing the code.
#
#   cd ~/app && bash deploy/server_setup.sh
#
# Creates the Python venv, installs deps, and checks the .env. No sudo needed.
set -euo pipefail

cd "$(dirname "$0")/.."
echo "→ App dir: $(pwd)"

# Pick a Python 3.9+ interpreter.
PY="$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3.9 || command -v python3)"
echo "→ Using: $PY ($($PY --version 2>&1))"

$PY -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt
echo "✓ Dependencies installed."

if [ ! -f .env ]; then
  echo "⚠  No .env found. Create one with your keys before starting:"
  echo "     cp .env.example .env  &&  nano .env     # set ANTHROPIC_API_KEY + SERPAPI_KEY"
  exit 1
fi

# Quick smoke test that the app imports and the tools/prompt load.
./.venv/bin/python -c "import tripsmart.server; print('✓ App imports OK')"
echo "✓ Server-side setup done. Start it via systemd (README step 5a) or: "
echo "    ./.venv/bin/uvicorn tripsmart.server:app --host 127.0.0.1 --port 3100 --env-file .env"
