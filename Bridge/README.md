# MilluBridge

OSC to MIDI bridge with ESP-NOW mesh synchronization for media playback with Millumin.

## 🚀 Quick Start (Development)

### Prerequisites

- Python 3.8 or higher
- [UV](https://github.com/astral-sh/uv) package manager

### Installation

```bash
# Install UV if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/Hemisphere-Project/MillluBridge.git
cd MillluBridge/Bridge

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows

# Sync dependencies from pyproject.toml
uv sync

# Run the application
uv run python src/main.py
```

### Alternative: Run without activating environment

```bash
# UV can run commands directly
uv run python src/main.py
```

## 📦 Building Portable Executables

### Using PyInstaller (Recommended - Faster Build)

```bash
# Add development dependencies
uv sync --extra dev

# Make build script executable
chmod +x scripts/build.sh

# Build
./scripts/build.sh
```

The executable will be in `dist/MilluBridge-{platform}` where platform is `macos` or `linux`.

### Using Nuitka (Better Performance - Slower Build)

```bash
# Add build dependencies
uv sync --extra build

# Make build script executable
chmod +x scripts/build-nuitka.sh

# Build (this takes longer but produces smaller/faster executables)
./scripts/build-nuitka.sh
```

### Manual Build Commands

**PyInstaller:**
```bash
uv run pyinstaller --onefile --name MilluBridge src/main.py
```

**Nuitka:**
```bash
uv run python -m nuitka --onefile --output-dir=dist src/main.py
```

## 🛠️ Development

### Project Structure

```
Bridge/
├── src/
│   ├── main.py              # Main application
│   ├── bridge/
│   │   ├── __init__.py
│   │   └── mapper.py        # OSC to MIDI mapping
│   ├── gui/
│   │   ├── __init__.py
│   │   └── main_window.py   # DearPyGUI interface
│   ├── midi/
│   │   ├── __init__.py
│   │   ├── input_manager.py # MIDI input handling
│   │   └── output_manager.py# MIDI output handling
│   └── osc/
│       ├── __init__.py
│       ├── message_handler.py
│       └── server.py         # OSC server
├── config.json              # Application configuration
├── pyproject.toml           # Project metadata and dependencies
├── scripts/
│   ├── build.sh            # PyInstaller build script
│   └── build-nuitka.sh     # Nuitka build script
└── README.md
```

### Adding Dependencies

```bash
# Add a runtime dependency
uv add package-name

# Add a development dependency
uv add --dev package-name

# Add an optional dependency (for builds)
uv add --optional build package-name
```

### Code Formatting (Optional)

```bash
# Format code with black
uv run black src/

# Lint with ruff
uv run ruff check src/
```

## 📝 Configuration

Edit `config.json` to configure:
- OSC server address and port
- MIDI device settings
- Media sync parameters
- RF simulation settings

## 🐛 Troubleshooting

### UV not found
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv
```

### MIDI device not found
- Ensure your MIDI device (Nowde) is connected via USB
- Check that the device name starts with "Nowde"
- Try reconnecting the USB cable

### OSC not receiving
- Verify Millumin is sending OSC feedback (Device Manager > OSC)
- Check the OSC address and port match in both applications
- Ensure firewall allows UDP traffic on the configured port

## 📄 License

GNU General Public License v3.0 or later (GPLv3+)

Copyright (C) 2025 Hemisphere Project

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
