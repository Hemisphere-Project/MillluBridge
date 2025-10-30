#!/usr/bin/env bash
# Build script for creating portable MilluBridge executables

set -e

echo "🏗️  Building MilluBridge..."

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

# Install build dependencies
echo -e "${BLUE}Installing build dependencies...${NC}"
uv sync --extra dev

# Create dist directory
mkdir -p dist

# Build with PyInstaller
echo -e "${BLUE}Building with PyInstaller...${NC}"
uv run pyinstaller \
    --onefile \
    --name "MilluBridge-${PLATFORM}" \
    --add-data "config.json:." \
    --hidden-import "dearpygui" \
    --hidden-import "dearpygui.dearpygui" \
    --hidden-import "rtmidi" \
    --hidden-import "pythonosc" \
    --clean \
    src/main.py

# Move to dist with platform-specific name
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
