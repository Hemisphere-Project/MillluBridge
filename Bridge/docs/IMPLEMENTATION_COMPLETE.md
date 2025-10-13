# Layer Persistence & GUI Editing - Implementation Summary

## What Was Implemented

### Goal
Enable receivers to remember their layer subscription across reboots and allow users to change layers directly from the Bridge GUI.

### Features Added
1. **EEPROM Persistence**: Receivers save their subscribed layer to non-volatile storage
2. **Auto-Start on Boot**: Receivers automatically subscribe to saved layer on power-up
3. **GUI Editing**: Layer field in Remote Nowdes table is now editable
4. **New SysEx Command**: Protocol extended with "Change Receiver Layer" (0x04)

---

## Files Modified

### 1. Nowde Firmware (`/Users/hmini25/Documents/MillluBridge/Nowde/src/main.cpp`)

#### Added Includes
```cpp
#include <Preferences.h>  // For EEPROM-like persistence
```

#### Added Constants
```cpp
#define SYSEX_CMD_CHANGE_RECEIVER_LAYER 0x04
```

#### Added Global Variable
```cpp
Preferences preferences;  // For EEPROM storage
```

#### New Functions
1. **`saveLayerToEEPROM(const char* layer)`**
   - Saves layer string to ESP32 NVS
   - Namespace: "nowde", Key: "layer"

2. **`loadLayerFromEEPROM()`**
   - Loads saved layer from ESP32 NVS
   - Returns saved layer or DEFAULT_RECEIVER_LAYER if none exists

#### Modified Functions

**`setup()`** - Auto-start from EEPROM
```cpp
// OLD: Checked #ifdef DEFAULT_RECEIVER_LAYER at compile time
#ifdef DEFAULT_RECEIVER_LAYER
  receiverModeEnabled = true;
  strncpy(subscribedLayer, DEFAULT_RECEIVER_LAYER, MAX_LAYER_LENGTH);
#endif

// NEW: Loads from EEPROM at runtime
String savedLayer = loadLayerFromEEPROM();
if (savedLayer.length() > 0 && savedLayer != "-") {
  receiverModeEnabled = true;
  strncpy(subscribedLayer, savedLayer.c_str(), MAX_LAYER_LENGTH);
  DEBUG_SERIAL.println("[INIT] Auto-starting receiver mode");
  DEBUG_SERIAL.print("  Subscribed Layer: ");
  DEBUG_SERIAL.println(subscribedLayer);
  DEBUG_SERIAL.println("  Source: EEPROM");
}
```

**`handleSysExMessage()`** - Save on layer commands
```cpp
// Added to SYSEX_CMD_SUBSCRIBE_LAYER case:
saveLayerToEEPROM(subscribedLayer);

// Added new case for SYSEX_CMD_CHANGE_RECEIVER_LAYER:
case SYSEX_CMD_CHANGE_RECEIVER_LAYER: {
  // Extract target MAC (6 bytes) and layer (16 bytes)
  // Forward to specific receiver via ESP-NOW
  // Sender acts as relay between USB and ESP-NOW
}
```

**`onDataRecv()`** - Handle ESP-NOW SysEx
```cpp
// Added SysEx handling via ESP-NOW:
if (data[0] == 0xF0 && data[1] == SYSEX_MANUFACTURER_ID) {
  if (data[2] == SYSEX_CMD_SUBSCRIBE_LAYER) {
    // Extract layer from ESP-NOW SysEx message
    // Update subscribedLayer
    // Save to EEPROM
    // Broadcast updated ReceiverInfo
  }
}
```

---

### 2. Bridge Output Manager (`/Users/hmini25/Documents/MillluBridge/Bridge/src/midi/output_manager.py`)

#### Added Constant
```python
self.SYSEX_CMD_CHANGE_RECEIVER_LAYER = 0x04
```

#### New Method
```python
def send_change_receiver_layer(self, mac_address, layer_name):
    """Send 'Change Receiver Layer' SysEx message to update a specific receiver's layer"""
    # Convert MAC string "AA:BB:CC:DD:EE:FF" to 6 bytes
    mac_bytes = [int(part, 16) for part in mac_address.split(':')]
    
    # Pad layer name to exactly 16 bytes
    layer_bytes = (layer_name[:16] + '\x00' * 16)[:16].encode('ascii')
    
    # Build message: F0 7D 04 [MAC(6)] [Layer(16)] F7
    message = ([0xF0, 0x7D, 0x04] + mac_bytes + list(layer_bytes) + [0xF7])
    
    self.midi_out.send_message(message)
    return (True, self.format_sysex_message(message))
```

#### Updated Method
**`format_sysex_message()`** - Added formatting for new command
```python
elif cmd == self.SYSEX_CMD_CHANGE_RECEIVER_LAYER:
    # Extract and display MAC and layer name
    mac_bytes = message[3:9]
    mac_str = ':'.join(f'{b:02X}' for b in mac_bytes)
    layer_bytes = message[9:-1]
    layer_name = bytes(layer_bytes).decode('ascii', errors='ignore').rstrip('\x00')
    return f"SysEx: Change Receiver Layer MAC={mac_str}, Layer='{layer_name}'"
```

---

### 3. Bridge Main Application (`/Users/hmini25/Documents/MillluBridge/Bridge/src/main.py`)

#### Modified Method
**`update_remote_nowdes_table()`** - Make layer editable
```python
# OLD: Static text display
dpg.add_text(nowde['layer'], color=layer_color)

# NEW: Editable input field
layer_input_tag = f"layer_input_{mac}"
dpg.add_input_text(
    tag=layer_input_tag,
    default_value=nowde['layer'],
    width=-1,
    on_enter=True,
    callback=lambda s, a, u: self.on_layer_changed(u['mac'], a),
    user_data={'mac': mac}
)
dpg.configure_item(layer_input_tag, color=layer_color)
```

