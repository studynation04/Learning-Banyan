#!/usr/bin/env bash
# Install Learning Banyan on a Hostinger VPS next to an existing :80 site.
# Run from the project root:
#   sudo bash deploy/hostinger/install.sh
set -euo pipefail

APP_NAME="learning-banyan"
DEFAULT_PORT="8080"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SERVICE_SRC="${SCRIPT_DIR}/learning-banyan.service"
SERVICE_DST="/etc/systemd/system/${APP_NAME}.service"
ENV_EXAMPLE="${SCRIPT_DIR}/env.example"
ENV_FILE="${APP_DIR}/.env"
RUN_USER="${SUDO_USER:-${USER}}"
RUN_GROUP="$(id -gn "${RUN_USER}")"
VPS_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
VPS_IP="${VPS_IP:-YOUR_VPS_IPV4}"

echo "== Learning Banyan Hostinger install =="
echo "App dir : ${APP_DIR}"
echo "User    : ${RUN_USER}"
echo "VPS IP  : ${VPS_IP}"
echo "URL     : http://${VPS_IP}:${DEFAULT_PORT}/"
echo
echo "This will NOT bind port 80 or 443 (your existing site stays)."
echo

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash deploy/hostinger/install.sh"
  exit 1
fi

PYTHON_BIN=""
for candidate in python3.12 python3.13 python3; do
  if command -v "${candidate}" >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v "${candidate}")"
    break
  fi
done
if [ -z "${PYTHON_BIN}" ]; then
  echo "Python 3 not found. Install Python 3.12+ first."
  exit 1
fi

PY_VER="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Using ${PYTHON_BIN} (${PY_VER})"
"${PYTHON_BIN}" - <<'PY'
import sys
if sys.version_info < (3, 12):
    raise SystemExit("Django 6 needs Python 3.12+. On Ubuntu 22.04: apt install python3.12 python3.12-venv")
PY

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  python3-venv python3-pip python3-dev build-essential \
  libjpeg-dev zlib1g-dev libpng-dev \
  libreoffice-writer-nogui fonts-dejavu-core fonts-liberation \
  curl

if ! "${PYTHON_BIN}" -m venv --help >/dev/null 2>&1; then
  apt-get install -y python3.12-venv || apt-get install -y python3-venv
fi

if [ ! -d "${APP_DIR}/.venv" ]; then
  "${PYTHON_BIN}" -m venv "${APP_DIR}/.venv"
fi
# shellcheck disable=SC1091
source "${APP_DIR}/.venv/bin/activate"
pip install --upgrade pip
pip install -r "${APP_DIR}/requirements.txt"

if [ ! -f "${ENV_FILE}" ]; then
  SECRET="$("${APP_DIR}/.venv/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed \
    -e "s|YOUR_VPS_IPV4|${VPS_IP}|g" \
    -e "s|change-me-to-a-long-random-string|${SECRET}|g" \
    "${ENV_EXAMPLE}" > "${ENV_FILE}"
  echo "Wrote ${ENV_FILE}"
else
  echo "Keeping existing ${ENV_FILE}"
fi

chown "${RUN_USER}:${RUN_GROUP}" "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

mkdir -p "${APP_DIR}/media" "${APP_DIR}/staticfiles"
chown -R "${RUN_USER}:${RUN_GROUP}" "${APP_DIR}/media" "${APP_DIR}/staticfiles" "${APP_DIR}/.venv"

cd "${APP_DIR}"
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

"${APP_DIR}/.venv/bin/python" manage.py migrate --noinput
"${APP_DIR}/.venv/bin/python" manage.py collectstatic --noinput

sed \
  -e "s|REPLACE_USER|${RUN_USER}|g" \
  -e "s|REPLACE_GROUP|${RUN_GROUP}|g" \
  -e "s|REPLACE_APP_DIR|${APP_DIR}|g" \
  "${SERVICE_SRC}" > "${SERVICE_DST}"

systemctl daemon-reload
systemctl enable "${APP_NAME}"
systemctl restart "${APP_NAME}"

if command -v ufw >/dev/null 2>&1; then
  ufw allow "${DEFAULT_PORT}/tcp" || true
fi

echo
echo "systemd: systemctl status ${APP_NAME} --no-pager"
systemctl --no-pager --full status "${APP_NAME}" || true
echo
echo "Open this port in Hostinger hPanel too: VPS → Firewall → allow TCP ${DEFAULT_PORT}"
echo "Existing website on :80 is unchanged."
echo "Visit: http://${VPS_IP}:${DEFAULT_PORT}/"
echo "Health: http://${VPS_IP}:${DEFAULT_PORT}/healthz/"
echo
echo "Create an admin user:"
echo "  sudo -u ${RUN_USER} ${APP_DIR}/.venv/bin/python ${APP_DIR}/manage.py createsuperuser"
