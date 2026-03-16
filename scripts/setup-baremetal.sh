#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
BACKEND_VENV="${BACKEND_DIR}/.venv"

pick_python() {
  local candidate
  for candidate in python3.12 python3.11 python3; do
    if ! command -v "${candidate}" >/dev/null 2>&1; then
      continue
    fi

    if "${candidate}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
      echo "${candidate}"
      return 0
    fi
  done

  return 1
}

PYTHON_BIN="$(pick_python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "Python 3.11+ is required. Install python3.11 and python3.11-venv, then re-run this script."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required"
  exit 1
fi

if [[ -d "${BACKEND_VENV}" ]]; then
  if ! "${BACKEND_VENV}/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    echo "Existing backend/.venv uses Python < 3.11. Remove it and re-run:"
    echo "rm -rf backend/.venv"
    exit 1
  fi
else
  "${PYTHON_BIN}" -m venv "${BACKEND_VENV}"
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

echo "Using Python interpreter: ${PYTHON_BIN}"
echo "Backend virtualenv is ready: ${BACKEND_VENV}"
echo "Frontend build is ready: ${FRONTEND_DIR}/dist"
