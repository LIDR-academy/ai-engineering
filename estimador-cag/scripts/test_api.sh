#!/bin/bash
# Script de testing rapido contra la API local
# Uso: bash scripts/test_api.sh
set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo ">>> Testing GET /health"
curl -s "${BASE_URL}/health" | python -m json.tool || curl -s "${BASE_URL}/health"

echo ""
echo ">>> Testing POST /api/v1/estimate"
curl -s -X POST "${BASE_URL}/api/v1/estimate" \\
  -H "Content-Type: application/json" \\
  -d @../docs/sample_request.json | python -m json.tool || curl -s -X POST "${BASE_URL}/api/v1/estimate" -H "Content-Type: application/json" -d @../docs/sample_request.json

echo ""
echo ">>> Done."
