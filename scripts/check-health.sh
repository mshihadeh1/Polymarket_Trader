#!/usr/bin/env sh
set -eu

curl -fsS http://localhost:8000/healthz
echo
curl -fsS http://localhost:8000/api/v1/system/health
echo
