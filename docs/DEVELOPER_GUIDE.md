# Developer Guide

API reference, customization, and development information for MilluBridge.

---

## Development Setup

### Prerequisites

- Python 3.8+
- PlatformIO
- Git
- Text editor (VS Code recommended)

### Clone and Setup

```bash
git clone https://github.com/Hemisphere-Project/MilluBridge.git
cd MilluBridge

# Bridge setup
cd Bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Nowde setup
cd ../Nowde
pio lib install  # Install dependencies
```

---

## Project Structure

```
MilluBridge/
├── Bridge/                    # Python application
│   ├── src/
│   │   ├── main.py           # Main application + MediaSyncManager
│   │   ├── osc/
│   │   │   └── server.py     # OSC server wrapper
│   │   └── midi/
│   │       ├── input_manager.py    # MIDI input + SysEx parser
│   │       └── output_manager.py   # MIDI output + SysEx builder
│   ├── requirements.txt
│   └── setup.py
│
└── Nowde/                     # ESP32 firmware
    ├── src/
    │   └── main.cpp          # Complete firmware
    ├── platformio.ini        # PlatformIO config
    └── lib/                  # Dependencies (ESPNowMeshClock)
```

---

## Bridge (Python) API

### MediaSyncManager Class

**Location**: `Bridge/src/main.py`

**Purpose**: Manages media state, throttling, and SysEx generation

#### Methods

```python
class MediaSyncManager:
    def __init__(self, output_manager, throttle_interval=0.1):
        """
        Args:
            output_manager: OutputManager instance
            throttle_interval: Update interval in seconds (default 0.1 = 10Hz)
        """
    
    def parse_media_index(self, filename):
        """
        Extract media index from filename.
        
        Args:
            filename (str): Media filename
        
        Returns:
            int: Media index (1-127), or 0 if no index found
        
        Example:
            parse_media_index("001_video.mp4")  # Returns 1
            parse_media_index("127_finale.mov") # Returns 127
            parse_media_index("no_index.mp4")   # Returns 0
        """
    
    def update_layer(self, layer_name, filename, position, duration, state):
        """
        Update layer state and send MIDI if needed.
        
        Args:
            layer_name (str): Millumin layer name
            filename (str): Media filename
            position (float): Position in seconds
            duration (float): Total duration in seconds
            state (str): "playing" or "stopped"
        
        Behavior:
            - Parses media index from filename
            - Throttles updates based on interval
            - Sends burst on stop (5 messages)
            - Change detection for CC#100
        """
    
    def set_throttle_interval(self, interval):
        """
        Update throttle interval dynamically.
        
        Args:
            interval (float): New interval in seconds (min 0.01)
        """
```

### OutputManager Class

**Location**: `Bridge/src/midi/output_manager.py`

#### SysEx Commands

```python
class OutputManager:
    # SysEx Constants
    SYSEX_MANUFACTURER_ID = 0x7D
    SYSEX_CMD_BRIDGE_CONNECTED = 0x01
    SYSEX_CMD_SUBSCRIBE_LAYER = 0x02
    SYSEX_CMD_CHANGE_RECEIVER_LAYER = 0x04
    SYSEX_CMD_MEDIA_SYNC = 0x05
    
    def send_bridge_connected(self):
        """
        Activate sender mode.
        
        Returns:
            tuple: (success: bool, formatted_message: str)
        
        SysEx: F0 7D 01 F7
        """
    
    def send_subscribe_layer(self, layer_name):
        """
        Set receiver layer (direct USB to receiver).
        
        Args:
            layer_name (str): Layer name (max 16 chars)
        
        Returns:
            tuple: (success: bool, formatted_message: str)
        
        SysEx: F0 7D 02 [layer...] F7
        """
    
    def send_change_receiver_layer(self, mac_address, layer_name):
        """
        Change specific receiver's layer via sender.
        
        Args:
            mac_address (str): MAC address "AA:BB:CC:DD:EE:FF"
            layer_name (str): New layer name (max 16 chars)
        
        Returns:
            tuple: (success: bool, formatted_message: str)
        
        SysEx: F0 7D 04 [MAC(6)] [layer(16)] F7
        """
    
    def send_media_sync(self, layer_name, media_index, position_ms, state):
        """
        Send media synchronization data.
        
        Args:
            layer_name (str): Target layer (max 16 chars)
            media_index (int): Media index 0-127
            position_ms (int): Position in milliseconds
            state (str): "playing" or "stopped"
        
        Returns:
            tuple: (success: bool, formatted_message: str)
        
        SysEx: F0 7D 05 [layer(16)] [index(1)] [pos(4)] [state(1)] F7
        Position encoded as big-endian uint32
        """
```

