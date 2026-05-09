#!/usr/bin/env bash
# 把 dist/ShapeYourPhoto.app 打包成 ShapeYourPhoto-<version>.dmg
# 依赖: create-dmg (brew install create-dmg)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 从 app_metadata 读版本号
APP_VERSION="$(python3 -c 'from app_metadata import APP_VERSION; print(APP_VERSION)')"
APP_NAME="ShapeYourPhoto"
APP_PATH="dist/${APP_NAME}.app"
DMG_DIR="dist_installer"
# 命名约定：ShapeYourPhoto-<version>-macOS-<arch>.dmg
ARCH="$(uname -m)"   # arm64 或 x86_64
DMG_PATH="${DMG_DIR}/${APP_NAME}-${APP_VERSION}-macOS-${ARCH}.dmg"

if [[ ! -d "$APP_PATH" ]]; then
  echo "Error: $APP_PATH not found. Run pyinstaller first." >&2
  exit 1
fi

if ! command -v create-dmg >/dev/null 2>&1; then
  echo "Error: create-dmg not installed. Run: brew install create-dmg" >&2
  exit 1
fi

mkdir -p "$DMG_DIR"
rm -f "$DMG_PATH"

create-dmg \
  --volname "${APP_NAME} ${APP_VERSION}" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --icon "${APP_NAME}.app" 200 185 \
  --hide-extension "${APP_NAME}.app" \
  --app-drop-link 600 185 \
  --no-internet-enable \
  "$DMG_PATH" \
  "$APP_PATH"

echo "Built: $DMG_PATH"
