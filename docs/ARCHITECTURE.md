# MilluBridge Architecture

System design, protocols, and technical implementation details.

---

## System Architecture

### High-Level Overview

```
┌─────────────────┐
│    Millumin     │
│  (OSC Server)   │
└────────┬────────┘
         │ OSC Messages
         │ /millumin/layer:X/mediaStarted
         │ /millumin/layer:X/media/time
         │ /millumin/layer:X/mediaStopped
         ↓
┌─────────────────┐
│     Bridge      │
│  (Python GUI)   │
│                 │
│ MediaSync       │
│ Manager         │
└────────┬────────┘
         │ USB MIDI (SysEx)
         │ F0 7D 05 [layer][index][pos][state] F7
         ↓
┌─────────────────┐
│  Sender Nowde   │
│   (ESP32-S3)    │
│                 │
│ + Mesh Clock    │
│ + ESP-NOW       │
└────────┬────────┘
         │ ESP-NOW Broadcast
         │ MediaSyncPacket {layer, index, pos, state, timestamp}
         ↓
┌──────────────────────────────────┐
│                                  │
↓                                  ↓
┌─────────────────┐      ┌─────────────────┐
│ Receiver Nowde  │      │ Receiver Nowde  │
│   (ESP32-S3)    │      │   (ESP32-S3)    │
│                 │      │                 │
│ Layer: "player1"│      │ Layer: "player2"│
└────────┬────────┘      └────────┬────────┘
         │                        │
         │ USB MIDI               │ USB MIDI
         │ CC#100 + MTC           │ CC#100 + MTC
         ↓                        ↓
   [Connected                [Connected
    MIDI Device]              MIDI Device]
```

---

## Data Flow

### 1. Media Playback Event Flow

```
1. User plays media in Millumin
   ↓
2. Millumin sends OSC: /millumin/layer:player1/mediaStarted
   Data: (index, "001_video.mp4", duration)
   ↓
3. Bridge parses filename → Media Index = 1
   ↓
4. MediaSyncManager throttles updates (10 Hz default)
   ↓
5. Bridge sends SysEx 0x05 via USB MIDI
   Packet: [layer="player1", index=1, position=0ms, state=playing]
   ↓
6. Sender Nowde receives SysEx
   ↓
7. Sender adds mesh timestamp: meshClock.meshMillis()
   ↓
8. Sender broadcasts ESP-NOW to all receivers on "player1"
   ↓
9. Receiver validates clock (delta < 200ms)
   ↓
10. Receiver compensates latency:
    position += (currentMeshTime - packetTimestamp)
    ↓
11. Receiver outputs MIDI:
    - CC#100 = 1 (media index)
    - MTC quarter-frames (position sync)
```

### 2. Position Update Flow (During Playback)

```
Every 100ms (10 Hz default):

1. Millumin sends OSC: /millumin/layer:player1/media/time
   Data: (position, duration)
   ↓
2. MediaSyncManager checks throttle
   ↓
3. If interval elapsed → Send SysEx 0x05
   ↓
4. Same flow as above (steps 6-11)
   ↓
5. Receiver updates MTC with compensated position
```

### 3. Stop Event Flow

```
1. User stops media in Millumin
   ↓
2. Millumin sends OSC: /millumin/layer:player1/mediaStopped
   ↓
3. MediaSyncManager sends BURST of 5 stop messages
   (Ensures reliable delivery even with packet loss)
   ↓
4. Each SysEx 0x05 with state=stopped, index=0
   ↓
5. Receiver receives (at least one)
   ↓
6. Receiver outputs:
   - CC#100 = 0 (stop)
   - MTC stops
```

---

## Communication Protocols

### OSC Protocol (Millumin → Bridge)

**Messages Parsed**:

| Address | Arguments | Purpose |
|---------|-----------|---------|
| `/millumin/layer:X/mediaStarted` | (index, filename, duration) | Media start notification |
| `/millumin/layer:X/media/time` | (position, duration) | Position update |
| `/millumin/layer:X/mediaStopped` | (index, filename, duration) | Media stop notification |

**Example**:
```
/millumin/layer:player1/mediaStarted: (0, "001_intro.mp4", 120.5)
/millumin/layer:player1/media/time: (5.32, 120.5)
/millumin/layer:player1/mediaStopped: (0, "001_intro.mp4", 120.5)
```