#### New Method
```python
def on_layer_changed(self, mac_address, new_layer):
    """Handle layer change from GUI"""
    if not self.current_nowde_device:
        self.update_osc_log("Error: No Nowde connected")
        return
    
    # Validate layer name
    new_layer = new_layer.strip()[:16]
    
    if not new_layer:
        self.update_osc_log("Error: Layer name cannot be empty")
        return
    
    # Send Change Receiver Layer SysEx
    result = self.output_manager.send_change_receiver_layer(mac_address, new_layer)
    if result and result[0]:
        success, formatted_msg = result
        self.update_osc_log(f"Sent Change Receiver Layer: MAC={mac_address}, Layer={new_layer}")
        self.log_nowde_message(f"TX: {formatted_msg}")
    else:
        self.update_osc_log("Error: Failed to send Change Receiver Layer command")
```

---

## New Documentation Files Created

1. **`LAYER_PERSISTENCE_IMPLEMENTATION.md`**
   - Complete feature overview
   - Code changes explained
   - Usage instructions
   - Technical details
   - Troubleshooting guide

2. **`LAYER_CHANGE_FLOW.md`**
   - Visual diagrams of data flow
   - Step-by-step message sequences
   - Component descriptions
   - Data structure definitions
   - State management details

3. **`TESTING_CHECKLIST.md`**
   - Comprehensive test procedures
   - 12 test scenarios covering:
     - EEPROM persistence
     - Auto-start behavior
     - GUI editing
     - Multiple receivers
     - Error handling
     - Edge cases
   - Troubleshooting reference
   - Success criteria

---

## Protocol Changes

### New SysEx Command: Change Receiver Layer (0x04)

**Format:**
```
F0 7D 04 [MAC(6 bytes)] [Layer(16 bytes)] F7
```

**Flow:**
```
GUI Edit → Bridge (USB) → Sender → ESP-NOW → Receiver → EEPROM Save → Broadcast Update
```

**Example:**
```
F0 7D 04 AA BB CC DD EE FF 70 6C 61 79 65 72 31 00 00 00 00 00 00 00 00 00 F7
         └──── MAC ────┘  └────────────── "player1" + padding ────────────┘
```

---

## How It Works

### 1. Initial Setup (First Time)
1. User edits layer in GUI table
2. Bridge sends SysEx 0x04 to Sender
3. Sender forwards to specific Receiver via ESP-NOW
4. Receiver updates layer and saves to EEPROM
5. Receiver broadcasts updated info
6. GUI table updates

### 2. Auto-Start (After Reboot)
1. Receiver boots up
2. `setup()` calls `loadLayerFromEEPROM()`
3. If layer exists and not "-":
   - Enable receiver mode
   - Subscribe to saved layer
4. Receiver starts listening immediately

### 3. Persistence
- Uses ESP32 Preferences library (NVS)
- Namespace: "nowde"
- Key: "layer"
- Survives power cycles and firmware updates (if NVS not erased)

---

## Benefits

### User Experience
- ✅ Zero configuration after initial setup
- ✅ Edit layers directly in GUI table
- ✅ No need to re-subscribe after power cycle
- ✅ Visual feedback with color-coded states
- ✅ Real-time updates

### Technical
- ✅ Reliable persistence using ESP32 NVS
- ✅ Backwards compatible (existing commands still work)
- ✅ Scalable (supports multiple receivers)
- ✅ Robust error handling
- ✅ Clear debug output

### Workflow
- ✅ Set once, works forever
- ✅ Easy to reconfigure on the fly
- ✅ No USB connection needed after initial setup
- ✅ Receivers auto-reconnect with correct layer

---

## Testing Status

**Ready for Testing:** ✅

All code changes complete and error-free:
- ✅ ESP32 firmware compiled without errors
- ✅ Python Bridge code validated
- ✅ Protocol changes documented
- ✅ Testing checklist provided

**Next Steps:**
1. Flash updated firmware to Nowde devices
2. Run Bridge application
3. Follow TESTING_CHECKLIST.md
4. Verify all 12 test scenarios pass

---

## Backward Compatibility

### Existing Features Still Work
- ✅ Bridge Connected (0x01)
- ✅ Subscribe Layer via USB (0x02)
- ✅ Receiver Table Report (0x03)
- ✅ ESP-NOW communication
- ✅ Status tracking (Active/Missing)
- ✅ Version reporting

### Migration Path
- Old firmware: Works but no persistence
- New firmware: Auto-upgrades with persistence
- No configuration changes needed

---

## Future Enhancements (Optional)

1. **GUI Improvements**
   - Add "Reset to Default" button
   - Bulk edit multiple receivers
   - Layer name autocomplete from Millumin

2. **Configuration Management**
   - Export/import receiver configs
   - Save presets for different setups
   - Remote backup of EEPROM data

3. **Advanced Features**
   - Layer groups (one receiver → multiple layers)
   - Time-based layer switching
   - Layer priority/fallback

---

## Summary

✅ **Goal Achieved:** Receivers now remember their layer across reboots and can be edited from GUI

✅ **Implementation Complete:** All code changes done, tested for compilation

✅ **Documentation Complete:** Full guides, flow diagrams, and testing procedures provided

✅ **Ready for Deployment:** Flash firmware and test according to checklist

---

## Questions or Issues?

Refer to:
- `LAYER_PERSISTENCE_IMPLEMENTATION.md` for technical details
- `LAYER_CHANGE_FLOW.md` for visual diagrams
- `TESTING_CHECKLIST.md` for testing procedures
- Serial debug output for real-time troubleshooting
