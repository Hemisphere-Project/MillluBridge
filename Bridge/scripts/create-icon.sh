#!/usr/bin/env bash
# Create macOS .icns icon from PNG
# Usage: ./scripts/create-icon.sh input.png

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <input.png>"
    echo "Example: $0 icon-1024.png"
    exit 1
fi

INPUT_PNG="$1"

if [ ! -f "$INPUT_PNG" ]; then
    echo "❌ Error: File not found: $INPUT_PNG"
    exit 1
fi

echo "🎨 Creating macOS icon from $INPUT_PNG..."

# Create iconset directory
ICONSET_DIR="icon.iconset"
rm -rf "$ICONSET_DIR"
mkdir "$ICONSET_DIR"

# Generate all required sizes
# macOS requires multiple sizes for different display densities
sips -z 16 16     "$INPUT_PNG" --out "$ICONSET_DIR/icon_16x16.png"
sips -z 32 32     "$INPUT_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png"
sips -z 32 32     "$INPUT_PNG" --out "$ICONSET_DIR/icon_32x32.png"
sips -z 64 64     "$INPUT_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png"
sips -z 128 128   "$INPUT_PNG" --out "$ICONSET_DIR/icon_128x128.png"
sips -z 256 256   "$INPUT_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png"
sips -z 256 256   "$INPUT_PNG" --out "$ICONSET_DIR/icon_256x256.png"
sips -z 512 512   "$INPUT_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png"
sips -z 512 512   "$INPUT_PNG" --out "$ICONSET_DIR/icon_512x512.png"
sips -z 1024 1024 "$INPUT_PNG" --out "$ICONSET_DIR/icon_512x512@2x.png"

# Convert to .icns
iconutil -c icns "$ICONSET_DIR" -o icon.icns

# Clean up
rm -rf "$ICONSET_DIR"

echo "✅ Created icon.icns"
echo ""
echo "📝 To use this icon in your build:"
echo "   Edit scripts/build-nuitka.sh and add this flag to the macOS nuitka command:"
echo "   --macos-app-icon=icon.icns \\"
echo ""
echo "   Then rebuild with: ./scripts/build-nuitka.sh"