### SysEx Protocol (Bridge ↔ Nowde)

**Manufacturer ID**: `0x7D` (Educational/Development use)

**Commands**:

| CMD | Name | Direction | Format | Purpose |
|-----|------|-----------|--------|---------|
| `0x01` | Bridge Connected | Bridge → Sender | `F0 7D 01 F7` | Activate sender mode |
| `0x02` | Subscribe Layer | Bridge → Receiver | `F0 7D 02 [layer(16)] F7` | Set receiver layer |
| `0x03` | Receiver Table | Sender → Bridge | `F0 7D 03 [count] [entries...] F7` | Report all receivers |
| `0x04` | Change Receiver Layer | Bridge → Sender | `F0 7D 04 [MAC(6)] [layer(16)] F7` | Update specific receiver |
| `0x05` | Media Sync | Bridge → Sender | `F0 7D 05 [layer(16)] [index(1)] [pos(4)] [state(1)] F7` | Sync media state |

**SysEx 0x05 Details** (26 bytes):
```
F0                    # SysEx start
7D                    # Manufacturer ID
05                    # Command: Media Sync
[16 bytes]            # Layer name (ASCII, null-padded)
[1 byte]              # Media index (0-127, 0=stop)
[4 bytes]             # Position in milliseconds (big-endian uint32)
[1 byte]              # State (0=stopped, 1=playing)
F7                    # SysEx end
```

### ESP-NOW Protocol (Sender ↔ Receiver)

**Message Types**:

| Type | Name | Size | Purpose |
|------|------|------|---------|
| `0x01` | Sender Beacon | 1 byte | Announce sender presence |
| `0x02` | Receiver Info | 25 bytes | Report layer subscription |
| `0x03` | Media Sync Packet | 27 bytes | Distribute media state |

**MediaSyncPacket Structure** (27 bytes):
```c
struct MediaSyncPacket {
  uint8_t type;              // 0x03
  char layer[16];            // Target layer name
  uint8_t mediaIndex;        // 0-127
  uint32_t positionMs;       // Position in milliseconds
  uint8_t state;             // 0=stopped, 1=playing
  uint32_t meshTimestamp;    // Mesh clock timestamp (for latency compensation)
} __attribute__((packed));
```

### MIDI Protocol (Receiver → Connected Device)

**Output Messages**:

| Message | Channel | Purpose | Value Range |
|---------|---------|---------|-------------|
| **CC#100** | 1 | Media Index | 0 (stop) / 1-127 (media index) |
| **MTC Quarter Frame** | - | Position Sync | 8 messages per frame @ 30fps |

**MTC Format**:
```
F1 0n dddd    # Quarter Frame message
n = piece number (0-7)
dddd = data nibble

Pieces encode: frames, seconds, minutes, hours + framerate
Framerate: 30fps non-drop (code 11b)
```

---

## Timing and Synchronization

### Mesh Clock Synchronization

**Library**: ESPNowMeshClock

**Configuration**:
```cpp
ESPNowMeshClock meshClock(
  1000,    // Sync interval: 1000ms
  0.25,    // Skew alpha: 0.25
  10000,   // Large step threshold: 10ms
  5000,    // Timeout: 5s
  10       // Random variation: 10%
);
```

**Operation**:
1. Devices periodically exchange timestamps
2. Each device calculates offset and skew
3. `meshClock.meshMillis()` returns synchronized time
4. Typical drift: < 10ms over 1 hour

### Latency Compensation

**Process**:
1. Sender adds `meshTimestamp` to MediaSyncPacket
2. Receiver calculates delta: `currentMeshTime - packetTimestamp`
3. Receiver adjusts position: `compensatedPos = position + delta`
4. Result: Accounts for network + processing delay

**Example**:
```
Packet position: 5000ms
Packet timestamp: 1234567ms (mesh time)
Current mesh time: 1234592ms
Delta: 25ms

Compensated position: 5000ms + 25ms = 5025ms
```

### Clock Validation

**Desync Detection**:
- Threshold: 200ms (configurable)
- If `abs(delta) > threshold` → Packet discarded
- Logged as clock desync warning
- Prevents corrupted playback from bad packets

**Freewheel Mode**:
- Triggered after 3s without sync (configurable)
- Receiver continues MTC updates locally
- Position calculated: `lastPos + (now - lastSyncTime)`
- Auto-exits when new sync received

