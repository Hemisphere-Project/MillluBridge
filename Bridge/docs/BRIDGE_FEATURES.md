# Bridge Application - Complete Feature Summary

## Overview
The MilluBridge application now includes full ESP-NOW support for remote Nowde device management.

## New Features Added

### 1. SysEx Protocol Implementation

#### Output Manager (`midi/output_manager.py`)
**New Methods:**
- `send_bridge_connected()` - Activates sender mode on Nowde
- `send_subscribe_layer(layer_name)` - Activates receiver mode with layer subscription

**SysEx Format:**
```python
# Bridge Connected: F0 7D 01 F7
# Subscribe Layer: F0 7D 02 [layer_name] F7
```

#### Input Manager (`midi/input_manager.py`)
**New Features:**
- SysEx parsing with state machine
- Receiver table message parsing
- Callback system for parsed SysEx data

**Parsed Data Structure:**
```python
{
    'mac': 'XX:XX:XX:XX:XX:XX',
    'layer': 'Layer1',
    'name': 'Nowde-XXXX',
    'version': '1.0'
}
```

### 2. GUI Enhancements

#### Remote Nowdes Table
- **Location:** After Local Nowde section
- **Columns:** Name (with layer), Version, UUID
- **Updates:** Real-time via SysEx messages from sender Nowde
- **Features:** Resizable, sortable, row backgrounds

#### Subscribe to Layer Controls
- **Input Field:** Enter layer name (max 16 chars)
- **Subscribe Button:** Sends SysEx command to connected Nowde
- **Validation:** Checks for connection and valid input
- **Feedback:** Logs success/error messages

### 3. Auto-Activation Flow

**Connection Sequence:**
1. Bridge detects "Nowde" device on USB
2. Opens MIDI input/output ports
3. Automatically sends "Bridge Connected" SysEx
4. Nowde activates sender mode
5. Begins broadcasting ESP-NOW beacons

**Result:**
- No manual setup required
- Nowde immediately becomes ESP-NOW sender
- Ready to discover remote Nowdes

### 4. Real-time Updates

**Data Flow:**
```
Remote Nowde (Receiver)
    ↓ ESP-NOW
Local Nowde (Sender)
    ↓ SysEx via USB MIDI
Bridge Application
    ↓ GUI Update
Remote Nowdes Table
```

**Update Triggers:**
- New remote Nowde discovered
- Remote Nowde layer subscription changes
- Remote Nowde disconnects (timeout)

## User Interface Layout

```
┌─────────────────────────────────────────────────┐
│ Millumin Settings                               │
│ ├── OSC Address/Port                            │
│ ├── Status Indicator                            │
│ └── OSC Logs (toggleable)                       │
├─────────────────────────────────────────────────┤
│ Millumin Layers                                 │
│ └── Table (Layer, State, Filename, etc.)        │
├─────────────────────────────────────────────────┤
│ Local Nowde                                     │
│ ├── USB Status                                  │
│ ├── Subscribe to Layer: [input] [Subscribe]    │
│ └── Nowde Logs (toggleable)                     │
├─────────────────────────────────────────────────┤
│ Remote Nowdes                                   │
│ └── Table (Name, Version, UUID)                 │
│     ├── Nowde-XXXX (Layer1) | 1.0 | XX:XX:...   │
│     └── Nowde-YYYY (Layer2) | 1.0 | YY:YY:...   │
└─────────────────────────────────────────────────┘
```

## Usage Scenarios

### Scenario 1: Bridge as ESP-NOW Hub
1. Connect Nowde to computer via USB
2. Bridge auto-activates sender mode
3. Remote Nowdes discover and register
4. Bridge displays all remote Nowdes
5. Monitor network topology in real-time

### Scenario 2: Layer-based Routing
1. Configure multiple Nowdes as receivers
2. Each subscribes to different layer (via Bridge UI)
3. Sender Nowde maintains routing table
4. Can implement layer-specific MIDI routing

### Scenario 3: Network Diagnostics
1. View all active remote Nowdes
2. See layer subscriptions
3. Monitor connection status
4. Detect timeouts and disconnections

## API Reference

### Main Application Methods

```python
def handle_sysex_message(self, msg_type, data):
    """Handle parsed SysEx messages from Nowde"""
    # msg_type: 'receiver_table'
    # data: list of remote Nowde dicts

def update_remote_nowdes_table(self):
    """Update the Remote Nowdes table in the GUI"""
    # Clears and rebuilds table from self.remote_nowdes

def on_subscribe_layer(self):
    """Handle Subscribe to Layer button click"""
    # Validates input and sends SysEx command
```

### InputManager Methods

