# MilluBridge# Nowde - ESP32-S3 USB MIDI Device



**Real-time media synchronization bridge between Millumin and ESP32 devices via wireless mesh network**


MilluBridge is a complete system for distributing synchronized media playback information from [Millumin](https://www.millumin.com) (a professional video mapping software) to multiple ESP32-based MIDI receivers over a wireless ESP-NOW mesh network. Perfect for multi-screen installations, distributed AV systems, and synchronized show control.

## Hardware
---
**Board**: ESP32-S3 DevKit C-1

- **USB Ports**: 
   - **USB Port (UART)**: Used for flashing and serial debugging
   - **USB Port (Native)**: Used for USB MIDI communication

## 🎯 Key Features  

- **📡 Wireless Distribution**: ESP-NOW mesh network for low-latency, reliable communication

- **🎬 Media Synchronization**: MTC (MIDI Time Code) + CC#100 for media index and position

- **⏱️ Sub-frame Accuracy**: Mesh-synchronized clocks with latency compensation

- **💾 Persistent Configuration**: Receiver layer assignments stored in EEPROM- Native USB MIDI support using ESP32-S3's built-in USB

- **🖥️ GUI Management**: Python-based bridge with real-time monitoring- Recognized as a standard USB MIDI device on any computer

- **🔄 Auto-recovery**: Freewheel mode and connection timeout handling- No external MIDI hardware required

- **🎵 Standard MIDI Output**: Works with any MIDI-compatible software/hardware

## Setup

---

### Prerequisites

## 📋 System Overview

1. Install [PlatformIO](https://platformio.org/install)

```2. Install PlatformIO extension in VS Code (recommended)

Millumin (OSC)  →  Bridge (Python/GUI)  →  Sender Nowde (USB MIDI + ESP-NOW)

                                                        ↓### Building and Uploading

                                         ┌──────────────┴────────────────┐

                                         ↓                               ↓1. Connect the ESP32-S3 to your computer via the **UART USB port** (for flashing)

                              Receiver Nowde 1                 Receiver Nowde 22. Build the project:

                              (MIDI: CC#100 + MTC)             (MIDI: CC#100 + MTC)   ```bash

                              Layer: "player1"                 Layer: "player2"   pio run

```   ```

3. Upload to the board:

### Components   ```bash

   pio run --target upload

1. **Millumin** - Video playback software (OSC sender)   ```

2. **Bridge** - Python application with GUI (OSC → USB MIDI)

3. **Sender Nowde** - ESP32-S3 device (USB MIDI → ESP-NOW mesh)### Using USB MIDI

4. **Receiver Nowde(s)** - ESP32-S3 device(s) (ESP-NOW → MIDI output)

1. After uploading, disconnect the UART USB cable

---2. Connect the **Native USB port** to your computer

3. The device should appear as a USB MIDI device in your DAW or MIDI software

## ⚡ Quick Start

## Configuration

### Prerequisites

### Build Flags

- **Hardware**:

  - 1× ESP32-S3 DevKit C-1 (Sender)The project uses these important build flags in `platformio.ini`:

  - 1+ ESP32-S3 DevKit C-1 (Receivers)

  - USB cables (data + power)- `ARDUINO_USB_MODE=1`: Enable native USB mode

- `ARDUINO_USB_CDC_ON_BOOT=0`: Disable CDC on boot to allow MIDI

- **Software**:- `BOARD_HAS_USB_NATIVE=1`: Indicate native USB support

  - Python 3.8+

  - [PlatformIO](https://platformio.org/install)#### Optional: Force Receiver Subscription (Test)

  - [Millumin](https://www.millumin.com) (trial or full version)

For testing, you can force the device to start directly in receiver mode and subscribe to a specific "layer" without sending a SysEx command.

### Installation

Use the following define either at the top of `src/main.cpp` or via `platformio.ini` build flags:

1. **Flash Nowde Firmware** (do this for each ESP32):

   ```bash- `FORCE_RECEIVER_LAYER="LayerName"`

   cd Nowde

   pio run --target uploadExample using `platformio.ini`:

   ```

```ini

2. **Install Bridge**:[env:esp32-s3-devkitc-1]

   ```bashbuild_flags =

   cd Bridge   -DARDUINO_USB_MODE=1

   python -m venv .venv   -DARDUINO_USB_CDC_ON_BOOT=0

   source .venv/bin/activate  # On Windows: .venv\Scripts\activate   -DFORCE_RECEIVER_LAYER=\"TestLayer\"

   pip install -r requirements.txt```

   ```

When this define is present, the firmware:

3. **Configure Millumin**:

   - Open Device Manager > OSC- Enables receiver mode on boot

   - Enable "Send feedback"- Subscribes to the specified layer

   - Set target: `127.0.0.1:8000`- Will still accept a later SysEx Subscribe Layer message that can change the subscription



4. **Launch System**:### MIDI Library

   ```bash

   # In Bridge folderThe project uses the `USBMIDI` library for ESP32-S3, which provides:

   python src/main.py- `MIDI.noteOn(note, velocity, channel)`

   ```- `MIDI.noteOff(note, velocity, channel)`

- `MIDI.controlChange(controller, value, channel)`

5. **Assign Receiver Layers**:- And other standard MIDI messages

   - Connect Sender Nowde via USB

   - Wait for receivers to appear in "Remote Nowdes" table## Example Code

   - Click on each receiver's Layer button

   - Select or type a layer name (e.g., "player1")The default `main.cpp` sends a test MIDI note every 2 seconds. You can modify this to:

   - Click Apply

- Read sensors and send MIDI CC messages

6. **Name Media Files** (in Millumin):- Respond to MIDI input from a computer

   - Format: `NNN_filename.ext` (e.g., `001_video.mp4`)- Create a custom MIDI controller

   - First 1-3 digits = media index (1-127)

## Troubleshooting

✅ **Done!** Play media in Millumin and receivers will output synchronized MIDI.

### Device not recognized

---

1. Make sure you're using the **Native USB port**, not the UART port

## 🎮 Features in Detail2. Check that the USB cable supports data transfer (not just power)

3. Try a different USB port on your computer

### Media Synchronization

### Upload fails

- **Media Index** via CC#100 (0=stop, 1-127=media index from filename)

- **Position Sync** via MTC quarter-frames at 30fps1. Make sure you're using the **UART USB port** for flashing

- **Latency Compensation** using mesh-synchronized timestamps2. Hold the BOOT button while connecting if the board doesn't enter bootloader mode

- **Clock Validation** discards out-of-sync packets (200ms threshold)3. Check that the correct port is selected in PlatformIO

- **Freewheel Mode** continues MTC updates during brief interruptions (3s timeout)

- **Stop Burst** sends multiple stop commands for reliable reception



### Network Features


- **ESP-NOW Mesh**: Low-latency wireless protocol (faster than WiFi)
- **Mesh Clock Sync**: Sub-10ms synchronization across devices
- **Auto-discovery**: Receivers automatically register with sender
- **Connection Monitoring**: Real-time status (ACTIVE/MISSING)
- **Persistent Peers**: Receivers remembered across reboots

### GUI Controls

- **Throttle Rate**: Adjustable 1-60 Hz (default 10 Hz)
- **MTC Framerate**: Configurable (default 30fps)
- **Freewheel Timeout**: Adjustable (default 3.0s)
- **Desync Threshold**: Configurable (default 200ms)
- **Live Monitoring**: OSC logs, Nowde logs, layer status, receiver table

---

## 📚 Documentation

- **[Getting Started Guide](docs/GETTING_STARTED.md)** - Detailed setup instructions
- **[Architecture](docs/ARCHITECTURE.md)** - System design and protocols
- **[User Guide](docs/USER_GUIDE.md)** - How to use the system
- **[Developer Guide](docs/DEVELOPER_GUIDE.md)** - API reference and development
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

---

## 🔧 Technical Specs

| Feature | Specification |
|---------|--------------|
| **Latency** | 10-50ms typical (including network, processing, compensation) |
| **Update Rate** | 1-60 Hz configurable (default 10 Hz) |
| **Max Receivers** | 10 per sender |
| **Max Senders** | 10 per receiver |
| **Clock Sync** | < 10ms drift over 1 hour |
| **Packet Loss** | < 1% on stable network |
| **Range** | 10-100m (line of sight, varies by environment) |
| **MIDI Output** | USB MIDI (class-compliant) |

---

## 🗂️ Project Structure

```
MilluBridge/
├── README.md                 # This file
├── Bridge/                   # Python bridge application
│   ├── src/
│   │   ├── main.py          # Main GUI application
│   │   ├── osc/             # OSC server
│   │   └── midi/            # MIDI output manager
│   └── requirements.txt     # Python dependencies
├── Nowde/                    # ESP32 firmware
│   ├── src/main.cpp         # Main firmware
│   └── platformio.ini       # PlatformIO config
└── docs/                     # Documentation
    ├── GETTING_STARTED.md
    ├── ARCHITECTURE.md
    ├── USER_GUIDE.md
    ├── DEVELOPER_GUIDE.md
    └── TROUBLESHOOTING.md
```

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test thoroughly
4. Submit a pull request

---

## 📄 License

This program is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License v3.0** as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [GNU General Public License](LICENSE) for more details.

**Copyright (C) 2025 maigre - Hemisphere Project**

---

## 🙏 Acknowledgments

- **ESPNowMeshClock** library for distributed time synchronization
- **Millumin** for OSC protocol documentation
- **PlatformIO** for ESP32 development platform
- **Claude Sonnet 4.5** and all the content creators feeding it

---

## 📞 Support

For issues or questions:
- Check the [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- Review serial debug output (115200 baud)
- Open an issue on GitHub

---

**Built with ❤️ for the AV production community**