---

## State Management

### Sender Nowde States

```
┌─────────────┐
│  BOOT/IDLE  │
└──────┬──────┘
       │
       │ Receives SysEx 0x01 (Bridge Connected)
       ↓
┌─────────────┐
│ SENDER MODE │
│             │
│ - Broadcasts beacons
│ - Maintains receiver table
│ - Forwards SysEx to ESP-NOW
└─────────────┘
```

### Receiver Nowde States

```
┌─────────────┐
│  BOOT/IDLE  │
└──────┬──────┘
       │
       │ Load layer from EEPROM (if saved)
       ↓
┌─────────────┐
│ RECEIVER    │
│ MODE        │
│             │
│ - Sends beacons
│ - Listens for media sync
│ - Outputs MIDI
└──────┬──────┘
       │
       ├─→ PLAYING: CC#100 = index, MTC updating
       ├─→ STOPPED: CC#100 = 0, MTC stopped
       └─→ FREEWHEEL: MTC continues locally
```

### MediaSyncManager State (Bridge)

**Per-Layer State**:
```python
{
  'index': 1,                    # Current media index
  'position': 5320.5,            # Position (ms)
  'state': 'playing',            # playing/stopped
  'last_sent_time': 1234567.89,  # For throttling
  'last_sent_index': 1,          # For change detection
  'stop_burst_remaining': 0      # Stop burst counter
}
```

---

## Network Architecture

### ESP-NOW Mesh

**Characteristics**:
- **Protocol**: ESP-NOW (Espressif proprietary)
- **Frequency**: 2.4 GHz WiFi channels
- **Encryption**: None (can be enabled)
- **Max Payload**: 250 bytes
- **Latency**: 1-10ms typical
- **Range**: 10-100m (environment dependent)

**Advantages vs WiFi**:
- Lower latency
- No router required
- Direct peer-to-peer
- More reliable for real-time

**Topology**:
```
     [Sender]
        ↓
    Broadcast
    (FF:FF:FF:FF:FF:FF)
        ↓
    ┌───┴───┬───────┐
    ↓       ↓       ↓
 [Rcv-1] [Rcv-2] [Rcv-3]
```

### Peer Management

**Auto-discovery**:
1. Sender broadcasts beacons (1s interval)
2. Receivers hear beacons, add sender to table
3. Receivers broadcast info (layer, version)
4. Sender receives info, adds receiver to table
5. Sender reports table to Bridge via SysEx 0x03

**Connection Monitoring**:
- Timeout: 5 seconds
- Missing receivers marked as "MISSING" (not removed)
- Can reconnect automatically when back in range

---

## Persistence Layer

### EEPROM Storage (ESP32)

**Namespace**: `"nowde"`

**Stored Data**:
| Key | Type | Purpose |
|-----|------|---------|
| `"layer"` | String | Subscribed layer name |

**Functions**:
```cpp
// Save
preferences.begin("nowde", false);  // RW mode
preferences.putString("layer", "player1");
preferences.end();

// Load
preferences.begin("nowde", true);   // RO mode
String layer = preferences.getString("layer", "-");
preferences.end();
```

**Persistence**:
- ✅ Survives power cycle
- ✅ Survives firmware update (unless flash erased)
- ✅ Survives reboot
- ❌ Lost on flash erase (reflashing with erase)

---

## Performance Characteristics

### Latency Breakdown

| Stage | Typical | Max |
|-------|---------|-----|
| Millumin → Bridge (OSC) | < 1ms | 5ms |
| Bridge Processing | < 1ms | 5ms |
| Bridge → Sender (USB MIDI) | 1-2ms | 10ms |
| Sender Processing | < 1ms | 5ms |
| Sender → Receiver (ESP-NOW) | 1-5ms | 20ms |
| Receiver Processing | < 1ms | 5ms |
| Receiver → MIDI Output | 1-2ms | 10ms |
| **Total** | **10-15ms** | **60ms** |

**Compensation**:
- Latency compensation reduces perceived delay
- Typical compensated latency: 5-10ms

### Throughput

| Metric | Value |
|--------|-------|
| Max update rate | 60 Hz (Bridge throttle) |
| Default rate | 10 Hz (100ms interval) |
| Stop burst | 5 packets ASAP |
| Beacon interval | 1s (sender/receiver) |
| Table report | 500ms (sender → bridge) |

