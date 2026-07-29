#!/usr/bin/env bash
# Copy the backend code to the server. Run this from the repo root ON YOUR MAC.
#
#   bash deploy/push.sh
#
# It rsyncs the repo (minus junk) to the server. You will be asked for the SSH
# password once (or use an SSH key — see deploy/README.md step 1 to avoid that).
set -euo pipefail

SSH_USER="${SSH_USER:-zah19-team40}"
SSH_HOST="${SSH_HOST:-118.102.2.140}"
APP_DIR="${APP_DIR:-/home/zah19-team40/app}"

echo "→ Pushing code to ${SSH_USER}@${SSH_HOST}:${APP_DIR}"

# --- what NOT to upload: local venv (wrong arch), node deps, build output,
#     the local SQLite DB, git internals, macOS cruft. Note: .env IS uploaded
#     so the server gets your keys — remove it from --exclude if you'd rather
#     create the server .env by hand.
rsync -az --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'miniapp/node_modules' \
  --exclude 'miniapp/www' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'tripsmart.db' \
  --exclude '.DS_Store' \
  ./ "${SSH_USER}@${SSH_HOST}:${APP_DIR}/"

echo "✓ Code uploaded. Next: SSH in and run the server-side setup (README step 3)."
