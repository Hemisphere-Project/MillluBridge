#!/usr/bin/env bash
# Build script for creating portable MilluBridge executables with Nuitka
# Nuitka produces smaller and faster executables

set -e

echo "🏗️  Building MilluBridge with Nuitka..."

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="linux"
else
    echo "❌ Unsupported platform: $OSTYPE"
    exit 1
fi

echo -e "${BLUE}Platform detected: ${PLATFORM}${NC}"

# Create dist directory
mkdir -p dist

# Build with Nuitka
echo -e "${BLUE}Building with Nuitka (this may take a while)...${NC}"
uv run python -m nuitka \
    --onefile \
    --output-dir=dist \
    --output-filename="MilluBridge-${PLATFORM}" \
    --include-data-files=config.json=config.json \
    --enable-plugin=no-qt \
    --assume-yes-for-downloads \
    src/main.py

if [ -f "dist/MilluBridge-${PLATFORM}" ]; then
    echo -e "${GREEN}✅ Build successful!${NC}"
    echo -e "${GREEN}Executable: dist/MilluBridge-${PLATFORM}${NC}"
    
    # Make executable
    chmod +x "dist/MilluBridge-${PLATFORM}"
    
    # Show file size
    ls -lh "dist/MilluBridge-${PLATFORM}"
else
    echo "❌ Build failed - executable not found"
    exit 1
fi

echo ""
echo "🎉 Done! Run with: ./dist/MilluBridge-${PLATFORM}"