---

## Security Considerations

**Current Implementation**:
- ⚠️ **No encryption** on ESP-NOW
- ⚠️ **No authentication**
- ⚠️ **Open OSC port** (localhost only by default)

**Recommendations for Production**:
1. Enable ESP-NOW encryption
2. Use OSC password authentication
3. Firewall OSC port if exposed
4. Consider WiFi isolation for ESP-NOW devices

---

## Scalability

### Current Limits

| Resource | Limit | Configurable |
|----------|-------|--------------|
| Max receivers per sender | 10 | Yes (`MAX_RECEIVERS`) |
| Max senders per receiver | 10 | Yes (`MAX_SENDERS`) |
| Max layers in Bridge | Unlimited | - |
| Layer name length | 16 chars | No (protocol limit) |
| Media index range | 1-127 | No (MIDI limit) |

### Future Enhancements

Possible improvements:
- Multiple senders per installation
- Receiver multi-layer subscription
- Bi-directional sync feedback
- Cloud-based configuration
- Web-based Bridge interface

---

## Reconnection & Hot-Plug Protocol

### HELLO Handshake

The system implements a robust HELLO handshake protocol to handle all connection scenarios:

**Message Format** (0x20):
```
F0 7D 20 [version(8,encoded)] [uptimeMs(4,encoded)] [bootReason(1)] F7
```

**Triggers**:
1. Sender boot (after 500ms delay for USB enumeration)
2. Sender receives QUERY_CONFIG from Bridge

**Bridge Response**:
1. Sets `sender_initialized = True`
2. Clears stale remote_nowdes table
3. Pushes configuration (RF sim settings)
4. Queries running state

### Connection Scenarios

**Scenario 1: Fresh Sender Boot (Bridge Running)**
```
1. Sender: Boot → delay 500ms → send HELLO
2. Bridge: USB detect → connect → send QUERY_CONFIG
3. Sender: Receive QUERY_CONFIG → send HELLO + CONFIG_STATE
4. Bridge: Receive HELLO → initialize → push config → query state
5. ✅ Fully synchronized
```

**Scenario 2: Bridge Restart (Sender Already Running)**
```
1. Bridge: Start → detect USB device → connect
2. Bridge: Send QUERY_CONFIG
3. Sender: Receive QUERY_CONFIG → send HELLO + CONFIG_STATE
4. Bridge: Receive HELLO → initialize → push config → query state
5. ✅ Fully synchronized
```

**Scenario 3: Sender Disconnect/Reconnect**
```
1. Bridge: Detect disconnect (USB enumeration change)
2. Bridge: Clear sender_initialized flag and remote_nowdes
3. Bridge: Detect reconnect → send QUERY_CONFIG
4. Sender: Receive QUERY_CONFIG → send HELLO + CONFIG_STATE
5. Bridge: Receive HELLO → initialize → push config → query state
6. ✅ Fully synchronized
```

**Scenario 4: Sender Quick Reboot**
```
1. Sender: Reboot → delay 500ms → send HELLO
2. Bridge: May/may not detect USB disconnect (timing dependent)
3. Bridge: Receive HELLO → detect reboot (uptime low)
4. Bridge: Reinitialize → push config → query state
5. ✅ Fully synchronized
```

### State Management

**Bridge State Flags**:
- `sender_initialized`: Set to `True` only after receiving HELLO
- `current_nowde_device`: Current USB device name (or `None`)
- `remote_nowdes`: Dictionary of discovered receivers

**Query Blocking**:
- Running state queries (1Hz thread) only execute when `sender_initialized == True`
- Prevents sending commands before sender is ready
- Avoids race conditions during boot

### 7-bit Encoding

All multi-byte data in SysEx messages uses 7-bit encoding to prevent USB MIDI protocol corruption:

**Encoding Process** (every 7 bytes → 8 bytes):
1. Extract MSBs from 7 data bytes
2. Pack MSBs into first output byte
3. Output 7-bit data bytes (MSB cleared)

**Example**: RUNNING_STATE message
- Uptime: 4 bytes → 5 bytes encoded
- Receiver entry: 35 bytes → 40 bytes encoded
- Version string: 8 bytes → 10 bytes encoded

This ensures no byte with bit 7 set (0x80-0xFF) ever appears as data in USB MIDI packets, preventing confusion with MIDI status bytes.
