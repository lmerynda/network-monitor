#!/usr/bin/env bash

set -euo pipefail

VERSION="$(git rev-parse --short HEAD)"
PACKAGE_NAME="network-monitor-${VERSION}"
DIST_DIR="dist"
STAGE_DIR="${DIST_DIR}/${PACKAGE_NAME}"
ARCHIVE_PATH="${DIST_DIR}/${PACKAGE_NAME}.tar.gz"

rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}"

cp -r network_monitor "${STAGE_DIR}/"
cp -r systemd "${STAGE_DIR}/"
cp README.md pyproject.toml config.example.json install.sh "${STAGE_DIR}/"

find "${STAGE_DIR}" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "${STAGE_DIR}" -type f -name "*.pyc" -delete

chmod 755 "${STAGE_DIR}/install.sh"

tar -C "${DIST_DIR}" -czf "${ARCHIVE_PATH}" "${PACKAGE_NAME}"

echo "Created ${ARCHIVE_PATH}"
