#!/usr/bin/env bash
# Run this once on your actual dev machine (with Docker installed).
# It builds the sandbox runtime image and runs the full test suite,
# including the real Docker security tests.
set -euo pipefail

cd "$(dirname "$0")"

echo "=== 1. Checking Docker ==="
if ! command -v docker &>/dev/null; then
  echo "Docker not found. See README.md 'Environment setup' section first."
  exit 1
fi
docker info >/dev/null 2>&1 || { echo "Docker daemon not running / permission denied."; exit 1; }
echo "Docker OK"

echo "=== 2. Building sandbox runtime image ==="
docker build -t sovereign-sandbox-runtime:latest docker/sandbox-image/

echo "=== 3. Setting up Python environment ==="
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt

echo "=== 4. Running mock + contract tests (no Docker execution) ==="
python3 -m pytest tests/unit tests/contract -k "not real" -v

echo "=== 5. Running REAL contract test (spins up a container) ==="
python3 -m pytest tests/contract -k real -v

echo "=== 6. Running full security attack matrix ==="
python3 -m pytest tests/security -v

echo "=== 7. Running the demo script against the real sandbox ==="
python3 sandbox_test.py --real

echo ""
echo "All checks passed. Your sandbox is ready to hand to Member 1."
