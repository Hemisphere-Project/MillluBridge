#!/usr/bin/env bash
# Build script for creating a universal2 MilluBridge app bundle using Nuitka

set -euo pipefail

if [[ "${OSTYPE}" != "darwin"* ]]; then
    echo "❌ This script can only be run on macOS."
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
cd "${PROJECT_ROOT}"

echo "🏗️  Building MilluBridge (universal2) with Nuitka..."

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Installing build dependencies...${NC}"
uv sync --extra build

mkdir -p dist

if [ -f "icon.png" ]; then
    if [ ! -f "icon.icns" ] || [ "icon.png" -nt "icon.icns" ]; then
        echo -e "${BLUE}Generating icon.icns from icon.png...${NC}"
        uv run python scripts/process-icon.py icon.png icon-processed.png

        ICONSET_DIR="icon.iconset"
        rm -rf "${ICONSET_DIR}"
        mkdir "${ICONSET_DIR}"

        sips -z 16 16     "icon-processed.png" --out "${ICONSET_DIR}/icon_16x16.png" >/dev/null 2>&1
        sips -z 32 32     "icon-processed.png" --out "${ICONSET_DIR}/icon_16x16@2x.png" >/dev/null 2>&1
        sips -z 32 32     "icon-processed.png" --out "${ICONSET_DIR}/icon_32x32.png" >/dev/null 2>&1
        sips -z 64 64     "icon-processed.png" --out "${ICONSET_DIR}/icon_32x32@2x.png" >/dev/null 2>&1
        sips -z 128 128   "icon-processed.png" --out "${ICONSET_DIR}/icon_128x128.png" >/dev/null 2>&1
        sips -z 256 256   "icon-processed.png" --out "${ICONSET_DIR}/icon_128x128@2x.png" >/dev/null 2>&1
        sips -z 256 256   "icon-processed.png" --out "${ICONSET_DIR}/icon_256x256.png" >/dev/null 2>&1
        sips -z 512 512   "icon-processed.png" --out "${ICONSET_DIR}/icon_256x256@2x.png" >/dev/null 2>&1
        sips -z 512 512   "icon-processed.png" --out "${ICONSET_DIR}/icon_512x512.png" >/dev/null 2>&1
        sips -z 1024 1024 "icon-processed.png" --out "${ICONSET_DIR}/icon_512x512@2x.png" >/dev/null 2>&1

        iconutil -c icns "${ICONSET_DIR}" -o icon.icns
        rm -rf "${ICONSET_DIR}" icon-processed.png
        echo -e "${GREEN}✅ icon.icns ready${NC}"
    else
        echo -e "${BLUE}icon.icns is up to date${NC}"
    fi
fi

ICON_FLAG=""
if [ -f "icon.icns" ]; then
    ICON_FLAG="--macos-app-icon=icon.icns"
fi

echo -e "${BLUE}Building universal2 app bundle...${NC}"
uv run python -m nuitka \
    --standalone \
    --macos-create-app-bundle \
    --macos-app-name="MilluBridge" \
    --macos-target-arch=universal \
    --output-dir=dist \
    --enable-plugin=no-qt \
    --assume-yes-for-downloads \
    --disable-console \
    ${ICON_FLAG} \
    src/main.py

UNIVERSAL_APP="dist/MilluBridge-universal.app"
if [ -d "dist/main.app" ]; then
    rm -rf "${UNIVERSAL_APP}"
    mv "dist/main.app" "${UNIVERSAL_APP}"
    echo -e "${GREEN}✅ Build successful: ${UNIVERSAL_APP}${NC}"
else
    echo "❌ Build failed - .app bundle not found"
    exit 1
fi

echo ""
echo "🎉 Done! Open with: open ${UNIVERSAL_APP}"
