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

## 🎬 Millumin Setup

MilluBridge works with Millumin in **Dashboard mode only**. Timeline mode is not yet supported because Millumin does not provide OSC feedback about media status and position when using timelines.

### Enable OSC Feedback in Millumin

1. Open Millumin and go to **Interact > Device Manager** (⌘D)
2. Click the **+** button and add an **OSC** device
3. Configure the OSC output:
   - **Host**: `127.0.0.1` (if MilluBridge runs on the same machine)
   - **Port**: `8000` (default MilluBridge OSC port)
4. Enable **OSC Feedback** to send layer state updates

### Setting Up Video Layers (Canvas Layers)

To synchronize video playback with remote Nowde devices:

1. **Create a Canvas Layer** in Millumin's Dashboard
2. **Name the layer** with the exact name that matches your Nowde device configuration
   - Example: `Layer1`, `MainVideo`, `Background`
3. **Add media** to the layer by dragging video files into it
4. **Media naming convention**: Prefix your media files with a number (1-127) followed by underscore
   - Example: `001_intro.mov`, `042_main_sequence.mp4`, `100_outro.mov`
   - The number becomes the media index sent to remote Nowde devices

**In MilluBridge UI:**
- The **Millumin Layers** table shows all detected layers with their current state
- **State**: `playing`, `paused`, or `stopped`
- **Filename**: Currently loaded media file
- **Position/Duration**: Playback progress

### Setting Up Light Layers (DALI Control)

To control DALI lights via the Hasseb DALI Master USB:

1. **Create a Data Layer** in Millumin's Dashboard
2. **Configure the Data Layer**:
   - **Mode**: `OSC`
   - **Method**: `Continuous`
   - **Address**: `/L{channel}` where `{channel}` is 1-16
     - Example: `/L1` for DALI channel 1, `/L7` for channel 7
   - **Range**: `0` to `255` (DALI brightness range)
3. **Add a value/gradient** to control the light level
   - Drag a color/gradient or use the data layer's built-in controls
   - The value (0-255) is sent continuously to the DALI device

**In MilluBridge UI:**
- The **MilluBridge Lights** table shows all light channels receiving data
- **Channel**: Light address (L1-L16)
- **Value**: Current brightness level (0-255)
- **Status**:
  - `OK` (green): DALI device detected and responding
  - `No Response` (orange): No DALI device at this address
  - `...` (grey): Scanning in progress

**Testing lights:**
- Click on a channel name (e.g., `L7`) in the table to **identify** it (device will blink)
- Use **All On** button to set all lights to full brightness
- Use **Blackout** button to turn off all lights

### Understanding the MilluBridge Display

| Section | What it shows |
|---------|---------------|
| **OSC Status** | Green checkmark = receiving OSC from Millumin |
| **Millumin Layers** | Video layers with playback state, media name, position |
| **MilluBridge Lights** | DALI light channels with values and device status |
| **Local Nowde** | USB-connected Nowde device status and firmware version |
| **Dali Master** | Hasseb DALI USB device connection status |
| **Remote Nowdes** | ESP-NOW mesh network devices and their assigned layers |

### Verifying Communication

1. **OSC from Millumin**: Check the OSC status indicator turns green when Millumin is running
2. **Light control working**: 
   - Change a Data Layer value in Millumin
   - The corresponding light channel value should update in MilluBridge
   - The physical light should respond (if DALI device is connected)
3. **Video sync working**:
   - Play a media in a Canvas Layer
   - The layer should appear in the Millumin Layers table with `playing` state
   - Position should increment as playback progresses

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
