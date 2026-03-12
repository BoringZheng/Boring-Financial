#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/infra/.env.server}"
COMPOSE_FILES=(-f "${ROOT_DIR}/infra/docker-compose.yml")

if [[ "${1:-}" == "--with-vllm" ]]; then
  COMPOSE_FILES+=(-f "${ROOT_DIR}/infra/docker-compose.cloud.yml")
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose plugin is required"
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${ROOT_DIR}/infra/.env.example" "${ENV_FILE}"
  echo "Created ${ENV_FILE}. Edit it before re-running this script."
  exit 1
fi

git -C "${ROOT_DIR}" pull --ff-only
docker compose --env-file "${ENV_FILE}" "${COMPOSE_FILES[@]}" up -d --build
docker compose --env-file "${ENV_FILE}" "${COMPOSE_FILES[@]}" ps
