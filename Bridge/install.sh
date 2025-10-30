#!/usr/bin/env bash
# Installation script for MilluBridge

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🎯 MilluBridge Installation${NC}"
echo ""

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}UV not found. Installing UV...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Add UV to PATH for current session
    export PATH="$HOME/.cargo/bin:$PATH"
    
    # Verify installation
    if ! command -v uv &> /dev/null; then
        echo "❌ UV installation failed. Please install manually:"
        echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    
    echo -e "${GREEN}✅ UV installed successfully${NC}"
else
    echo -e "${GREEN}✅ UV found: $(uv --version)${NC}"
fi

echo ""

# Create virtual environment
echo -e "${BLUE}Creating virtual environment...${NC}"
uv venv

echo -e "${GREEN}✅ Virtual environment created${NC}"
echo ""

# Sync dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
uv sync

echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Success message
echo -e "${GREEN}🎉 Installation complete!${NC}"
echo ""
echo "To activate the virtual environment, run:"
echo -e "${BLUE}  source .venv/bin/activate${NC}"
echo ""
echo "Or run directly with:"
echo -e "${BLUE}  ./run.sh${NC}"
echo -e "${BLUE}  # or${NC}"
echo -e "${BLUE}  uv run python src/main.py${NC}"