### InputManager Class

**Location**: `Bridge/src/midi/input_manager.py`

**Purpose**: Parses incoming SysEx messages

```python
class InputManager:
    def __init__(self, sysex_callback=None):
        """
        Args:
            sysex_callback: Function called with (msg_type, data)
        """
    
    # Callback receives:
    # - msg_type = 'receiver_table' → data = list of {mac, name, version, layer}
    # - msg_type = 'sysex_received' → data = formatted SysEx string
```

---

## Nowde (ESP32) API

### Core Functions

**Location**: `Nowde/src/main.cpp`

#### EEPROM Functions

```cpp
void saveLayerToEEPROM(const char* layer) {
  // Save layer to ESP32 NVS
  // Namespace: "nowde"
  // Key: "layer"
}

String loadLayerFromEEPROM() {
  // Load saved layer
  // Returns: Layer name or "-" if none
}
```

#### ESP-NOW Functions

```cpp
void sendReceiverInfo() {
  // Broadcast receiver info to all senders
  // Sent every 1 second + random offset
}

void sendSenderBeacon() {
  // Broadcast sender presence
  // Sent every 1 second
}
```

#### MIDI Output Functions

```cpp
void sendMIDICC100(uint8_t value) {
  // Send CC#100 on channel 1
  // value: 0 = stop, 1-127 = media index
}

void sendMIDITimeCode(uint32_t positionMs) {
  // Send MTC quarter-frames
  // Encodes position as HH:MM:SS:FF @ 30fps
}
```

### Data Structures

```cpp
// Receiver entry in sender table
struct ReceiverEntry {
  uint8_t mac[6];                   // MAC address
  char layer[MAX_LAYER_LENGTH];     // Subscribed layer (16 chars)
  char version[MAX_VERSION_LENGTH]; // Firmware version (8 chars)
  unsigned long lastSeen;           // millis() last contact
  bool active;                      // Ever registered
  bool connected;                   // Currently responding
};

// Media sync packet (ESP-NOW)
struct MediaSyncPacket {
  uint8_t type;              // ESPNOW_MSG_MEDIA_SYNC (0x03)
  char layer[16];            // Target layer
  uint8_t mediaIndex;        // 0-127
  uint32_t positionMs;       // Position in milliseconds
  uint8_t state;             // 0=stopped, 1=playing
  uint32_t meshTimestamp;    // Mesh clock timestamp
} __attribute__((packed));
```

### Configuration Constants

```cpp
#define NOWDE_VERSION "1.0"
#define MAX_LAYER_LENGTH 16
#define RECEIVER_TIMEOUT_MS 5000        // Receiver considered missing
#define SENDER_TIMEOUT_MS 5000          // Sender considered missing
#define RECEIVER_BEACON_INTERVAL_MS 1000
#define SENDER_BEACON_INTERVAL_MS 1000
#define BRIDGE_REPORT_INTERVAL_MS 500   // Table report frequency

// Media sync (receiver)
const uint8_t MTC_FRAMERATE = 30;
const uint32_t FREEWHEEL_TIMEOUT_MS = 3000;
const uint32_t CLOCK_DESYNC_THRESHOLD_MS = 200;
```

---

## Customization Examples

### Example 1: Change MTC Framerate

**File**: `Nowde/src/main.cpp`

```cpp
// Change from 30fps to 24fps
const uint8_t MTC_FRAMERATE = 24;

// Update framerate code in sendMIDITimeCode():
uint8_t framerateCode = 0;  // 00=24fps, 01=25fps, 10=30drop, 11=30
```

### Example 2: Add Custom SysEx Command

**Bridge** (`output_manager.py`):
```python
SYSEX_CMD_CUSTOM = 0x06

def send_custom_command(self, data):
    message = [self.SYSEX_START, self.SYSEX_MANUFACTURER_ID,
               self.SYSEX_CMD_CUSTOM] + list(data) + [self.SYSEX_END]
    self.midi_out.send_message(message)
    return (True, self.format_sysex_message(message))
```

**Nowde** (`main.cpp`):
```cpp
#define SYSEX_CMD_CUSTOM 0x06

// In handleSysExMessage():
case SYSEX_CMD_CUSTOM:
  // Handle custom command
  break;
```

### Example 3: Increase Max Receivers

**File**: `Nowde/src/main.cpp`

```cpp
// Change from 10 to 20
#define MAX_RECEIVERS 20

// Note: Increases memory usage ~31 bytes per receiver
```

### Example 4: Custom Throttle Logic

**File**: `Bridge/src/main.py`

