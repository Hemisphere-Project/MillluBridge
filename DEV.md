# MilluBridge - Developer Guide

This document covers development, building, and technical implementation details for MilluBridge.

> 📖 **For users**: See [README.md](README.md) for usage instructions and Millumin setup.

---

## 🗂️ Project Structure

```
MilluBridge/
├── README.md                 # User documentation
├── DEV.md                    # This file (developer documentation)
├── Bridge/                   # Python bridge application
│   ├── src/
│   │   ├── main.py          # Main GUI application
│   │   ├── osc/             # OSC server
│   │   ├── midi/            # MIDI input/output managers
│   │   ├── dali_control/    # DALI Master USB control
│   │   └── bridge/          # OSC to MIDI mapping
│   ├── scripts/             # Build scripts
│   ├── pyproject.toml       # Project metadata and dependencies
│   └── config.json          # Application configuration
├── Nowde/                    # ESP32 firmware
│   ├── src/
│   │   ├── main.cpp         # Main firmware
│   │   ├── sysex.cpp        # SysEx protocol implementation
│   │   ├── sender_mode.cpp  # Sender mode logic
│   │   └── receiver_mode.cpp # Receiver mode logic
│   └── platformio.ini       # PlatformIO config
└── docs/                     # Additional documentation
```

---

## 🚀 Bridge Development

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

---

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

---

## 🔌 Nowde Firmware Development

### Prerequisites

- [PlatformIO](https://platformio.org/install)
- ESP32-S3 DevKit C-1 board

### Flashing Firmware

```bash
cd Nowde
pio run --target upload
```

### Build Flags

The project uses these important build flags in `platformio.ini`:

- `ARDUINO_USB_MODE=1`: Enable native USB mode
- `ARDUINO_USB_CDC_ON_BOOT=0`: Disable CDC on boot to allow MIDI
- `BOARD_HAS_USB_NATIVE=1`: Indicate native USB support

### Force Receiver Mode (Testing)

For testing, you can force the device to start directly in receiver mode and subscribe to a specific layer:

```ini
[env:esp32-s3-devkitc-1]
build_flags =
   -DARDUINO_USB_MODE=1
   -DARDUINO_USB_CDC_ON_BOOT=0
   -DFORCE_RECEIVER_LAYER=\"TestLayer\"
```

When this define is present, the firmware:
- Enables receiver mode on boot
- Subscribes to the specified layer
- Will still accept a later SysEx Subscribe Layer message that can change the subscription

### MIDI Library

The project uses the `USBMIDI` library for ESP32-S3, which provides:
- `MIDI.noteOn(note, velocity, channel)`
- `MIDI.noteOff(note, velocity, channel)`
- `MIDI.controlChange(controller, value, channel)`
- And other standard MIDI messages

---

## 🔧 Communication Protocol

### SysEx Commands (7-bit Encoded)

The system uses a custom SysEx protocol (Manufacturer ID: `0x7D`) with **7-bit encoding** for all multi-byte data to ensure USB MIDI compatibility and prevent protocol corruption.

**Bridge → Sender:**
- `0x01` QUERY_CONFIG - Request current configuration
- `0x02` PUSH_FULL_CONFIG - Update RF simulation settings
- `0x03` QUERY_RUNNING_STATE - Request receiver table status
- `0x10` MEDIA_SYNC - Send media index/position/state
- `0x11` CHANGE_RECEIVER_LAYER - Update receiver layer assignment

**Sender → Bridge:**
- `0x20` HELLO - Boot/reboot notification (includes version, uptime, boot reason)
- `0x21` CONFIG_STATE - Current configuration response
- `0x22` RUNNING_STATE - Receiver table and mesh status (7-bit encoded)
- `0x30` ERROR_REPORT - Error notifications

### Media Synchronization

- **Media Index**: 1-127 (parsed from filename prefix, 0 = stopped)
- **Position**: Milliseconds, sent via SysEx
- **State**: `playing`, `paused`, `stopped`

### Reconnection Handling

The system implements robust reconnection logic:

- **HELLO Handshake**: Sender sends HELLO on boot and when receiving QUERY_CONFIG
- **Auto-Initialization**: Bridge sends QUERY_CONFIG on connection, triggering sender response
- **State Management**: Bridge tracks `sender_initialized` flag, only queries when ready
- **Disconnect Detection**: Auto-detects USB disconnect and clears stale receiver table
- **Hot-Plug Support**: Handles all scenarios:
  - ✅ Sender boot with Bridge running
  - ✅ Bridge restart with sender running
  - ✅ Sender disconnect/reconnect
  - ✅ Sender quick reboot

---

## 📝 Configuration

Edit `Bridge/config.json` to configure:
- OSC server address and port
- MIDI device settings
- Media sync parameters
- RF simulation settings (for testing)

---

## 🐛 Troubleshooting (Development)

### UV not found
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv
```

### Upload fails
1. Make sure you're using the **UART USB port** for flashing
2. Hold the BOOT button while connecting if the board doesn't enter bootloader mode
3. Check that the correct port is selected in PlatformIO

### Device not recognized
1. Make sure you're using the **Native USB port**, not the UART port
2. Check that the USB cable supports data transfer (not just power)
3. Try a different USB port on your computer

### Serial Debug Output
- Connect to UART port at 115200 baud for debug messages

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test thoroughly (all reconnection scenarios)
4. Submit a pull request

---

## 📄 License

GNU General Public License v3.0 or later (GPLv3+)

Copyright (C) 2025 maigre - Hemisphere Project
