#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <user@host> [remote-dir]" >&2
  exit 1
fi

REMOTE_HOST="$1"
REMOTE_BASE_DIR="${2:-/tmp}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

"${SCRIPT_DIR}/build-package.sh"

ARCHIVE_PATH="$(ls -t dist/network-monitor-*.tar.gz | head -n 1)"
ARCHIVE_NAME="$(basename "${ARCHIVE_PATH}")"
PACKAGE_DIR="${ARCHIVE_NAME%.tar.gz}"
REMOTE_ARCHIVE="${REMOTE_BASE_DIR}/${ARCHIVE_NAME}"
REMOTE_PACKAGE_DIR="${REMOTE_BASE_DIR}/${PACKAGE_DIR}"

echo "Copying ${ARCHIVE_NAME} to ${REMOTE_HOST}:${REMOTE_BASE_DIR}/"
scp "${ARCHIVE_PATH}" "${REMOTE_HOST}:${REMOTE_ARCHIVE}"

echo "Installing on ${REMOTE_HOST}"
ssh -t "${REMOTE_HOST}" "
  set -euo pipefail
  mkdir -p '${REMOTE_BASE_DIR}'
  rm -rf '${REMOTE_PACKAGE_DIR}'
  tar -xzf '${REMOTE_ARCHIVE}' -C '${REMOTE_BASE_DIR}'
  cd '${REMOTE_PACKAGE_DIR}'
  sudo ./install.sh
"

echo "Deployment finished."
