# Layer Change Data Flow

## Complete Layer Management Architecture

### 1. Initial Layer Setup (USB SysEx)
```
┌─────────────────────────────────────────────────────────────────┐
│ Initial Setup via USB MIDI                                       │
└─────────────────────────────────────────────────────────────────┘

GUI (Bridge)                    Sender Nowde                 Receiver Nowde
     │                               │                             │
     │  SysEx 0x02 (Subscribe)      │                             │
     │  F0 7D 02 [layer] F7         │                             │
     ├──────────────────────────────>│                             │
     │                               │  Store layer locally        │
     │                               │  Save to EEPROM            │
     │                               │  Enable receiver mode      │
     │                               │                             │
```

### 2. Auto-Start on Boot (EEPROM)
```
┌─────────────────────────────────────────────────────────────────┐
│ Power Cycle - Auto-Start from EEPROM                            │
└─────────────────────────────────────────────────────────────────┘

Receiver Nowde (Boot)
     │
     │ setup()
     ├─ loadLayerFromEEPROM()
     │    │
     │    ├─ Preferences.getString("layer")
     │    │
     │    └─ Returns saved layer (or DEFAULT_RECEIVER_LAYER)
     │
     ├─ If layer exists and not "-":
     │    ├─ Enable receiver mode
     │    ├─ Set subscribedLayer
     │    └─ Start listening to layer
     │
     └─ [Receiver automatically active on boot]
```

### 3. GUI-Based Layer Change (New Feature)
```
┌─────────────────────────────────────────────────────────────────┐
│ Layer Change Flow via GUI                                        │
└─────────────────────────────────────────────────────────────────┘

GUI (Bridge)                    Sender Nowde                 Receiver Nowde
     │                               │                             │
     │ User edits layer              │                             │
     │ in Remote Nowdes table        │                             │
     │                               │                             │
     │  SysEx 0x04 (Change Layer)    │                             │
     │  F0 7D 04 [MAC(6)]            │                             │
     │           [layer(16)] F7      │                             │
     ├──────────────────────────────>│                             │
     │                               │                             │
     │                               │  Extract MAC & layer        │
     │                               │  Find receiver by MAC       │
     │                               │                             │
     │                               │  ESP-NOW SysEx Forward      │
     │                               │  F0 7D 02 [layer] F7        │
     │                               ├────────────────────────────>│
     │                               │                             │
     │                               │                         ┌───┴───┐
     │                               │                         │ Process│
     │                               │                         │ Layer  │
     │                               │                         └───┬───┘
     │                               │                             │
     │                               │                    Update subscribedLayer
     │                               │                    Save to EEPROM
     │                               │                    Broadcast new info
     │                               │                             │
     │                               │  ESP-NOW ReceiverInfo       │
     │                               │<────────────────────────────┤
     │                               │                             │
     │                               │  Build receiver table       │
     │                               │                             │
     │  SysEx 0x03 (Receiver Table)  │                             │
     │  F0 7D 03 [entries...] F7     │                             │
     │<──────────────────────────────┤                             │
     │                               │                             │
     │ Update GUI table              │                             │
     │ Show new layer                │                             │
     │                               │                             │
```

### 4. Receiver Info Broadcast (Periodic Updates)
```
┌─────────────────────────────────────────────────────────────────┐
│ Periodic Receiver Info Broadcast                                 │
└─────────────────────────────────────────────────────────────────┘

All Receivers                   Sender Nowde                 GUI (Bridge)
     │                               │                             │
     │ Every 5 seconds:              │                             │
     │ Broadcast ReceiverInfo        │                             │
     │ via ESP-NOW                   │                             │
     ├──────────────────────────────>│                             │
     │                               │                             │
     │ [MAC | Layer | Version        │                             │
     │  | Connected]                 │                             │
     │                               │                             │
     │                               │  Aggregate all receivers    │
     │                               │  Build table                │
     │                               │                             │
     │                               │  SysEx 0x03 (Table Report)  │
     │                               ├────────────────────────────>│
     │                               │                             │
     │                               │                 Update Remote Nowdes table
     │                               │                 Color: ACTIVE (green)
     │                               │                 or MISSING (dark red)
     │                               │                             │
```

## Key Components

### ESP32 Firmware (Nowde)

#### EEPROM Functions
```cpp
// Save layer to persistent storage
void saveLayerToEEPROM(const char* layer) {
    Preferences prefs;
    prefs.begin("nowde", false);      // Read/write mode
    prefs.putString("layer", layer);   // Save with key "layer"
    prefs.end();
}

// Load layer from persistent storage
String loadLayerFromEEPROM() {
    Preferences prefs;
    prefs.begin("nowde", true);        // Read-only mode
    String layer = prefs.getString("layer", DEFAULT_RECEIVER_LAYER);
    prefs.end();
    return layer;
}
```

