# Layer Persistence & GUI Editing Implementation

## Overview
This document describes the implementation of persistent layer storage and GUI-based layer editing for remote Nowde receivers.

## Features Implemented

### 1. EEPROM Persistence (ESP32)
- **Storage Library**: ESP32 Preferences (NVS - Non-Volatile Storage)
- **Namespace**: "nowde"
- **Key**: "layer"
- **Default Fallback**: DEFAULT_RECEIVER_LAYER ("-")

### 2. Auto-Start on Boot
When a Nowde device boots:
1. Loads saved layer from EEPROM using `loadLayerFromEEPROM()`
2. If a valid layer exists (not empty, not "-"):
   - Automatically enables receiver mode
   - Subscribes to the saved layer
   - No need to wait for USB commands

### 3. GUI Editable Layer Field
- Layer column in "Remote Nowdes" table is now editable
- Users can type a new layer name and press Enter
- Changes propagate: GUI → Bridge → Sender → Receiver → EEPROM

### 4. New SysEx Command: Change Receiver Layer (0x04)

**Format**: `F0 7D 04 [MAC(6 bytes)] [Layer(16 bytes)] F7`

**Flow**:
```
User edits layer in GUI
  ↓
Bridge sends SysEx 0x04 to Sender via USB
  ↓
Sender forwards via ESP-NOW to specific Receiver (by MAC)
  ↓
Receiver updates layer, saves to EEPROM
  ↓
Receiver broadcasts updated ReceiverInfo
  ↓
Sender relays to Bridge via SysEx 0x03
  ↓
GUI table updates with new layer
```

## Code Changes

### Nowde Firmware (`main.cpp`)

#### Added Includes
```cpp
#include <Preferences.h>
```

#### Added Constants
```cpp
#define SYSEX_CMD_CHANGE_RECEIVER_LAYER 0x04
```

#### New Functions
```cpp
void saveLayerToEEPROM(const char* layer);
String loadLayerFromEEPROM();
```

#### Modified Functions
1. **`setup()`**
   - Loads saved layer from EEPROM on boot
   - Auto-starts receiver mode if layer exists

2. **`handleSysExMessage()`**
   - On `SYSEX_CMD_SUBSCRIBE_LAYER`: Saves layer to EEPROM
   - On `SYSEX_CMD_CHANGE_RECEIVER_LAYER`: Sender forwards to receiver via ESP-NOW

3. **`onDataRecv()`**
   - Handles SysEx messages received via ESP-NOW (for layer changes)

### Bridge Python (`output_manager.py`)

#### Added Constants
```python
self.SYSEX_CMD_CHANGE_RECEIVER_LAYER = 0x04
```

#### New Method
```python
def send_change_receiver_layer(self, mac_address, layer_name):
    """Send 'Change Receiver Layer' SysEx to update receiver's layer"""
```

### Bridge Python (`main.py`)

#### Modified `update_remote_nowdes_table()`
- Changed Layer column from `dpg.add_text()` to `dpg.add_input_text()`
- Added `on_enter=True` to trigger on Enter key
- Added callback to handle layer changes

#### New Method
```python
def on_layer_changed(self, mac_address, new_layer):
    """Handle layer change from GUI"""
```

## Usage

### For Receivers
1. **Initial Setup**: Use USB command "Subscribe to Layer" (0x02) to set initial layer
2. **Persistent Storage**: Layer is automatically saved to EEPROM
3. **Auto-Start**: On next boot, receiver auto-subscribes to saved layer
4. **GUI Update**: Edit layer in Bridge GUI anytime

### For GUI Users
1. Connect Bridge to Sender Nowde via USB
2. Remote Nowdes table shows all discovered receivers
3. Click on Layer field for any receiver
4. Type new layer name and press Enter
5. Change is sent and saved to receiver's EEPROM
6. Receiver immediately starts listening to new layer

## Technical Details

### EEPROM Functions

#### Save Layer
```cpp
void saveLayerToEEPROM(const char* layer) {
    Preferences prefs;
    prefs.begin("nowde", false);
    prefs.putString("layer", layer);
    prefs.end();
}
```

#### Load Layer
```cpp
String loadLayerFromEEPROM() {
    Preferences prefs;
    prefs.begin("nowde", true);
    String layer = prefs.getString("layer", DEFAULT_RECEIVER_LAYER);
    prefs.end();
    return layer;
}
```

### SysEx Protocol Summary

| Command | Hex | Format | Description |
|---------|-----|--------|-------------|
| Bridge Connected | 0x01 | `F0 7D 01 F7` | Activates sender mode |
| Subscribe Layer | 0x02 | `F0 7D 02 [layer] F7` | Sets receiver layer |
| Receiver Table | 0x03 | `F0 7D 03 [entries...] F7` | Reports receiver list |
| Change Receiver Layer | 0x04 | `F0 7D 04 [MAC(6)] [layer(16)] F7` | Updates specific receiver |

### ESP-NOW Communication
- Sender and receivers communicate via ESP-NOW (peer-to-peer)
- MAC addresses are used to identify specific receivers
- Dynamic peer management ensures reliable delivery
- SysEx commands are forwarded from USB to ESP-NOW transparently

## Testing

### Test Layer Persistence
1. Set layer via GUI: Edit layer in Remote Nowdes table
2. Verify save: Check debug serial output for "Layer saved to EEPROM"
3. Power cycle receiver: Disconnect and reconnect power
4. Verify auto-start: Serial output should show "Auto-starting receiver mode"
5. Verify GUI: Bridge should show receiver with correct layer

### Test GUI Editing
1. Edit layer in GUI table (press Enter after typing)
2. Check Nowde Logs for TX message: "SysEx: Change Receiver Layer..."
3. Check receiver serial for layer change confirmation
4. Verify table updates with new layer

## Troubleshooting

### Receiver doesn't auto-start
- Check if layer was saved: Look for "Layer saved to EEPROM" in serial output
- Verify saved value: After boot, check "Auto-starting receiver mode" message
- Clear EEPROM: Send empty layer or default ("-") to reset

### GUI edit doesn't work
- Ensure Sender Nowde is connected via USB
- Check Bridge status indicator shows "[OK]"
- Verify MAC address format in Remote Nowdes table
- Check Nowde Logs for error messages

### Layer not persisting
- Ensure ESP32 Preferences library is included
- Check NVS partition is available (platformio.ini)
- Verify EEPROM functions are called after layer changes

## Future Enhancements
- Add "Reset to Default" button in GUI
- Bulk edit multiple receivers at once
- Export/import receiver configurations
- Add layer name autocomplete from Millumin layers
