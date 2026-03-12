#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
BACKEND_VENV="${BACKEND_DIR}/.venv"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required"
  exit 1
fi

if [[ ! -d "${BACKEND_VENV}" ]]; then
  python3 -m venv "${BACKEND_VENV}"
fi

source "${BACKEND_VENV}/bin/activate"
python -m pip install --upgrade pip
python -m pip install -e "${BACKEND_DIR}[dev]"

if [[ ! -f "${BACKEND_DIR}/.env" ]]; then
  cp "${BACKEND_DIR}/.env.bare.example" "${BACKEND_DIR}/.env"
  echo "Created ${BACKEND_DIR}/.env. Edit it and re-run if needed."
fi

(
  cd "${FRONTEND_DIR}"
  npm ci
  VITE_API_BASE_URL=/api npm run build
)

echo "Backend virtualenv is ready: ${BACKEND_VENV}"
echo "Frontend build is ready: ${FRONTEND_DIR}/dist"