#### SysEx Handler
```cpp
void handleSysExMessage(const uint8_t* sysex, uint16_t len) {
    uint8_t cmd = sysex[2];
    
    switch (cmd) {
        case SYSEX_CMD_SUBSCRIBE_LAYER:
            // Extract layer, enable receiver mode
            saveLayerToEEPROM(layer);  // ← Save to EEPROM
            break;
            
        case SYSEX_CMD_CHANGE_RECEIVER_LAYER:
            // Extract MAC and layer
            // Forward to specific receiver via ESP-NOW
            break;
    }
}
```

#### ESP-NOW Data Receiver
```cpp
void onDataRecv(const uint8_t *mac, const uint8_t *data, int len) {
    // Check if it's a SysEx message
    if (data[0] == 0xF0 && data[1] == 0x7D) {
        if (data[2] == SYSEX_CMD_SUBSCRIBE_LAYER) {
            // Process layer change
            saveLayerToEEPROM(layer);  // ← Save to EEPROM
            // Broadcast updated info
        }
    }
}
```

### Python Bridge

#### Output Manager
```python
def send_change_receiver_layer(self, mac_address, layer_name):
    # Convert MAC string to bytes
    mac_bytes = [int(part, 16) for part in mac_address.split(':')]
    
    # Pad layer to 16 bytes
    layer_bytes = (layer_name[:16] + '\x00' * 16)[:16].encode('ascii')
    
    # Build SysEx: F0 7D 04 [MAC(6)] [Layer(16)] F7
    message = ([0xF0, 0x7D, 0x04] + 
               mac_bytes + list(layer_bytes) + [0xF7])
    
    self.midi_out.send_message(message)
```

#### GUI Handler
```python
def on_layer_changed(self, mac_address, new_layer):
    # Validate and trim layer name
    new_layer = new_layer.strip()[:16]
    
    # Send SysEx command
    self.output_manager.send_change_receiver_layer(mac_address, new_layer)
    
    # Log the action
    self.update_osc_log(f"Sent Change Receiver Layer: MAC={mac_address}")
```

## Data Structures

### ReceiverInfo (ESP-NOW Broadcast)
```cpp
struct ReceiverInfo {
    uint8_t mac[6];           // Receiver MAC address
    char layer[16];           // Subscribed layer name
    char version[8];          // Firmware version
    bool connected;           // Connection status
    unsigned long lastSeen;   // Last broadcast timestamp
};
```

### SysEx Message Formats

#### Subscribe Layer (0x02)
```
F0 7D 02 [layer_name...] F7

Example:
F0 7D 02 70 6C 61 79 65 72 32 F7  ← "player2"
```

#### Change Receiver Layer (0x04)
```
F0 7D 04 [MAC(6)] [Layer(16)] F7

Example:
F0 7D 04 AA BB CC DD EE FF 70 6C 61 79 65 72 33 00 ... F7
         └──── MAC ────┘  └───── "player3" + padding ────┘
```

#### Receiver Table Report (0x03)
```
F0 7D 03 [entry1] [entry2] ... F7

Each entry (31 bytes):
- MAC address: 6 bytes
- Layer name: 16 bytes (null-padded)
- Version: 8 bytes (null-padded)
- Status: 1 byte (0x00=inactive, 0x01=active)
```

## State Management

### Receiver States
1. **Inactive**: Never registered or timed out
2. **Active**: Currently broadcasting, responding
3. **Missing**: Previously active but timed out

### GUI Visual Indicators
- **ACTIVE** (Green): Receiver is online and responding
- **MISSING** (Dark Red): Receiver was seen but now timed out

### Persistence Lifecycle
```
Boot → Load EEPROM → Auto-start receiver mode
  ↓
Subscribe command → Save to EEPROM → Enable receiver
  ↓
GUI layer change → Forward to receiver → Save to EEPROM → Broadcast update
  ↓
Power cycle → Load EEPROM → Auto-start with saved layer
```

## Benefits

1. **Zero Configuration**: Receivers remember their layer across reboots
2. **User-Friendly**: Edit layers directly in GUI table
3. **Real-Time Feedback**: GUI updates immediately when layers change
4. **Status Visibility**: See which receivers are active vs missing
5. **Reliable Persistence**: Uses ESP32 NVS for robust storage
6. **Flexible Management**: Change layers via USB or GUI anytime
