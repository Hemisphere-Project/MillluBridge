# Debugging SysEx Communication

## Problem
Nowde is not receiving SysEx messages from Bridge (Bridge Connected or Subscribe to Layer).

## What Was Added
Verbose logging in Nowde firmware to track MIDI/SysEx reception:
- `[MIDI RX]` - Every incoming MIDI packet
- `[SYSEX]` - SysEx-specific events (start, end, data)

## Testing Steps

### 1. Upload Latest Firmware
```bash
cd /Users/hmini25/Documents/MillluBridge/Nowde
~/.platformio/penv/bin/platformio run --target upload
```

### 2. Monitor Nowde Serial Output
Open PlatformIO Monitor or use screen:
```bash
# Option A: PlatformIO Monitor
~/.platformio/penv/bin/platformio device monitor

# Option B: Screen (disconnect other monitors first)
screen /dev/cu.usbmodem* 115200
# To exit screen: Ctrl+A then K then Y
```

### 3. Run Bridge Application
```bash
cd /Users/hmini25/Documents/MillluBridge/Bridge
.venv/bin/python src/main.py
```

### 4. Check Nowde Logs

#### Expected on Bridge Connection:
```
[INIT] Nowde starting...
[INIT] USB MIDI initialized
[INIT] WiFi initialized
[INIT] ESP-NOW initialized
[INIT] Ready!

[MIDI RX] Header: 0x04, Bytes: F0 7D 01
[SYSEX] CIN=0x4, Processing bytes...
[SYSEX] Start detected (F0)
[MIDI RX] Header: 0x05, Bytes: F7 00 00
[SYSEX] CIN=0x5, Processing bytes...
[SYSEX] End detected (F7), length=4 bytes
[SYSEX] Data: F0 7D 01 F7

=== SENDER MODE ACTIVATED ===
Received: Bridge Connected SysEx
Status: Broadcasting ESP-NOW beacons
=============================
```

#### Expected on Subscribe to Layer:
```
[MIDI RX] Header: 0x04, Bytes: F0 7D 02
[SYSEX] CIN=0x4, Processing bytes...
[SYSEX] Start detected (F0)
[MIDI RX] Header: 0x04, Bytes: 70 6C 61  # "pla"
[SYSEX] CIN=0x4, Processing bytes...
[MIDI RX] Header: 0x04, Bytes: 79 65 72  # "yer"
[SYSEX] CIN=0x4, Processing bytes...
[MIDI RX] Header: 0x06, Bytes: 32 F7 00  # "2" + F7
[SYSEX] CIN=0x6, Processing bytes...
[SYSEX] End detected (F7), length=11 bytes
[SYSEX] Data: F0 7D 02 70 6C 61 79 65 72 32 F7

=== RECEIVER MODE ACTIVATED ===
Received: Subscribe to Layer SysEx
Layer: player2
Status: Listening for sender beacons
===============================
```

## Possible Issues

### Issue 1: No `[MIDI RX]` Messages at All
**Problem:** Nowde is not receiving ANY MIDI data from Bridge

**Check:**
- Is Bridge showing "USB Status: [OK]" and connected to "Nowde 1.0"?
- Is the USB cable working? (Try different cable/port)
- Is the Nowde USB device recognized by macOS?
  ```bash
  ls /dev/cu.usb*  # Should show device
  system_profiler SPUSBDataType | grep -A 10 "Nowde"
  ```

**Solution:**
- Reconnect USB cable
- Restart Bridge application
- Check Bridge logs - does it show "TX: SysEx: Bridge Connected"?

### Issue 2: `[MIDI RX]` But No `[SYSEX]` Messages
**Problem:** MIDI packets arriving but not recognized as SysEx

**Check:**
- What CIN (Code Index Number) is in the Header?
- SysEx should have CIN 0x4-0x7 (Header & 0xF0 = 0x40-0x70)

**Possible causes:**
- Bridge sending wrong packet format
- USB MIDI library issue
- CIN not in range 0x4-0x7