```python
def _process_sysex(self, message):
    """Process incoming MIDI message for SysEx data"""

def _parse_receiver_table(self, sysex_data):
    """Parse receiver table SysEx message"""
    # Returns list of {mac, layer, name, version}
```

### OutputManager Methods

```python
def send_bridge_connected(self):
    """Send 'Bridge Connected' SysEx message"""
    # Activates sender mode on Nowde

def send_subscribe_layer(self, layer_name):
    """Send 'Subscribe to Layer' SysEx message"""
    # Activates receiver mode on Nowde
```

## Configuration

### Adjustable Parameters

**In Nowde Firmware:**
```cpp
#define RECEIVER_TIMEOUT_MS 5000
#define SENDER_TIMEOUT_MS 5000
#define RECEIVER_BEACON_INTERVAL_MS 1000
#define SENDER_BEACON_INTERVAL_MS 1000
#define BRIDGE_REPORT_INTERVAL_MS 500
```

**In Bridge Application:**
- MIDI refresh interval: 1 second (hardcoded in thread)
- GUI update: On data change
- Log retention: 1000 lines

## Error Handling

### Bridge Application
- Validates Nowde connection before sending SysEx
- Checks for valid layer name input
- Logs all errors to OSC log window
- Gracefully handles disconnections

### Input Manager
- Validates SysEx message format
- Checks manufacturer ID and command
- Handles incomplete messages
- Robust state machine for SysEx parsing

## Logging and Debugging

### OSC/MIDI Logs
- All SysEx sends logged
- Remote Nowde updates logged
- Connection events logged
- Timestamps on all entries

### Nowde Logs (Toggle)
- MIDI IN/OUT traffic
- Human-readable format
- Direction indicators
- Auto-scroll, 1000 line limit

### Serial Monitor (Nowde)
- ESP-NOW events
- SysEx reception
- Mode activation
- Table updates

## Known Limitations

1. **Single USB Nowde:** Only one Nowde can be USB-connected at a time
2. **Layer Length:** Maximum 16 characters
3. **Receiver Table:** Updates every 500ms (not instant)
4. **MAC as UUID:** No custom UUIDs yet
5. **Version Hardcoded:** Version "1.0" is static

## Future Enhancements

### Planned Features
- [ ] Bidirectional MIDI routing based on layers
- [ ] Custom Nowde naming (persistent)
- [ ] Firmware version in ESP-NOW protocol
- [ ] RSSI signal strength display
- [ ] Connection quality metrics
- [ ] Multi-Nowde USB support (hub mode)
- [ ] Layer auto-discovery from Millumin
- [ ] Save/load layer configurations

### Protocol Extensions
- [ ] Add version field to beacons
- [ ] Include RSSI in receiver info
- [ ] Add ping/pong for latency measurement
- [ ] Implement mesh routing (multi-hop)
- [ ] Add encryption for secure communication

## Troubleshooting

### Remote Nowdes not appearing
1. Check sender mode activated (Serial: "Sender mode activated")
2. Verify ESP-NOW range (<100m, ideally <20m)
3. Ensure receiver has layer subscription
4. Check Bridge logs for "Remote Nowdes updated"

### Subscribe button not working
1. Verify Nowde is connected (USB Status: ✓)
2. Check layer name is not empty
3. Look for error in OSC logs
4. Verify MIDI output port is open

### Table not updating
1. Check SysEx callback registered
2. Verify InputManager has sysex_callback
3. Look for parse errors in logs
4. Ensure Nowde reporting interval (500ms)

## Testing Checklist

- [x] SysEx parsing in InputManager
- [x] SysEx sending in OutputManager
- [x] GUI table population
- [x] Subscribe UI controls
- [x] Auto-activation on connection
- [x] Real-time table updates
- [x] Error handling and validation
- [x] Logging and feedback
- [ ] End-to-end ESP-NOW test with 2+ Nowdes
- [ ] Layer-based routing implementation
- [ ] Performance under load (10+ remotes)

## Documentation Files

- `ESP-NOW_PROTOCOL.md` - Complete protocol specification
- `TESTING_GUIDE.md` - Step-by-step testing procedures
- This file - Bridge application features

## Quick Start

1. **Flash Nowde firmware**
   ```bash
   cd Nowde && platformio run --target upload
   ```

2. **Run Bridge**
   ```bash
   cd Bridge && .venv/bin/python src/main.py
   ```

3. **Connect Nowde** - Auto-detected, sender mode activated

4. **Subscribe receiver Nowdes** - Use UI controls

5. **Monitor** - Watch Remote Nowdes table populate

That's it! The system is designed for minimal manual setup.
