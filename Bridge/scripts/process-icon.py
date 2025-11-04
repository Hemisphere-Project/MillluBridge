#!/usr/bin/env python3
"""
Process icon.png for macOS app bundle
Adds rounded corners and proper transparency for native macOS look
"""

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("ERROR: Pillow not installed. Install with: uv pip install pillow")
    sys.exit(1)


def create_rounded_mask(size, radius_percent=0.225):
    """Create a rounded rectangle mask for macOS-style icons
    
    Args:
        size: (width, height) tuple
        radius_percent: Corner radius as percentage of size (default 22.5% matches macOS)
    """
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    
    # Calculate radius (22.5% is the standard macOS app icon radius)
    radius = int(min(size) * radius_percent)
    
    # Draw rounded rectangle
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    
    return mask


def process_icon(input_path, output_path, padding_percent=0.10):
    """Process icon: add rounded corners and ensure proper transparency
    
    Args:
        input_path: Path to input PNG
        output_path: Path to output PNG
        padding_percent: Padding as percentage of size (default 10% matches macOS)
    """
    
    # Open image
    img = Image.open(input_path)
    
    # Convert to RGBA if not already
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Original size
    size = img.size
    
    # Calculate padding and content size
    padding = int(min(size) * padding_percent)
    content_size = (size[0] - 2 * padding, size[1] - 2 * padding)
    
    # Resize content to fit with padding
    img_resized = img.resize(content_size, Image.Resampling.LANCZOS)
    
    # Create rounded mask for the CONTENT (not full size)
    mask = create_rounded_mask(content_size)
    
    # Apply mask to resized content
    img_resized.putalpha(mask)
    
    # Create final transparent image
    processed = Image.new('RGBA', size, (0, 0, 0, 0))
    
    # Paste rounded content centered with padding
    processed.paste(img_resized, (padding, padding), img_resized)
    
    # Save
    processed.save(output_path, 'PNG')
    print(f"✅ Processed icon: {output_path}")
    print(f"   - Added rounded corners (macOS style)")
    print(f"   - Applied {int(padding_percent*100)}% padding")
    print(f"   - Transparent background")


def main():
    if len(sys.argv) < 2:
        print("Usage: process-icon.py <input.png> [output.png]")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)
    
    # Default output is icon-processed.png
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("icon-processed.png")
    
    process_icon(input_path, output_path)


if __name__ == "__main__":
    main()
