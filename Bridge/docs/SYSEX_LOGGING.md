# Bridge SysEx Logging - Feature Summary

## Overview
The Bridge application now logs all SysEx messages (sent and received) in human-readable format in the "Nowde Logs" section.

## What's Logged

### Sent Messages (TX)

1. **Bridge Connected**
   - Sent automatically when a Nowde device is connected
   - Format: `[HH:MM:SS] TX: SysEx: Bridge Connected (F0 7D 01 F7)`
   - Purpose: Activates sender mode on the Nowde

2. **Subscribe to Layer**
   - Sent when user clicks "Subscribe" button with a layer name
   - Format: `[HH:MM:SS] TX: SysEx: Subscribe to Layer 'player2' (F0 7D 02 70 6C 61 79 65 72 32 F7)`
   - Purpose: Activates receiver mode and subscribes Nowde to a Millumin layer

### Received Messages (RX)

1. **Receiver Table**
   - Received periodically from Nowde in sender mode
   - Shows connected remote Nowdes
   - Format examples:
     - Empty: `[HH:MM:SS] RX: SysEx: Receiver Table - 0 devices (F0 7D 03 00 F7)`
     - With devices: `[HH:MM:SS] RX: SysEx: Receiver Table - 1 device(s): Nowde-EEFF (player2) (F0 7D 03 01 AA BB CC DD EE FF ...)`

## Log Format Details

Each log entry includes:
- **Timestamp**: `[HH:MM:SS]` format
- **Direction**: `TX` (transmitted) or `RX` (received)
- **Message Type**: Human-readable description
- **Hex Dump**: Raw SysEx bytes in hexadecimal for debugging

### Examples

```
[14:32:15] TX: SysEx: Bridge Connected (F0 7D 01 F7)
[14:32:18] TX: SysEx: Subscribe to Layer 'player2' (F0 7D 02 70 6C 61 79 65 72 32 F7)
[14:32:20] RX: SysEx: Receiver Table - 1 device(s): Nowde-EEFF (player2) (F0 7D 03 01 AA BB CC DD EE FF 70 6C 61 79 65 72 32 00 00 00 00 00 00 00 00 00 F7)
[14:32:25] RX: SysEx: Receiver Table - 2 device(s): Nowde-EEFF (player2), Nowde-1234 (player1) (F0 7D 03 02 ...)
```

## Where to See the Logs

1. In the Bridge application GUI
2. Click the **"Show Logs"** button next to "USB Status:"
3. The "Nowde Logs" section will expand showing all MIDI and SysEx messages
4. Auto-scrolls to show latest messages
5. Keeps last 1000 lines

## Implementation Details

### Files Modified

1. **`src/midi/output_manager.py`**
   - Added `format_sysex_message()` method
   - Modified `send_bridge_connected()` to return formatted message
   - Modified `send_subscribe_layer()` to return formatted message

2. **`src/midi/input_manager.py`**
   - Modified `_parse_receiver_table()` to return formatted message
   - Modified `_handle_sysex_message()` to send formatted message via callback
   - Callback sends both parsed data and formatted string

3. **`src/main.py`**
   - Added `log_nowde_message()` helper method
   - Modified `handle_sysex_message()` to log received SysEx
   - Modified `on_subscribe_layer()` to log sent SysEx
   - Modified `connect_nowde_device()` to log Bridge Connected SysEx

### Message Flow

**Sending:**
```
User Action → output_manager.send_*() → Format message → Return (success, formatted_msg) → log_nowde_message()
```

**Receiving:**
```
MIDI Input → _process_sysex() → _handle_sysex_message() → _parse_receiver_table() → 
Returns formatted string → Callback with 'sysex_received' → handle_sysex_message() → log_nowde_message()
```

## Benefits

1. **Debugging**: Easy to see exact SysEx communication between Bridge and Nowde
2. **Protocol Understanding**: Hex dump helps understand the binary protocol
3. **Troubleshooting**: Quickly identify if messages are being sent/received correctly
4. **Learning**: Clear human-readable format makes the protocol accessible
5. **Monitoring**: Track remote Nowdes joining/leaving the network

## SysEx Protocol Reference

### Command Bytes
- `0x01`: Bridge Connected (Bridge → Nowde, activates sender mode)
- `0x02`: Subscribe to Layer (Bridge → Nowde, activates receiver mode)
- `0x03`: Receiver Table (Nowde → Bridge, reports remote Nowdes)

### Message Format
```
F0          - SysEx Start
7D          - Manufacturer ID (custom)
[CMD]       - Command byte
[DATA...]   - Command-specific data
F7          - SysEx End
```

## Testing

Run the test script to verify formatting:
```bash
cd /Users/hmini25/Documents/MillluBridge/Bridge
.venv/bin/python test_sysex_logging.py
```

Expected output shows correctly formatted messages for all SysEx types.
