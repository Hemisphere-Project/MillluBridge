#!/usr/bin/env bash
# Build script for creating an x86_64-only MilluBridge app bundle using Nuitka

set -euo pipefail

if [[ "${OSTYPE}" != "darwin"* ]]; then
    echo "❌ This script can only be run on macOS."
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
cd "${PROJECT_ROOT}"

MACOS_MIN_VERSION="${MACOS_MIN_VERSION:-10.15}"
export MACOSX_DEPLOYMENT_TARGET="${MACOS_MIN_VERSION}"

ARCH_BIN="arch"
if ! command -v "${ARCH_BIN}" >/dev/null 2>&1 || ! ${ARCH_BIN} -x86_64 /usr/bin/true >/dev/null 2>&1; then
    echo "❌ Rosetta (arch -x86_64) is required. Install with: softwareupdate --install-rosetta"
    exit 1
fi

ARCH_X64=("${ARCH_BIN}" -x86_64)
X64_VENV="${PROJECT_ROOT}/.venv-x64"
X64_PYTHON="${X64_VENV}/bin/python"

BASE_PYTHON="${PYTHON_X64_BIN:-}"
if [ -z "${BASE_PYTHON}" ]; then
    if [ -x "/usr/local/bin/python3" ]; then
        BASE_PYTHON="/usr/local/bin/python3"
    else
        BASE_PYTHON="$(command -v python3 || true)"
    fi
fi

if [ -z "${BASE_PYTHON}" ] || ! ${ARCH_X64[@]} "${BASE_PYTHON}" -c "import platform" >/dev/null 2>&1; then
    cat <<'EOF'
❌ Could not find a universal/x86_64 Python interpreter.

Please install one of the following and rerun this script:
  1. Download the "macOS 64-bit universal2 installer" from https://www.python.org/downloads/
  2. Or install an x86_64 Homebrew Python located at /usr/local/bin/python3 (via Rosetta Homebrew).

After installation, either ensure `python3` resolves to the universal binary or rerun with:
  PYTHON_X64_BIN="/path/to/python3" ./scripts/build-nuitka-macos-x64.sh
EOF
    exit 1
fi

echo "🏗️  Building MilluBridge (x86_64) with Nuitka..."
echo "🎯 Targeting macOS ${MACOSX_DEPLOYMENT_TARGET}+ runtimes"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

if [ ! -x "${X64_PYTHON}" ]; then
    echo -e "${BLUE}Creating x86_64 virtual environment at ${X64_VENV}...${NC}"
    "${ARCH_X64[@]}" "${BASE_PYTHON}" -m venv "${X64_VENV}"
fi

echo -e "${BLUE}Upgrading pip in x86_64 venv...${NC}"
"${ARCH_X64[@]}" "${X64_PYTHON}" -m pip install --upgrade pip >/dev/null 2>&1 || true

echo -e "${BLUE}Installing build dependencies into x86_64 venv...${NC}"
"${ARCH_X64[@]}" "${X64_PYTHON}" -m pip install --upgrade wheel setuptools
"${ARCH_X64[@]}" "${X64_PYTHON}" -m pip install -e ".[build]"

mkdir -p dist

if [ -f "icon.png" ]; then
    if [ ! -f "icon.icns" ] || [ "icon.png" -nt "icon.icns" ]; then
        echo -e "${BLUE}Generating icon.icns from icon.png...${NC}"
        "${ARCH_X64[@]}" "${X64_PYTHON}" scripts/process-icon.py icon.png icon-processed.png

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

echo -e "${BLUE}Building x86_64 app bundle...${NC}"
"${ARCH_X64[@]}" "${X64_PYTHON}" -m nuitka \
    --standalone \
    --macos-create-app-bundle \
    --macos-app-name="MilluBridge" \
    --macos-target-arch=x86_64 \
    --output-dir=dist \
    --enable-plugin=no-qt \
    --assume-yes-for-downloads \
    --disable-console \
    ${ICON_FLAG} \
    src/main.py

X64_APP="dist/MilluBridge-x64.app"
if [ -d "dist/main.app" ]; then
    rm -rf "${X64_APP}"
    mv "dist/main.app" "${X64_APP}"
    echo -e "${GREEN}✅ Build successful: ${X64_APP}${NC}"

    PLIST_PATH="${X64_APP}/Contents/Info.plist"
    if [ -f "${PLIST_PATH}" ]; then
        if /usr/libexec/PlistBuddy -c "Print :LSMinimumSystemVersion" "${PLIST_PATH}" >/dev/null 2>&1; then
            /usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersion ${MACOSX_DEPLOYMENT_TARGET}" "${PLIST_PATH}" >/dev/null
        else
            /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string ${MACOSX_DEPLOYMENT_TARGET}" "${PLIST_PATH}" >/dev/null
        fi

        if /usr/libexec/PlistBuddy -c "Print :LSMinimumSystemVersionByArchitecture" "${PLIST_PATH}" >/dev/null 2>&1; then
            /usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersionByArchitecture:x86_64 ${MACOSX_DEPLOYMENT_TARGET}" "${PLIST_PATH}" >/dev/null
        else
            /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersionByArchitecture dict" "${PLIST_PATH}" >/dev/null
            /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersionByArchitecture:x86_64 string ${MACOSX_DEPLOYMENT_TARGET}" "${PLIST_PATH}" >/dev/null
        fi

        echo -e "${GREEN}✅ Minimum macOS version set to ${MACOSX_DEPLOYMENT_TARGET}${NC}"
    else
        echo "⚠️ Couldn't find Info.plist to stamp LSMinimumSystemVersion"
    fi
else
    echo "❌ Build failed - .app bundle not found"
    exit 1
fi

echo ""
echo "🎉 Done! Open with: open ${X64_APP}"
