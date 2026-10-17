#!/usr/bin/env bash
# Run from any directory. Browser tests start isolated local application servers.
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python -m pip check
.venv/bin/python scripts/export_contracts.py --check
.venv/bin/python -m ruff check backend tests scripts
.venv/bin/python -m pytest -q
npm --prefix frontend run contracts:check
npm --prefix frontend run test:unit
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend run test:e2e
npm --prefix frontend run test:e2e:providers
