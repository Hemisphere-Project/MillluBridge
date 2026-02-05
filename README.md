# MilluBridge

**Real-time media synchronization bridge between Millumin and ESP32 devices via wireless mesh network**

MilluBridge is a complete system for distributing synchronized media playback information from [Millumin](https://www.millumin.com) (a professional video mapping software) to multiple ESP32-based receivers over a wireless ESP-NOW mesh network. Perfect for multi-screen installations, distributed AV systems, and synchronized show control.

> 📖 **For developers**: See [DEV.md](DEV.md) for build instructions, architecture, and development guide.

---

## 🎯 Key Features

- **📡 Wireless Distribution**: ESP-NOW mesh network for low-latency, reliable communication
- **🎬 Media Synchronization**: Media index and position tracking via SysEx
- **⏱️ Sub-millisecond Accuracy**: Mesh-synchronized clocks with latency compensation
- **💡 DALI Light Control**: Control DALI lights via Hasseb DALI Master USB
- **💾 Persistent Configuration**: Receiver layer assignments stored in EEPROM
- **🖥️ GUI Management**: Python-based bridge with real-time monitoring
- **🔄 Auto-Recovery**: Automatic reconnection handling and connection timeout management
- **🎵 Native USB MIDI**: No external MIDI hardware required (ESP32-S3 built-in USB)
- **🔌 Hot-Plug Support**: Graceful handling of device disconnect/reconnect scenarios

---

## 📋 System Overview

```
Millumin (OSC)  →  Bridge (Python/GUI)  →  Sender Nowde (USB MIDI + ESP-NOW)
                                                        ↓
                                         ┌──────────────┴────────────────┐
                                         ↓                               ↓
                              Receiver Nowde 1                 Receiver Nowde 2
                              (MIDI Output)                    (MIDI Output)
                              Layer: "player1"                 Layer: "player2"
```

### Components

1. **Millumin** - Video playback software (OSC sender)
2. **Bridge** - Python application with GUI (OSC → USB MIDI via SysEx)
3. **Sender Nowde** - ESP32-S3 device (USB MIDI → ESP-NOW mesh broadcaster)
4. **Receiver Nowde(s)** - ESP32-S3 device(s) (ESP-NOW → MIDI output)

---

## ⚡ Quick Start

### Hardware Requirements

**Board**: ESP32-S3 DevKit C-1 (one for sender + one or more for receivers)

- **USB Port (Native)**: Used for USB MIDI communication with Bridge
- **USB Port (UART)**: Used for flashing firmware and serial debugging

### Installation

1. **Download the latest Bridge release** from [Releases](https://github.com/Hemisphere-Project/MillluBridge/releases)
2. **Flash Nowde firmware** to your ESP32-S3 devices (see [DEV.md](DEV.md) for instructions)
3. **Connect Sender Nowde** via Native USB port to your computer
4. **Launch Bridge** application

---

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

---

## 🖥️ Understanding the MilluBridge Display

| Section | What it shows |
|---------|---------------|
| **OSC Status** | Green checkmark = receiving OSC from Millumin |
| **Millumin Layers** | Video layers with playback state, media name, position |
| **MilluBridge Lights** | DALI light channels with values and device status |
| **Local Nowde** | USB-connected Nowde device status and firmware version |
| **Dali Master** | Hasseb DALI USB device connection status |
| **Remote Nowdes** | ESP-NOW mesh network devices and their assigned layers |

### Assigning Layers to Remote Nowdes

1. Connect Sender Nowde via Native USB port
2. Wait for "Nowde HELLO received" message
3. Wait for receivers to appear in "Remote Nowdes" table
4. Click on each receiver's Layer button
5. Select or type a layer name (e.g., "player1")
6. Click Apply

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

---

## 🐛 Troubleshooting

### MIDI device not found
- Ensure your MIDI device (Nowde) is connected via Native USB port (not UART)
- Check that the device name starts with "Nowde"
- Try reconnecting the USB cable
- Make sure the USB cable supports data transfer (not just power)

### OSC not receiving
- Verify Millumin is sending OSC feedback (Device Manager > OSC)
- Check the OSC address and port match in both applications
- Ensure firewall allows UDP traffic on the configured port

### Receivers not appearing
- Check that receivers are powered on
- Verify sender Nowde is connected and showing as connected
- Wait a few seconds for ESP-NOW mesh discovery

### DALI lights not responding
- Check DALI Master USB is connected (green indicator)
- Verify DALI wiring and power supply
- Click on a channel to identify (blink) and confirm communication

---

## 🔧 Technical Specs

| Feature | Specification |
|---------|--------------|
| **Latency** | 10-50ms typical (including network, processing, compensation) |
| **Update Rate** | 1-60 Hz configurable (default 10 Hz) |
| **Max Receivers** | 10 per sender |
| **Clock Sync** | < 10ms drift over 1 hour |
| **Packet Loss** | < 1% on stable network |
| **Range** | 10-100m (line of sight, varies by environment) |
| **MIDI Protocol** | USB MIDI (class-compliant), SysEx with 7-bit encoding |

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

---

## 📞 Support

For issues or questions:
- Check the troubleshooting section above
- Review the [DEV.md](DEV.md) for technical details
- Open an issue on GitHub

---

**Built with ❤️ for the AV production community**