**Debug:**
Look at the Header byte in logs:
```
[MIDI RX] Header: 0xXX, Bytes: YY YY YY
                    ^^
                    This should be 0x04-0x07 for SysEx
```

### Issue 3: `[SYSEX]` Events But No Mode Activation
**Problem:** SysEx detected but handleSysExMessage() not called or failing

**Check in logs:**
- Is `[SYSEX] Data:` line showing correct bytes?
  - Bridge Connected: `F0 7D 01 F7`
  - Subscribe Layer: `F0 7D 02 [layer bytes...] F7`

**Possible causes:**
- Wrong manufacturer ID (should be 0x7D)
- Wrong command byte (0x01 or 0x02)
- Validation failing in handleSysExMessage()

**Add debug print in handleSysExMessage():**
```cpp
void handleSysExMessage(uint8_t* data, uint8_t length) {
  DEBUG_SERIAL.printf("[DEBUG] handleSysExMessage called: length=%d\n", length);
  
  // Print all bytes
  DEBUG_SERIAL.print("[DEBUG] Bytes: ");
  for (int i = 0; i < length; i++) {
    DEBUG_SERIAL.printf("%02X ", data[i]);
  }
  DEBUG_SERIAL.println();
  
  // ... rest of function
}
```

### Issue 4: Bridge Not Sending
**Problem:** Bridge application not sending SysEx

**Check Bridge Logs:**
1. Click "Show Logs" button next to "USB Status:"
2. Look for:
   ```
   [HH:MM:SS] TX: SysEx: Bridge Connected (F0 7D 01 F7)
   ```

**If no TX messages:**
- Bridge not connected to Nowde MIDI device
- output_manager.send_bridge_connected() not being called
- MIDI port not opened successfully

**Debug:**
Check Bridge console output:
```
Opened MIDI port: Nowde 1.0
Opened MIDI input port: Nowde 1.0
Sent Bridge Connected SysEx
```

## Quick Test: Manual SysEx Send

If automated sending doesn't work, test manually:

### Using Python in Bridge
```python
# In Bridge Python console
from midi.output_manager import OutputManager
om = OutputManager()
ports = om.get_ports()
print(ports)  # Should show "Nowde 1.0"

# Open port
om.open_port("Nowde 1.0")

# Send Bridge Connected
message = [0xF0, 0x7D, 0x01, 0xF7]
om.midi_out.send_message(message)
print("Sent:", [hex(b) for b in message])
```

Watch Nowde serial logs - you should see the `[MIDI RX]` messages.

### Using sendmidi (macOS)
Install sendmidi:
```bash
brew install sendmidi
```

Send SysEx:
```bash
# Bridge Connected
sendmidi dev "Nowde 1.0" hex syx F0 7D 01 F7

# Subscribe to "player2"
sendmidi dev "Nowde 1.0" hex syx F0 7D 02 70 6C 61 79 65 72 32 F7
```

## Verification Checklist

- [ ] Nowde firmware uploaded with verbose logging
- [ ] Serial monitor connected and showing `[INIT]` messages
- [ ] Bridge application running
- [ ] Bridge shows "USB Status: [OK] Nowde 1.0"
- [ ] Bridge Nowde Logs show "TX: SysEx: Bridge Connected"
- [ ] Nowde serial shows `[MIDI RX]` messages
- [ ] Nowde serial shows `[SYSEX]` processing
- [ ] Nowde shows "=== SENDER MODE ACTIVATED ===" or similar

## Next Steps

Once you have the serial output from Nowde while Bridge is running:
1. Copy the relevant log section
2. Check which step is failing (MIDI RX? SYSEX? handleSysExMessage?)
3. We can add more specific debugging based on what's happening

## Files Modified

- `/Users/hmini25/Documents/MillluBridge/Nowde/src/main.cpp`
  - Added `[MIDI RX]` logging for all packets
  - Added `[SYSEX]` logging for SysEx parsing steps
  - Added data dumps when SysEx message completes
