# Getting Started with MilluBridge

Complete setup guide from hardware to first synchronized playback.

---

## Hardware Setup

### What You Need

- **1× ESP32-S3 DevKit C-1** - Sender (connected to computer running Bridge)
- **1+ ESP32-S3 DevKit C-1** - Receiver(s) (distributed at installation locations)
- **USB cables** (data + power for each device)
- **Computer** running macOS, Windows, or Linux
- **Millumin** installation (trial or licensed)

### ESP32-S3 Port Identification

Each ESP32-S3 DevKit C-1 has **TWO USB ports**:

1. **UART Port** (labeled "USB"): For flashing firmware and serial debugging
2. **Native USB Port** (labeled "UART"): For USB MIDI communication

> 💡 **Important**: You'll use **UART port** for flashing, then switch to **Native USB port** for operation.

---

## Software Installation

### 1. Install PlatformIO

**Option A: VS Code Extension** (Recommended)
1. Install [Visual Studio Code](https://code.visualstudio.com/)
2. Open Extensions (Cmd+Shift+X / Ctrl+Shift+X)
3. Search for "PlatformIO IDE"
4. Click Install

**Option B: Command Line**
```bash
pip install platformio
```

### 2. Install Python (if not installed)

**macOS**:
```bash
brew install python@3.11
```

**Windows**:
Download from [python.org](https://www.python.org/downloads/)

**Linux**:
```bash
sudo apt install python3.11 python3-pip python3-venv
```

### 3. Clone or Download Project

```bash
git clone https://github.com/Hemisphere-Project/MilluBridge.git
cd MilluBridge
```

---

## Firmware Installation

### Flash Each ESP32 Device

**Repeat for each device (Sender + all Receivers):**

1. **Connect ESP32** via **UART port**

2. **Open Terminal** in `Nowde` folder:
   ```bash
   cd Nowde
   ```

3. **Compile and Upload**:
   ```bash
   pio run --target upload
   ```

4. **Wait for completion** (~2-3 minutes first time)

5. **Monitor Serial Output** (optional, for verification):
   ```bash
   pio device monitor
   ```

6. **Verify Boot Messages**:
   ```
   [SETUP] Starting Nowde v1.0
   [WIFI] MAC Address: AA:BB:CC:DD:EE:FF
   [ESP-NOW] Initialized
   [MESH CLOCK] Initialized
   [SETUP] Complete - Ready
   ```

7. **Disconnect and Label** device (e.g., "Sender", "Receiver-1", etc.)

> 💡 **Tip**: Use label maker or tape to mark each device's role

---

## Bridge Installation

### 1. Create Virtual Environment

```bash
cd Bridge
python3 -m venv .venv
```

### 2. Activate Virtual Environment

**macOS/Linux**:
```bash
source .venv/bin/activate
```

**Windows**:
```cmd
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Expected packages:
- `dearpygui` - GUI framework
- `python-osc` - OSC client/server
- `python-rtmidi` - MIDI I/O

---

## Millumin Configuration

### Enable OSC Feedback

1. **Open Millumin**
2. **Window** → **Device Manager**
3. Select **OSC** tab
4. **Enable** "Send feedback to remote clients"
5. **Add Target**:
   - Address: `127.0.0.1`
   - Port: `8000`
6. **Click** "+" to add
7. **Close** Device Manager

> ⚠️ **Important**: Without OSC feedback enabled, MilluBridge won't receive media events!

---

## First Launch

### 1. Connect Sender Nowde

1. **Disconnect** UART cable from Sender
2. **Connect** Sender's **Native USB port** to computer
3. Device should appear as "Nowde" in MIDI devices

### 2. Start Bridge

```bash
cd Bridge
source .venv/bin/activate  # If not already activated
python src/main.py
```

### 3. Verify Connection

**Bridge GUI should show**:
- ✅ **OSC Status**: `[OK] Listening on 127.0.0.1:8000`
- ✅ **USB Status**: `[OK] Nowde` (device name)

**Sender Serial Output**:
```
[SYSEX] Command: 0x01 | Sender mode: NO | Receiver mode: NO
=== SENDER MODE ACTIVATED ===
```

### 4. Power On Receivers

1. **Connect** each Receiver via USB power (any port)
2. **Wait 5-10 seconds** for boot
3. **Watch** "Remote Nowdes" table in Bridge

**Expected**:
- Each receiver appears with unique MAC address
- **State** shows "ACTIVE" (green)
- **Version** shows "1.0"
- **Layer** shows "-" (not assigned)

> 💡 **Troubleshooting**: If receivers don't appear, check [Troubleshooting Guide](TROUBLESHOOTING.md#receivers-not-appearing)

---

## Layer Assignment

### Assign Layers to Receivers

For each receiver:

1. **Click** on **Layer button** in Remote Nowdes table
2. **Modal dialog** appears
3. **Option A**: Select from Millumin layers list
4. **Option B**: Type custom layer name
5. **Click** "Apply"

**Confirmation**:
- Receiver LED may blink briefly
- Serial output: `=== RECEIVER LAYER CHANGED ===`
- Layer button now shows assigned layer name
- ✅ **Saved to EEPROM** (survives power loss!)

### Layer Naming Convention

**Recommended format**:
- Millumin default layers: `player1`, `player2`, etc.
- Custom: `main`, `backup`, `video1`, `audio1`

**Rules**:
- Max 16 characters
- Case-sensitive
- No special characters recommended

---

## Media File Naming

### Configure Media Index

For MilluBridge to send media index via CC#100, rename files:

**Format**: `NNN_filename.ext`

**Examples**:
- `001_intro.mp4` → Media Index 1
- `002_main_content.mov` → Media Index 2
- `127_finale.mp4` → Media Index 127

**Rules**:
- **1-3 digits** at start of filename
- **Underscore separator**
- Index range: **1-127** (0 reserved for stop)

**Without Index**:
- Files without index prefix → Index 0 (stop state)
- MTC still sent, but no CC#100 media identification

---

## First Test

### 1. Create Test Media in Millumin

1. **Drag** video file into "player1" layer
2. **Rename** file: `001_test_video.mp4`
3. **Verify** duration is visible

### 2. Play Media

1. **Click** play in Millumin timeline
2. **Watch** Bridge GUI:
   - "Millumin Layers" table shows `player1` playing
   - "Nowde Logs": Media Sync messages

### 3. Verify MIDI Output

Connect MIDI monitor to receiver:

**Expected MIDI Output**:
- **CC#100 = 1** (media index from filename `001_`)
- **MTC Quarter Frames** updating at 30fps
- **Position** advances with playback

**Stop**:
- Millumin stops media
- **CC#100 = 0** (stop)
- MTC stops

---

## Sync Settings Configuration

### Adjust Performance

**Bridge GUI → Media Sync Settings**:

| Setting | Default | Purpose |
|---------|---------|---------|
| **Throttle (Hz)** | 10 Hz | Update frequency (lower = less network traffic) |
| **MTC Framerate** | 30 fps | Match your video framerate |
| **Freewheel Timeout** | 3.0s | Continue MTC during brief interruptions |
| **Desync Threshold** | 200ms | Max clock delta before packet rejection |

**When to Adjust**:
- **High latency** → Increase desync threshold
- **24fps video** → Change MTC framerate to 24
- **Network congestion** → Decrease throttle rate
- **Fast sync needed** → Increase throttle rate (max 60 Hz)

---

## Verification Checklist

After setup, verify:

- [ ] All receivers appear in Remote Nowdes table
- [ ] All receivers show ACTIVE status (green)
- [ ] Layer assignments are correct
- [ ] Media files have index prefixes (001_, 002_, etc.)
- [ ] Millumin OSC feedback is enabled
- [ ] Playing media sends MIDI to receivers
- [ ] Stopping media sends CC#100 = 0
- [ ] Receivers survive power cycle (layer remembered)

---

## Next Steps

- **[User Guide](USER_GUIDE.md)** - Learn all features
- **[Architecture](ARCHITECTURE.md)** - Understand system design
- **[Troubleshooting](TROUBLESHOOTING.md)** - Fix common issues
- **[Developer Guide](DEVELOPER_GUIDE.md)** - Customize and extend

---

## Quick Reference

### Start Bridge
```bash
cd Bridge
source .venv/bin/activate
python src/main.py
```

### Monitor Nowde Serial
```bash
cd Nowde
pio device monitor
```

### Reflash Firmware
```bash
cd Nowde
pio run --target upload
```

### Default Ports
- **OSC**: 127.0.0.1:8000
- **Serial**: 115200 baud
- **MIDI**: Channel 1
