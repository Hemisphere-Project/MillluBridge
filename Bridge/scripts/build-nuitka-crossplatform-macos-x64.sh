#!/usr/bin/env bash
# Build script for creating Intel (x86_64) MilluBridge app bundles with Nuitka
# Can be invoked from Apple Silicon hosts (requires Rosetta 2)

set -e

if [[ "$OSTYPE" == "darwin"* && "$(uname -m)" == "arm64" && -z "${MB_CROSS_TO_X64:-}" ]]; then
    if ! arch -x86_64 /usr/bin/true >/dev/null 2>&1; then
        echo "❌ Rosetta 2 is required to build Intel binaries. Install it with: softwareupdate --install-rosetta"
        exit 1
    fi
    export MB_CROSS_TO_X64=1
    BASH_BIN="$(command -v bash)"
    exec arch -x86_64 "${BASH_BIN}" "$0" "$@"
fi

select_python_for_arch() {
    local target_arch="$1"
    shift
    for candidate in "$@"; do
        if command -v "$candidate" >/dev/null 2>&1; then
            local machine
            machine="$("$candidate" -c 'import platform; print(platform.machine())' 2>/dev/null || true)"
            if [[ "$machine" == "$target_arch" ]]; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

echo "🏗️  Building MilluBridge with Nuitka..."

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script only works on macOS when producing Intel builds."
    exit 1
fi

PLATFORM="macos"
ARCHITECTURE="$(uname -m)"
MACOS_TARGET_ARCH="x86_64"
MACOS_MIN_VERSION="${MACOS_MIN_VERSION_X64:-10.14}"
BUILD_SUFFIX="-macos-intel"

echo -e "${BLUE}Platform detected: ${PLATFORM} (${ARCHITECTURE}) targeting ${MACOS_TARGET_ARCH}${NC}"

export MACOSX_DEPLOYMENT_TARGET="${MACOS_MIN_VERSION}"
echo -e "${BLUE}Targeting macOS ${MACOSX_DEPLOYMENT_TARGET}+${NC}"

MIN_VERSION_FLAG="-mmacosx-version-min=${MACOS_MIN_VERSION}"
export CFLAGS="${MIN_VERSION_FLAG} ${CFLAGS:-}"
export CXXFLAGS="${MIN_VERSION_FLAG} ${CXXFLAGS:-}"
export LDFLAGS="${MIN_VERSION_FLAG} ${LDFLAGS:-}"

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
if [[ "$PYTHON_VERSION" == 3.14* ]]; then
    echo -e "${BLUE}⚠️  Warning: Python 3.14 detected. Nuitka may have compatibility issues.${NC}"
    echo -e "${BLUE}   Consider downgrading to Python 3.12 if build fails:${NC}"
    echo -e "${BLUE}   brew unlink python && brew install python@3.12 && brew link python@3.12${NC}"
fi

# Install build dependencies (pin uv to an interpreter that matches host architecture unless overridden)
if [[ -z "${UV_PYTHON:-}" ]]; then
    if SELECTED_PY=$(select_python_for_arch "$MACOS_TARGET_ARCH" python3.12 python3.11 python3.10 python3); then
        export UV_PYTHON="$SELECTED_PY"
    else
        export UV_PYTHON="python3.12"
    fi
fi

echo -e "${BLUE}Installing build dependencies...${NC}"
uv sync --extra build

# Create dist directory
mkdir -p dist

# Auto-generate icon from icon.png if present
if [ -f "icon.png" ]; then
    echo -e "${BLUE}Found icon.png - auto-generating platform icon...${NC}"
    
    if [[ "$PLATFORM" == "macos" ]]; then
        # Convert to .icns for macOS
        if [ ! -f "icon.icns" ] || [ "icon.png" -nt "icon.icns" ]; then
            echo -e "${BLUE}Generating icon.icns from icon.png...${NC}"
            
            # Process icon: add rounded corners for macOS style
            echo -e "${BLUE}Adding rounded corners and transparency...${NC}"
            uv run python scripts/process-icon.py icon.png icon-processed.png
            
            # Create iconset directory
            ICONSET_DIR="icon.iconset"
            rm -rf "$ICONSET_DIR"
            mkdir "$ICONSET_DIR"
            
            # Generate all required sizes using sips (built-in macOS tool)
            sips -z 16 16     "icon-processed.png" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null 2>&1
            sips -z 32 32     "icon-processed.png" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null 2>&1
            sips -z 32 32     "icon-processed.png" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null 2>&1
            sips -z 64 64     "icon-processed.png" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null 2>&1
            sips -z 128 128   "icon-processed.png" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null 2>&1
            sips -z 256 256   "icon-processed.png" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null 2>&1
            sips -z 256 256   "icon-processed.png" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null 2>&1
            sips -z 512 512   "icon-processed.png" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null 2>&1
            sips -z 512 512   "icon-processed.png" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null 2>&1
            sips -z 1024 1024 "icon-processed.png" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null 2>&1
            
            # Convert to .icns
            iconutil -c icns "$ICONSET_DIR" -o icon.icns
            
            # Clean up
            rm -rf "$ICONSET_DIR"
            rm -f icon-processed.png
            
            echo -e "${GREEN}✅ Generated icon.icns (with rounded corners)${NC}"
        else
            echo -e "${BLUE}Using existing icon.icns (up to date)${NC}"
        fi
    fi
fi

# Build with Nuitka
echo -e "${BLUE}Building with Nuitka (this may take a while)...${NC}"

ICON_FLAG=""
if [ -f "icon.icns" ]; then
    echo -e "${BLUE}Using app icon: icon.icns${NC}"
    ICON_FLAG="--macos-app-icon=icon.icns"
fi

PYTHON_FOR_SCONS_FLAG=""
if command -v brew >/dev/null 2>&1; then
    BREW_PYTHON_PREFIX=$(brew --prefix python 2>/dev/null || brew --prefix python@3.14 2>/dev/null || brew --prefix python@3.13 2>/dev/null || brew --prefix python@3.12 2>/dev/null || true)
    if [ -n "$BREW_PYTHON_PREFIX" ] && [ -x "${BREW_PYTHON_PREFIX}/bin/python3" ]; then
        echo -e "${BLUE}Using Homebrew Python for scons: ${BREW_PYTHON_PREFIX}/bin/python3${NC}"
        PYTHON_FOR_SCONS_FLAG="--python-for-scons=${BREW_PYTHON_PREFIX}/bin/python3"
    fi
fi

uv run python -m nuitka \
    --standalone \
    --macos-create-app-bundle \
    --macos-app-name="MilluBridge${BUILD_SUFFIX}" \
    --output-dir=dist \
    --enable-plugin=no-qt \
    --assume-yes-for-downloads \
    --disable-console \
    --show-progress \
    --show-memory \
    --macos-target-arch=${MACOS_TARGET_ARCH} \
    ${PYTHON_FOR_SCONS_FLAG} \
    $ICON_FLAG \
    src/main.py

if [ -d "dist/main.app" ]; then
    APP_BUNDLE_PATH="dist/MilluBridge${BUILD_SUFFIX}.app"
    rm -rf "${APP_BUNDLE_PATH}"
    mv "dist/main.app" "${APP_BUNDLE_PATH}"

    PLIST_PATH="${APP_BUNDLE_PATH}/Contents/Info.plist"
    if [ -f "${PLIST_PATH}" ]; then
        if ! /usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersion ${MACOS_MIN_VERSION}" "${PLIST_PATH}" >/dev/null 2>&1; then
            /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string ${MACOS_MIN_VERSION}" "${PLIST_PATH}" >/dev/null
        fi

        if ! /usr/libexec/PlistBuddy -c "Print :LSMinimumSystemVersionByArchitecture" "${PLIST_PATH}" >/dev/null 2>&1; then
            /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersionByArchitecture dict" "${PLIST_PATH}" >/dev/null
        fi

        if ! /usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersionByArchitecture:${MACOS_TARGET_ARCH} ${MACOS_MIN_VERSION}" "${PLIST_PATH}" >/dev/null 2>&1; then
            /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersionByArchitecture:${MACOS_TARGET_ARCH} string ${MACOS_MIN_VERSION}" "${PLIST_PATH}" >/dev/null
        fi

        echo -e "${GREEN}✅ Minimum macOS version set to ${MACOS_MIN_VERSION}${NC}"
    else
        echo "⚠️ Unable to find Info.plist for stamping minimum macOS version"
    fi

    FINAL_TARGET="${APP_BUNDLE_PATH}"

    echo -e "${BLUE}Signing application bundle...${NC}"
    codesign --deep --force --sign - "${FINAL_TARGET}" 2>/dev/null || {
        echo -e "${BLUE}⚠️  Warning: codesigning failed, but continuing...${NC}"
    }

    echo -e "${GREEN}✅ Build successful!${NC}"
    echo -e "${GREEN}Application: ${FINAL_TARGET}${NC}"
    ls -lh "${FINAL_TARGET}"
else
    echo "❌ Build failed - .app bundle not found"
    exit 1
fi

echo ""
echo "🎉 Done! Open with: open ${FINAL_TARGET}"
echo ""
if [ ! -f "icon.png" ]; then
    echo "Tip: Place icon.png (1024x1024 recommended) in Bridge/ for a custom app icon"
fi
