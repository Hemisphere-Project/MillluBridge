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

# Install build dependencies
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
    elif [[ "$PLATFORM" == "linux" ]]; then
        # For Linux, just copy the PNG (Nuitka can use PNG directly on Linux)
        if [ ! -f "icon-linux.png" ] || [ "icon.png" -nt "icon-linux.png" ]; then
            echo -e "${BLUE}Copying icon.png for Linux build...${NC}"
            cp "icon.png" "icon-linux.png"
            echo -e "${GREEN}✅ Icon ready for Linux${NC}"
        fi
    fi
fi

# Build with Nuitka
echo -e "${BLUE}Building with Nuitka (this may take a while)...${NC}"

if [[ "$PLATFORM" == "macos" ]]; then
    # Check for custom icon
    ICON_FLAG=""
    if [ -f "icon.icns" ]; then
        echo -e "${BLUE}Using app icon: icon.icns${NC}"
        ICON_FLAG="--macos-app-icon=icon.icns"
    fi
    
    # macOS: Build as .app bundle (no terminal window, proper app icon support)
    uv run python -m nuitka \
        --standalone \
        --macos-create-app-bundle \
        --macos-app-name="MilluBridge" \
        --output-dir=dist \
        --enable-plugin=no-qt \
        --assume-yes-for-downloads \
        --disable-console \
        $ICON_FLAG \
        src/main.py
    
    # Check for .app bundle
    if [ -d "dist/main.app" ]; then
        # Rename to MilluBridge.app
        rm -rf "dist/MilluBridge.app"
        mv "dist/main.app" "dist/MilluBridge.app"
        echo -e "${GREEN}✅ Build successful!${NC}"
        echo -e "${GREEN}Application: dist/MilluBridge.app${NC}"
        ls -lh "dist/MilluBridge.app"
    else
        echo "❌ Build failed - .app bundle not found"
        exit 1
    fi
else
    # Linux: Build as single executable
    ICON_FLAG=""
    if [ -f "icon-linux.png" ]; then
        echo -e "${BLUE}Using app icon: icon-linux.png${NC}"
        ICON_FLAG="--linux-icon=icon-linux.png"
    fi
    
    uv run python -m nuitka \
        --onefile \
        --output-dir=dist \
        --output-filename="MilluBridge-${PLATFORM}" \
        --enable-plugin=no-qt \
        --assume-yes-for-downloads \
        $ICON_FLAG \
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
fi

echo ""
if [[ "$PLATFORM" == "macos" ]]; then
    echo "🎉 Done! Open with: open dist/MilluBridge.app"
    echo ""
    if [ ! -f "icon.png" ]; then
        echo "� Tip: Place icon.png (1024x1024 recommended) in Bridge/ for custom app icon"
    fi
else
    echo "🎉 Done! Run with: ./dist/MilluBridge-${PLATFORM}"
    echo ""
    if [ ! -f "icon.png" ]; then
        echo "💡 Tip: Place icon.png in Bridge/ for custom app icon"
    fi
fi
