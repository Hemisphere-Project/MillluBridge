# MilluBridge# MilluBridge



**Real-time media synchronization bridge between Millumin and ESP32 devices via wireless mesh network****Real-time media synchronization bridge between Millumin and ESP32 devices via wireless mesh network**



MilluBridge is a complete system for distributing synchronized media playback information from [Millumin](https://www.millumin.com) (a professional video mapping software) to multiple ESP32-based receivers over a wireless ESP-NOW mesh network. Perfect for multi-screen installations, distributed AV systems, and synchronized show control.MilluBridge is a complete system for distributing synchronized media playback information from [Millumin](https://www.millumin.com) (a professional video mapping software) to multiple ESP32-based receivers over a wireless ESP-NOW mesh network. Perfect for multi-screen installations, distributed AV systems, and synchronized show control.



## Hardware Requirements## Hardware Requirements



**Board**: ESP32-S3 DevKit C-1 (one for sender + one or more for receivers)**Board**: ESP32-S3 DevKit C-1 (one for sender + one or more for receivers)



- **USB Port (Native)**: Used for USB MIDI communication with Bridge- **USB Port (Native)**: Used for USB MIDI communication with Bridge

- **USB Port (UART)**: Used for flashing firmware and serial debugging- **USB Port (UART)**: Used for flashing firmware and serial debugging



---## 🎯 Key Features  



## 🎯 Key Features  - **📡 Wireless Distribution**: ESP-NOW mesh network for low-latency, reliable communication

- **🎬 Media Synchronization**: CC#100 for media index and position tracking

- **📡 Wireless Distribution**: ESP-NOW mesh network for low-latency, reliable communication- **⏱️ Sub-millisecond Accuracy**: Mesh-synchronized clocks with latency compensation

- **🎬 Media Synchronization**: CC#100 for media index and position tracking- **💾 Persistent Configuration**: Receiver layer assignments stored in EEPROM

- **⏱️ Sub-millisecond Accuracy**: Mesh-synchronized clocks with latency compensation- **🖥️ GUI Management**: Python-based bridge with real-time monitoring

- **💾 Persistent Configuration**: Receiver layer assignments stored in EEPROM- **🔄 Auto-Recovery**: Automatic reconnection handling and connection timeout management

- **🖥️ GUI Management**: Python-based bridge with real-time monitoring- **🎵 Native USB MIDI**: No external MIDI hardware required (ESP32-S3 built-in USB)

- **🔄 Auto-Recovery**: Automatic reconnection handling with HELLO handshake protocol- **🔌 Hot-Plug Support**: Graceful handling of device disconnect/reconnect scenarios

- **🎵 Native USB MIDI**: No external MIDI hardware required (ESP32-S3 built-in USB)

- **🔌 Hot-Plug Support**: Graceful handling of device disconnect/reconnect scenarios## 📋 System Overview



---```

Millumin (OSC)  →  Bridge (Python/GUI)  →  Sender Nowde (USB MIDI + ESP-NOW)

## 📋 System Overview                                                        ↓

                                         ┌──────────────┴────────────────┐

```                                         ↓                               ↓

Millumin (OSC)  →  Bridge (Python/GUI)  →  Sender Nowde (USB MIDI + ESP-NOW)                              Receiver Nowde 1                 Receiver Nowde 2

                                                        ↓                              (MIDI Output)                    (MIDI Output)

                                         ┌──────────────┴────────────────┐                              Layer: "player1"                 Layer: "player2"

                                         ↓                               ↓```

                              Receiver Nowde 1                 Receiver Nowde 2

                              (MIDI Output)                    (MIDI Output)### Components

                              Layer: "player1"                 Layer: "player2"

```1. **Millumin** - Video playback software (OSC sender)

2. **Bridge** - Python application with GUI (OSC → USB MIDI via SysEx)

### Components3. **Sender Nowde** - ESP32-S3 device (USB MIDI → ESP-NOW mesh broadcaster)

4. **Receiver Nowde(s)** - ESP32-S3 device(s) (ESP-NOW → MIDI output)

1. **Millumin** - Video playback software (OSC sender)

2. **Bridge** - Python application with GUI (OSC → USB MIDI via SysEx)## ⚡ Quick Start

3. **Sender Nowde** - ESP32-S3 device (USB MIDI → ESP-NOW mesh broadcaster)

4. **Receiver Nowde(s)** - ESP32-S3 device(s) (ESP-NOW → MIDI output)## Configuration



---### Prerequisites



## ⚡ Quick Start### Build Flags



### Prerequisites- **Hardware**:



- **Hardware**:  - 1× ESP32-S3 DevKit C-1 (Sender)The project uses these important build flags in `platformio.ini`:

  - 1× ESP32-S3 DevKit C-1 (Sender)

  - 1+ ESP32-S3 DevKit C-1 (Receivers)  - 1+ ESP32-S3 DevKit C-1 (Receivers)

  - USB cables (data + power)

  - USB cables (data + power)- `ARDUINO_USB_MODE=1`: Enable native USB mode

- **Software**:

  - Python 3.8+- `ARDUINO_USB_CDC_ON_BOOT=0`: Disable CDC on boot to allow MIDI

  - [PlatformIO](https://platformio.org/install)

  - [Millumin](https://www.millumin.com) (trial or full version)- **Software**:- `BOARD_HAS_USB_NATIVE=1`: Indicate native USB support



### Installation  - Python 3.8+



1. **Flash Nowde Firmware** (do this for each ESP32):  - [PlatformIO](https://platformio.org/install)#### Optional: Force Receiver Subscription (Test)

   ```bash

   cd Nowde  - [Millumin](https://www.millumin.com) (trial or full version)

   pio run --target upload

   ```For testing, you can force the device to start directly in receiver mode and subscribe to a specific "layer" without sending a SysEx command.



2. **Install Bridge**:### Installation

   ```bash

   cd BridgeUse the following define either at the top of `src/main.cpp` or via `platformio.ini` build flags:

   python -m venv .venv

   source .venv/bin/activate  # On Windows: .venv\Scripts\activate1. **Flash Nowde Firmware** (do this for each ESP32):

   pip install -r requirements.txt

   ```   ```bash- `FORCE_RECEIVER_LAYER="LayerName"`



3. **Configure Millumin**:   cd Nowde

   - Open Device Manager > OSC

   - Enable "Send feedback"   pio run --target uploadExample using `platformio.ini`:

   - Set target: `127.0.0.1:8000`

   ```

4. **Launch Bridge**:

   ```bash```ini

   python src/main.py

   ```2. **Install Bridge**:[env:esp32-s3-devkitc-1]



5. **Assign Receiver Layers**:   ```bashbuild_flags =

   - Connect Sender Nowde via Native USB port

   - Wait for "Nowde HELLO received" message   cd Bridge   -DARDUINO_USB_MODE=1

   - Wait for receivers to appear in "Remote Nowdes" table

   - Click on each receiver's Layer button   python -m venv .venv   -DARDUINO_USB_CDC_ON_BOOT=0

   - Select or type a layer name (e.g., "player1")

   - Click Apply   source .venv/bin/activate  # On Windows: .venv\Scripts\activate   -DFORCE_RECEIVER_LAYER=\"TestLayer\"



6. **Name Media Files** (in Millumin):   pip install -r requirements.txt```

   - Format: `NNN_filename.ext` (e.g., `001_video.mp4`)

   - First 1-3 digits = media index (1-127)   ```



✅ **Done!** Play media in Millumin and receivers will output synchronized MIDI.When this define is present, the firmware:



---3. **Configure Millumin**:



## 🔧 Communication Protocol   - Open Device Manager > OSC- Enables receiver mode on boot



### SysEx Commands (7-bit Encoded)   - Enable "Send feedback"- Subscribes to the specified layer



The system uses a custom SysEx protocol (Manufacturer ID: `0x7D`) with **7-bit encoding** for all multi-byte data to ensure USB MIDI compatibility and prevent protocol corruption.   - Set target: `127.0.0.1:8000`- Will still accept a later SysEx Subscribe Layer message that can change the subscription



**Bridge → Sender:**

- `0x01` QUERY_CONFIG - Request current configuration

- `0x02` PUSH_FULL_CONFIG - Update RF simulation settings4. **Launch System**:### MIDI Library

- `0x03` QUERY_RUNNING_STATE - Request receiver table status

- `0x10` MEDIA_SYNC - Send media index/position/state   ```bash

- `0x11` CHANGE_RECEIVER_LAYER - Update receiver layer assignment

   # In Bridge folderThe project uses the `USBMIDI` library for ESP32-S3, which provides:

**Sender → Bridge:**

- `0x20` HELLO - Boot/reboot notification (includes version, uptime, boot reason)   python src/main.py- `MIDI.noteOn(note, velocity, channel)`

- `0x21` CONFIG_STATE - Current configuration response

- `0x22` RUNNING_STATE - Receiver table and mesh status (7-bit encoded)   ```- `MIDI.noteOff(note, velocity, channel)`

- `0x30` ERROR_REPORT - Error notifications

- `MIDI.controlChange(controller, value, channel)`

### Reconnection Handling

5. **Assign Receiver Layers**:- And other standard MIDI messages

The system implements robust reconnection logic:

   - Connect Sender Nowde via USB

- **HELLO Handshake**: Sender sends HELLO on boot and when receiving QUERY_CONFIG

- **Auto-Initialization**: Bridge sends QUERY_CONFIG on connection, triggering sender response   - Wait for receivers to appear in "Remote Nowdes" table## Example Code

- **State Management**: Bridge tracks `sender_initialized` flag, only queries when ready

- **Disconnect Detection**: Auto-detects USB disconnect and clears stale receiver table   - Click on each receiver's Layer button

- **Hot-Plug Support**: Handles all scenarios:

  - ✅ Sender boot with Bridge running   - Select or type a layer name (e.g., "player1")The default `main.cpp` sends a test MIDI note every 2 seconds. You can modify this to:

  - ✅ Bridge restart with sender running

  - ✅ Sender disconnect/reconnect   - Click Apply

  - ✅ Sender quick reboot

- Read sensors and send MIDI CC messages

---

6. **Name Media Files** (in Millumin):- Respond to MIDI input from a computer

## 🎮 Features in Detail

   - Format: `NNN_filename.ext` (e.g., `001_video.mp4`)- Create a custom MIDI controller

### Media Synchronization

   - First 1-3 digits = media index (1-127)

- **Media Index** via CC#100 (0=stop, 1-127=media index from filename)

- **Position Sync** via CC#101-103 (position in milliseconds, 21-bit value)## Troubleshooting

- **Latency Compensation** using mesh-synchronized timestamps

- **Clock Validation** discards out-of-sync packets (200ms threshold)✅ **Done!** Play media in Millumin and receivers will output synchronized MIDI.

- **Freewheel Mode** continues updates during brief interruptions (3s timeout)

- **Stop Burst** sends multiple stop commands for reliable reception### Device not recognized



### Network Features---



- **ESP-NOW Mesh**: Low-latency wireless protocol (faster than WiFi)1. Make sure you're using the **Native USB port**, not the UART port

- **Mesh Clock Sync**: Sub-10ms synchronization across devices

- **Auto-Discovery**: Receivers automatically register with sender## 🎮 Features in Detail2. Check that the USB cable supports data transfer (not just power)

- **Connection Monitoring**: Real-time status (ACTIVE/MISSING in GUI)

- **Persistent Peers**: Receivers remembered across reboots3. Try a different USB port on your computer



### GUI Controls### Media Synchronization



- **Throttle Rate**: Adjustable 1-60 Hz (default 10 Hz)### Upload fails

- **Freewheel Timeout**: Adjustable (default 3.0s)

- **Desync Threshold**: Configurable (default 200ms)- **Media Index** via CC#100 (0=stop, 1-127=media index from filename)

- **RF Simulation**: Bad RF conditions testing mode

- **Live Monitoring**: OSC logs, Nowde logs, layer status, receiver table- **Position Sync** via MTC quarter-frames at 30fps1. Make sure you're using the **UART USB port** for flashing

- **Layer Management**: Visual editor for receiver layer assignments

- **Latency Compensation** using mesh-synchronized timestamps2. Hold the BOOT button while connecting if the board doesn't enter bootloader mode

---

- **Clock Validation** discards out-of-sync packets (200ms threshold)3. Check that the correct port is selected in PlatformIO

## 📚 Documentation

- **Freewheel Mode** continues MTC updates during brief interruptions (3s timeout)

- **[Getting Started Guide](docs/GETTING_STARTED.md)** - Detailed setup instructions

- **[Architecture](docs/ARCHITECTURE.md)** - System design and protocols- **Stop Burst** sends multiple stop commands for reliable reception

- **[User Guide](docs/USER_GUIDE.md)** - How to use the system

- **[Developer Guide](docs/DEVELOPER_GUIDE.md)** - API reference and development

- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Network Features

---



## 🔧 Technical Specs- **ESP-NOW Mesh**: Low-latency wireless protocol (faster than WiFi)

- **Mesh Clock Sync**: Sub-10ms synchronization across devices

| Feature | Specification |- **Auto-discovery**: Receivers automatically register with sender

|---------|--------------|- **Connection Monitoring**: Real-time status (ACTIVE/MISSING)

| **Latency** | 10-50ms typical (including network, processing, compensation) |- **Persistent Peers**: Receivers remembered across reboots

| **Update Rate** | 1-60 Hz configurable (default 10 Hz) |

| **Max Receivers** | 10 per sender |### GUI Controls

| **Clock Sync** | < 10ms drift over 1 hour |

| **Packet Loss** | < 1% on stable network |- **Throttle Rate**: Adjustable 1-60 Hz (default 10 Hz)

| **Range** | 10-100m (line of sight, varies by environment) |- **MTC Framerate**: Configurable (default 30fps)

| **MIDI Protocol** | USB MIDI (class-compliant), SysEx with 7-bit encoding |- **Freewheel Timeout**: Adjustable (default 3.0s)

- **Desync Threshold**: Configurable (default 200ms)

---- **Live Monitoring**: OSC logs, Nowde logs, layer status, receiver table



## 🗂️ Project Structure---



```## 📚 Documentation

MilluBridge/

├── README.md                 # This file- **[Getting Started Guide](docs/GETTING_STARTED.md)** - Detailed setup instructions

├── Bridge/                   # Python bridge application- **[Architecture](docs/ARCHITECTURE.md)** - System design and protocols

│   ├── src/- **[User Guide](docs/USER_GUIDE.md)** - How to use the system

│   │   ├── main.py          # Main GUI application- **[Developer Guide](docs/DEVELOPER_GUIDE.md)** - API reference and development

│   │   ├── osc/             # OSC server- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

│   │   └── midi/            # MIDI input/output managers

│   └── requirements.txt     # Python dependencies---

├── Nowde/                    # ESP32 firmware

│   ├── src/## 🔧 Technical Specs

│   │   ├── main.cpp         # Main firmware

│   │   ├── sysex.cpp        # SysEx protocol implementation| Feature | Specification |

│   │   ├── sender_mode.cpp  # Sender mode logic|---------|--------------|

│   │   └── receiver_mode.cpp # Receiver mode logic| **Latency** | 10-50ms typical (including network, processing, compensation) |

│   └── platformio.ini       # PlatformIO config| **Update Rate** | 1-60 Hz configurable (default 10 Hz) |

└── docs/                     # Documentation| **Max Receivers** | 10 per sender |

    ├── GETTING_STARTED.md| **Max Senders** | 10 per receiver |

    ├── ARCHITECTURE.md| **Clock Sync** | < 10ms drift over 1 hour |

    ├── USER_GUIDE.md| **Packet Loss** | < 1% on stable network |

    ├── DEVELOPER_GUIDE.md| **Range** | 10-100m (line of sight, varies by environment) |

    └── TROUBLESHOOTING.md| **MIDI Output** | USB MIDI (class-compliant) |

```

---

---

## 🗂️ Project Structure

## 🤝 Contributing

```

Contributions welcome! Please:MilluBridge/

1. Fork the repository├── README.md                 # This file

2. Create a feature branch├── Bridge/                   # Python bridge application

3. Test thoroughly (all reconnection scenarios)│   ├── src/

4. Submit a pull request│   │   ├── main.py          # Main GUI application

│   │   ├── osc/             # OSC server

---│   │   └── midi/            # MIDI output manager

│   └── requirements.txt     # Python dependencies

## 📄 License├── Nowde/                    # ESP32 firmware

│   ├── src/main.cpp         # Main firmware

This program is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License v3.0** as published by the Free Software Foundation.│   └── platformio.ini       # PlatformIO config

└── docs/                     # Documentation

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [GNU General Public License](LICENSE) for more details.    ├── GETTING_STARTED.md

    ├── ARCHITECTURE.md

**Copyright (C) 2025 maigre - Hemisphere Project**    ├── USER_GUIDE.md

    ├── DEVELOPER_GUIDE.md

---    └── TROUBLESHOOTING.md

```

## 🙏 Acknowledgments

---

- **ESPNowMeshClock** library for distributed time synchronization

- **Millumin** for OSC protocol documentation## 🤝 Contributing

- **PlatformIO** for ESP32 development platform

- **Claude Sonnet 4** for development assistanceContributions welcome! Please:

1. Fork the repository

---2. Create a feature branch

3. Test thoroughly

## 📞 Support4. Submit a pull request



For issues or questions:---

- Check the [Troubleshooting Guide](docs/TROUBLESHOOTING.md)

- Review serial debug output (115200 baud)## 📄 License

- Open an issue on GitHub

This program is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License v3.0** as published by the Free Software Foundation.

---

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [GNU General Public License](LICENSE) for more details.

**Built with ❤️ for the AV production community**

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
