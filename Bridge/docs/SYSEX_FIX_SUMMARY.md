# SysEx Communication - FIXED ✅

## Problem Summary
Nowde was not processing SysEx messages from Bridge despite receiving them via USB MIDI.

## Root Cause
**Incorrect CIN (Code Index Number) extraction from USB MIDI packet header.**

The USB MIDI packet header contains the CIN in the **lower nibble** (bits 0-3), but the code was extracting the **upper nibble** (bits 4-7).

### Before (Broken)
```cpp
uint8_t cin = (packet.header >> 4) & 0x0F;  // Extracting upper nibble
```

For header `0x04`:
- Wrong extraction: `(0x04 >> 4) & 0x0F = 0x00` ❌
- Never matched SysEx CIN range (0x4-0x7)

### After (Fixed)
```cpp
uint8_t cin = packet.header & 0x0F;  // Extracting lower nibble
```

For header `0x04`:
- Correct extraction: `0x04 & 0x0F = 0x04` ✅
- Matches SysEx CIN range (0x4-0x7)

## USB MIDI Packet Format

```
┌─────────┬─────────┬─────────┬─────────┐
│ Header  │  Byte1  │  Byte2  │  Byte3  │
├─────────┼─────────┼─────────┼─────────┤
│ CN│CIN  │  Data   │  Data   │  Data   │
│7-4│3-0  │         │         │         │
└─────────┴─────────┴─────────┴─────────┘

CN  = Cable Number (bits 7-4) - typically 0
CIN = Code Index Number (bits 3-0) - message type
```

### SysEx CIN Values
- `0x4` = SysEx starts or continues (3 bytes of data)
- `0x5` = SysEx ends with 1 byte
- `0x6` = SysEx ends with 2 bytes
- `0x7` = SysEx ends with 3 bytes

## Example: Bridge Connected Message

### Bridge Sends
```
F0 7D 01 F7
```

### USB MIDI Packets
```
Packet 1: Header=0x04, Bytes: F0 7D 01
  CIN = 0x4 (SysEx starts, 3 bytes)

Packet 2: Header=0x05, Bytes: F7 00 00
  CIN = 0x5 (SysEx ends with 1 byte)
```

### Nowde Logs (After Fix)
```
[SYSEX RX] F0 7D 01 F7 (4 bytes)

=== SENDER MODE ACTIVATED ===
Received: Bridge Connected SysEx
Status: Broadcasting ESP-NOW beacons
=============================
```

## Example: Subscribe to Layer "super"

### Bridge Sends
```
F0 7D 02 73 75 70 65 72 F7
│  │  │  └────┬────┘
│  │  │       └── "super" in ASCII
│  │  └── Command: Subscribe (0x02)
│  └── Manufacturer ID (0x7D)
└── SysEx Start
```

### USB MIDI Packets
```
Packet 1: Header=0x04, Bytes: F0 7D 02
  CIN = 0x4 (SysEx starts, 3 bytes)

Packet 2: Header=0x04, Bytes: 73 75 70
  CIN = 0x4 (SysEx continues, 3 bytes) - "sup"

Packet 3: Header=0x07, Bytes: 65 72 F7
  CIN = 0x7 (SysEx ends with 3 bytes) - "er" + F7
```

### Nowde Logs (After Fix)
```
[SYSEX RX] F0 7D 02 73 75 70 65 72 F7 (9 bytes)

=== RECEIVER MODE ACTIVATED ===
Received: Subscribe to Layer SysEx
Layer: super
Status: Listening for sender beacons
===============================
```

## Clean Logs

The verbose debug logs have been cleaned up. You'll now see:

### Normal Operation
```
[INIT] Nowde starting...
[INIT] USB MIDI initialized
[INIT] WiFi initialized
[INIT] ESP-NOW initialized
[INIT] Ready!

[SYSEX RX] F0 7D 01 F7 (4 bytes)
=== SENDER MODE ACTIVATED ===

[ESP-NOW TX] Sender Beacon #10 (every 10th logged)
[ESP-NOW TX] Sender Beacon #20 (every 10th logged)
```

### When Subscribing
```
[SYSEX RX] F0 7D 02 73 75 70 65 72 F7 (9 bytes)
=== RECEIVER MODE ACTIVATED ===
Layer: super
```

### When Receiving ESP-NOW
```
[ESP-NOW RX] Receiver Info from XX:XX:XX:XX:XX:XX
  Layer: player2
```

## Files Modified

**`/Users/hmini25/Documents/MillluBridge/Nowde/src/main.cpp`**
- Fixed CIN extraction: `cin = packet.header & 0x0F`
- Cleaned up debug logging
- Kept essential `[SYSEX RX]` logs with hex dump

## Verification

✅ **Bridge Connected** - Works  
✅ **Subscribe to Layer** - Works  
✅ **ESP-NOW Beacons** - Broadcasting  
✅ **Serial Logging** - Clean and informative  

## Next Steps

Your ESP-NOW network should now work correctly:

1. **Sender Mode (USB-connected Nowde)**
   - Receives Bridge Connected SysEx
   - Broadcasts ESP-NOW beacons
   - Reports receiver table to Bridge

2. **Receiver Mode (Standalone Nowde)**
   - Can subscribe to Millumin layers
   - Listens for sender beacons
   - Sends info back to sender

3. **Bridge Application**
   - Logs all SysEx TX/RX in "Nowde Logs"
   - Shows remote Nowdes in real-time
   - Subscribe to Layer UI control works

## Technical Reference

### USB MIDI Bit Manipulation
```cpp
// Header byte: 0xCN (where C=cable, N=CIN)
uint8_t header = 0x04;

// WRONG - gets cable number (upper nibble)
uint8_t wrong = (header >> 4) & 0x0F;  // = 0x00

// CORRECT - gets CIN (lower nibble)
uint8_t correct = header & 0x0F;  // = 0x04
```

### Why This Matters
The USB MIDI library packs data into 4-byte packets with a header that describes the packet type. For SysEx messages, the CIN (Code Index Number) tells us:
- If this is the start, middle, or end of a SysEx stream
- How many data bytes are valid in this packet

Without correctly extracting the CIN, the firmware couldn't recognize SysEx packets at all.

---

**The bug has been fixed and the system is now fully operational! 🎉**
