#!/usr/bin/env bash
# One-command start for macOS/Linux
set -e
cd "$(dirname "$0")/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -r requirements.txt
fi
[ -f .env ] || cp .env.example .env
echo "Reel Routes → http://127.0.0.1:8000"
./.venv/bin/uvicorn app.main:app --reload
