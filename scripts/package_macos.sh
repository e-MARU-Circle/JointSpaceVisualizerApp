#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

DIST_DIR="${ROOT_DIR}/dist"
CACHE_DIR="${ROOT_DIR}/.pyinstaller-cache"
APP_BUNDLE="${DIST_DIR}/JointSpaceVisualizer.app"
ONEDIR="${DIST_DIR}/JointSpaceVisualizer"
ZIP_OUTPUT="${DIST_DIR}/JointSpaceVisualizer_mac.zip"

mkdir -p "${CACHE_DIR}"

echo "Cleaning previous macOS artifacts..."
rm -rf "${ONEDIR}" \
       "${APP_BUNDLE}" \
       "${ZIP_OUTPUT}"

echo "Building with PyInstaller..."
MPLCONFIGDIR="${ROOT_DIR}/.joint_space_visualizer/matplotlib" \
PYVISTA_USERDATA_PATH="${ROOT_DIR}/.joint_space_visualizer" \
./venv/bin/python -m PyInstaller --noconfirm JointSpaceVisualizer.spec

if [[ ! -d "${APP_BUNDLE}" ]]; then
  echo "ERROR: App bundle not found at ${APP_BUNDLE}" >&2
  exit 1
fi

echo "Creating zip archive..."
(cd "${DIST_DIR}" && zip -rq "$(basename "${ZIP_OUTPUT}")" "$(basename "${APP_BUNDLE}")")

echo "Done. Artifacts:"
echo "  - ${APP_BUNDLE}"
echo "  - ${ZIP_OUTPUT}"
