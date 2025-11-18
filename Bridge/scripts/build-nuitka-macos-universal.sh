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

MACOS_MIN_VERSION_X64="${MACOS_MIN_VERSION_X64:-10.15}"
MACOS_MIN_VERSION_ARM="${MACOS_MIN_VERSION_ARM:-11.0}"
export MACOSX_DEPLOYMENT_TARGET="${MACOS_MIN_VERSION_X64}"

echo "🏗️  Building MilluBridge (universal2) with Nuitka..."
echo "🎯 Targeting macOS ${MACOS_MIN_VERSION_X64}+ on x86_64 and ${MACOS_MIN_VERSION_ARM}+ on arm64"

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

    PLIST_PATH="${UNIVERSAL_APP}/Contents/Info.plist"
    if [ -f "${PLIST_PATH}" ]; then
        if /usr/libexec/PlistBuddy -c "Print :LSMinimumSystemVersion" "${PLIST_PATH}" >/dev/null 2>&1; then
            /usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersion ${MACOS_MIN_VERSION_X64}" "${PLIST_PATH}" >/dev/null
        else
            /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string ${MACOS_MIN_VERSION_X64}" "${PLIST_PATH}" >/dev/null
        fi

        if /usr/libexec/PlistBuddy -c "Print :LSMinimumSystemVersionByArchitecture" "${PLIST_PATH}" >/dev/null 2>&1; then
            /usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersionByArchitecture:x86_64 ${MACOS_MIN_VERSION_X64}" "${PLIST_PATH}" >/dev/null
            /usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersionByArchitecture:arm64 ${MACOS_MIN_VERSION_ARM}" "${PLIST_PATH}" >/dev/null
        else
            /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersionByArchitecture dict" "${PLIST_PATH}" >/dev/null
            /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersionByArchitecture:x86_64 string ${MACOS_MIN_VERSION_X64}" "${PLIST_PATH}" >/dev/null
            /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersionByArchitecture:arm64 string ${MACOS_MIN_VERSION_ARM}" "${PLIST_PATH}" >/dev/null
        fi

        echo -e "${GREEN}✅ Minimum macOS versions stamped (x86_64=${MACOS_MIN_VERSION_X64}, arm64=${MACOS_MIN_VERSION_ARM})${NC}"
    else
        echo "⚠️ Couldn't find Info.plist to stamp LSMinimumSystemVersion"
    fi
else
    echo "❌ Build failed - .app bundle not found"
    exit 1
fi

echo ""
echo "🎉 Done! Open with: open ${UNIVERSAL_APP}"
