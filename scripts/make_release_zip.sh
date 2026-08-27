#!/usr/bin/env bash
# Construit l'archive de distribution a partir du dernier commit.
# Usage : bash scripts/make_release_zip.sh [version]
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-$(grep -oP '__version__ = "\K[^"]+' transcribe_ai/__init__.py)}"
NAME="TranscribeAI-v${VERSION}"
WORK="$(mktemp -d)"
mkdir -p "${WORK}/TranscribeAI"
git archive HEAD | tar -x -C "${WORK}/TranscribeAI"
rm -f "${NAME}.zip"
(cd "${WORK}" && zip -qr - TranscribeAI -x "*.pyc" "*__pycache__*") > "${NAME}.zip"
rm -rf "${WORK}"
echo "Archive generee : ${NAME}.zip ($(du -h "${NAME}.zip" | cut -f1))"
