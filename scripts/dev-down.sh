#!/usr/bin/env sh
set -eu

docker compose --env-file .env -f infrastructure/docker-compose.yml down
