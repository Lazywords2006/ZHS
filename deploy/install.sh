#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root: sudo bash deploy/install.sh"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

INSTALL_DIR="${INSTALL_DIR:-/opt/ZHS}"
DEPLOY_USER="${DEPLOY_USER:-${SUDO_USER:-$(id -un)}}"
DEPLOY_GROUP="${DEPLOY_GROUP:-${DEPLOY_USER}}"
DOMAIN="${DOMAIN:-_}"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

if ! id -u "${DEPLOY_USER}" >/dev/null 2>&1; then
  echo "Deploy user '${DEPLOY_USER}' does not exist"
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This installer currently targets Debian/Ubuntu systems with apt-get"
  exit 1
fi

apt-get update
apt-get install -y \
  "${PYTHON_BIN}" \
  "${PYTHON_BIN}-venv" \
  python3-pip \
  nodejs \
  npm \
  nginx \
  rsync \
  logrotate

mkdir -p "${INSTALL_DIR}"
rsync -a \
  --delete \
  --exclude '.git' \
  --exclude '.github' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude 'config.json' \
  --exclude 'cookies.json' \
  --exclude 'execution.json' \
  --exclude 'logs' \
  --exclude 'web-demo/.env.local' \
  --exclude 'web-demo/node_modules' \
  --exclude 'web-demo/dist' \
  --exclude 'web-demo/backend/runtime' \
  "${REPO_DIR}/" "${INSTALL_DIR}/"

chown -R "${DEPLOY_USER}:${DEPLOY_GROUP}" "${INSTALL_DIR}"

sudo -u "${DEPLOY_USER}" mkdir -p "${INSTALL_DIR}/logs" "${INSTALL_DIR}/web-demo/backend/runtime"

if [[ ! -d "${INSTALL_DIR}/.venv" ]]; then
  sudo -u "${DEPLOY_USER}" "${PYTHON_BIN}" -m venv "${INSTALL_DIR}/.venv"
fi

sudo -u "${DEPLOY_USER}" "${INSTALL_DIR}/.venv/bin/python" -m pip install --upgrade pip
sudo -u "${DEPLOY_USER}" "${INSTALL_DIR}/.venv/bin/python" -m pip install -r "${INSTALL_DIR}/requirements.txt"
sudo -u "${DEPLOY_USER}" "${INSTALL_DIR}/.venv/bin/python" -m pip install -r "${INSTALL_DIR}/web-demo/backend/requirements.txt"

cat > "${INSTALL_DIR}/web-demo/.env.local" <<EOF
VITE_USE_MOCK=false
VITE_API_BASE_URL=
EOF

sudo -u "${DEPLOY_USER}" bash -lc "cd '${INSTALL_DIR}/web-demo' && npm ci && npm run build"

mkdir -p /etc/zhs
if [[ "${DOMAIN}" == "_" ]]; then
  cat > /etc/zhs/zhs-backend.env <<EOF
PYTHONUNBUFFERED=1
CORS_ALLOW_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
EOF
else
  cat > /etc/zhs/zhs-backend.env <<EOF
PYTHONUNBUFFERED=1
CORS_ALLOW_ORIGINS=http://${DOMAIN},https://${DOMAIN}
EOF
fi

sed \
  -e "s|User=zhs|User=${DEPLOY_USER}|" \
  -e "s|Group=zhs|Group=${DEPLOY_GROUP}|" \
  -e "s|/opt/ZHS|${INSTALL_DIR}|g" \
  -e "s|127.0.0.1|${BACKEND_HOST}|g" \
  -e "s|8000|${BACKEND_PORT}|g" \
  "${INSTALL_DIR}/deploy/systemd/zhs-backend.service" \
  > /etc/systemd/system/zhs-backend.service

sed \
  -e "s|server_name _;|server_name ${DOMAIN};|" \
  -e "s|/opt/ZHS|${INSTALL_DIR}|g" \
  -e "s|127.0.0.1|${BACKEND_HOST}|g" \
  -e "s|8000|${BACKEND_PORT}|g" \
  "${INSTALL_DIR}/deploy/nginx/zhs.conf" \
  > /etc/nginx/sites-available/zhs.conf

sed \
  -e "s|/opt/ZHS|${INSTALL_DIR}|g" \
  "${INSTALL_DIR}/deploy/logrotate/zhs" \
  > /etc/logrotate.d/zhs

ln -sf /etc/nginx/sites-available/zhs.conf /etc/nginx/sites-enabled/zhs.conf
rm -f /etc/nginx/sites-enabled/default

systemctl daemon-reload
systemctl enable --now zhs-backend.service
nginx -t
systemctl reload nginx

echo
echo "Deployment complete."
echo "Backend service: systemctl status zhs-backend.service"
echo "Frontend root: ${INSTALL_DIR}/web-demo/dist"
echo "Runtime data: ${INSTALL_DIR}/web-demo/backend/runtime"
echo "Backend env file: /etc/zhs/zhs-backend.env"
echo "Logrotate rule: /etc/logrotate.d/zhs"