```python
class MediaSyncManager:
    def update_layer(self, layer_name, filename, position, duration, state):
        # ... existing code ...
        
        # Custom: Always send on position % 1000ms == 0 (every second mark)
        if int(position) % 1 == 0:  # Every 1 second
            should_send = True
        
        # ... rest of method ...
```

---

## Testing

### Unit Tests (Bridge)

```bash
cd Bridge
python test_sysex_logging.py   # Test SysEx parsing
python test_sysex_send.py      # Test SysEx generation
```

### Serial Monitor (Nowde)

```bash
cd Nowde
pio device monitor
```

**Useful debug output**:
- `[SYSEX]` - SysEx command received
- `[ESP-NOW TX/RX]` - Network messages
- `[MIDI TX]` - MIDI output
- `[MEDIA SYNC]` - Sync state changes
- `[EEPROM]` - Persistence operations

### Manual Testing

See `TROUBLESHOOTING.md` for test procedures.

---

## Building and Deployment

### Build Bridge Executable (Optional)

**macOS/Linux**:
```bash
cd Bridge
pip install pyinstaller
pyinstaller --onefile --windowed src/main.py
# Output: dist/main
```

**Windows**:
```cmd
cd Bridge
pip install pyinstaller
pyinstaller --onefile --windowed src\main.py
REM Output: dist\main.exe
```

### Flash Multiple Nowdes

**Batch script** (macOS/Linux):
```bash
#!/bin/bash
cd Nowde
for port in /dev/cu.usbserial*; do
  echo "Flashing $port..."
  pio run --target upload --upload-port $port
done
```

---

## Debugging

### Enable Verbose Logging (Nowde)

**Current**: Already verbose, logs every 10th packet to reduce spam

**To see ALL packets**:
Comment out throttling checks in `main.cpp`:
```cpp
// if (syncCount % 10 == 0 && sentCount > 0) {
  DEBUG_SERIAL.printf("[ESP-NOW TX] Media Sync #%d...", syncCount);
// }
```

### Debug Bridge MIDI

Add print statements in `update_layer()`:
```python
def update_layer(self, ...):
    print(f"DEBUG: layer={layer_name}, index={media_index}, pos={position}, state={state}")
    # ... rest of method ...
```

### Monitor OSC Traffic

```bash
# macOS
nc -u -l 8000

# Or use dedicated OSC monitor app
```

---

## Contributing

### Code Style

**Python**:
- PEP 8 compliant
- 4-space indentation
- Type hints preferred

**C++**:
- K&R brace style
- 2-space indentation  
- Descriptive variable names

### Pull Request Process

1. Fork repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Test thoroughly (Bridge + Nowde)
4. Commit with clear messages
5. Push and create PR

### Reporting Issues

Include:
- Bridge OS and Python version
- Nowde serial output
- Steps to reproduce
- Expected vs actual behavior

---

## API Version Compatibility

| Bridge Version | Nowde Version | Compatible |
|----------------|---------------|------------|
| 1.0 | 1.0 | ✅ Yes |

Future versions will maintain backward compatibility where possible.

---

## Advanced Topics

### Custom MIDI Channels

**Current**: Hardcoded to channel 1

**To change** (`Nowde/src/main.cpp`):
```cpp
void sendMIDICC100(uint8_t value) {
  MIDI.sendControlChange(100, value, 2);  // Channel 2
}
```

### Multiple Senders

Not currently supported. Future enhancement.

**Workaround**: Use separate Bridge instances on different ports.

### Encrypt ESP-NOW

```cpp
// In setup(), after esp_now_init():
esp_now_peer_info_t peerInfo = {};
memcpy(peerInfo.peer_addr, receiverMac, 6);
peerInfo.encrypt = true;
memcpy(peerInfo.lmk, "YOUR_16_BYTE_KEY", 16);
esp_now_add_peer(&peerInfo);
```

**Note**: Both sender and receiver must use same key.

---

## Performance Profiling

### Bridge CPU Usage

**Monitor**:
```python
import psutil
process = psutil.Process()
print(f"CPU: {process.cpu_percent()}%")
print(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
```

**Typical**:
- Idle: 1-2% CPU
- Active (10 Hz): 3-5% CPU
- Memory: 50-100 MB

### Nowde Performance

**Monitor free heap**:
```cpp
void loop() {
  static unsigned long lastHeapReport = 0;
  if (millis() - lastHeapReport > 10000) {
    DEBUG_SERIAL.printf("[HEAP] Free: %d bytes\n", ESP.getFreeHeap());
    lastHeapReport = millis();
  }
}
```

---

## Future Enhancements

Planned features:
- Web-based Bridge interface
- Cloud configuration storage
- Bi-directional sync feedback
- Multi-sender support
- Advanced filtering/routing
- MQTT integration
- RESTful API

See GitHub Issues for full roadmap.
