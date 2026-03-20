#!/usr/bin/env bash

set -euo pipefail

APP_NAME="network-monitor"
INSTALL_DIR="/opt/${APP_NAME}"
CONFIG_DIR="/etc/${APP_NAME}"
DATA_DIR="/var/lib/${APP_NAME}"
BIN_PATH="/usr/local/bin/${APP_NAME}"
SERVICE_PATH="/etc/systemd/system/${APP_NAME}.service"
SERVICE_USER="network-monitor"
SERVICE_GROUP="network-monitor"

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Run as root: sudo ./install.sh" >&2
    exit 1
  fi
}

create_user() {
  if ! getent group "${SERVICE_GROUP}" >/dev/null; then
    groupadd --system "${SERVICE_GROUP}"
  fi

  if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
    useradd \
      --system \
      --gid "${SERVICE_GROUP}" \
      --home-dir "${INSTALL_DIR}" \
      --shell /usr/sbin/nologin \
      "${SERVICE_USER}"
  fi
}

install_files() {
  mkdir -p "${INSTALL_DIR}" "${CONFIG_DIR}" "${DATA_DIR}"

  cp -r network_monitor "${INSTALL_DIR}/"
  cp pyproject.toml "${INSTALL_DIR}/"
  cp README.md "${INSTALL_DIR}/"

  if [[ ! -f "${CONFIG_DIR}/config.json" ]]; then
    cp config.example.json "${CONFIG_DIR}/config.json"
  fi

  cp systemd/network-monitor.service "${SERVICE_PATH}"

  cat > "${BIN_PATH}" <<'EOF'
#!/usr/bin/env bash
cd /opt/network-monitor
exec /usr/bin/python3 -m network_monitor.main --config /etc/network-monitor/config.json "$@"
EOF
  chmod 755 "${BIN_PATH}"
}

fix_permissions() {
  chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${INSTALL_DIR}" "${DATA_DIR}"
  chown root:root "${CONFIG_DIR}" "${CONFIG_DIR}/config.json" "${SERVICE_PATH}" "${BIN_PATH}"
  chmod 755 "${INSTALL_DIR}" "${CONFIG_DIR}" "${DATA_DIR}"
  chmod 644 "${CONFIG_DIR}/config.json" "${SERVICE_PATH}"
}

reload_service() {
  systemctl daemon-reload
  systemctl enable --now "${APP_NAME}.service"
}

main() {
  require_root
  create_user
  install_files
  fix_permissions
  reload_service

  echo "Installed ${APP_NAME}."
  echo "Config: ${CONFIG_DIR}/config.json"
  echo "Data: ${DATA_DIR}/network-monitor.sqlite3"
  echo "Status: systemctl status ${APP_NAME}"
  echo "CLI: ${BIN_PATH} status --limit 10"
}

main "$@"
