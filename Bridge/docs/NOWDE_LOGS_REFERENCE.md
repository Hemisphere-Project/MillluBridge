# Nowde Logs - Visual Reference

## What You'll See in the Bridge Application

### Location
Click **"Show Logs"** button next to "USB Status:" in the "Local Nowde" section.

### Example Log Output

```
─────────────────────── Nowde Logs ───────────────────────
┌─────────────────────────────────────────────────────────┐
│ [14:32:15] TX: SysEx: Bridge Connected (F0 7D 01 F7)   │
│ [14:32:18] TX: SysEx: Subscribe to Layer 'player2'     │
│            (F0 7D 02 70 6C 61 79 65 72 32 F7)           │
│ [14:32:20] RX: SysEx: Receiver Table - 1 device(s):    │
│            Nowde-EEFF (player2)                          │
│            (F0 7D 03 01 AA BB CC DD EE FF ...)          │
│ [14:32:22] OUT: Note On: C4, Vel=100 (Ch 1)             │
│            Raw: [144, 60, 100]                           │
│ [14:32:25] RX: SysEx: Receiver Table - 2 device(s):    │
│            Nowde-EEFF (player2), Nowde-1234 (player1)   │
│            (F0 7D 03 02 ...)                             │
└─────────────────────────────────────────────────────────┘
```

## Log Entry Format

### TX (Transmitted) Messages
```
[HH:MM:SS] TX: <Human-readable description> (<Hex bytes>)
```

### RX (Received) Messages
```
[HH:MM:SS] RX: <Human-readable description> (<Hex bytes>)
```

### Regular MIDI Messages (if any)
```
[HH:MM:SS] IN/OUT: <MIDI message type> - Raw: [bytes]
```

## Typical Workflow Log

### 1. Connecting a Nowde Device
```
[14:30:00] TX: SysEx: Bridge Connected (F0 7D 01 F7)
```
This activates sender mode on the Nowde.

### 2. Subscribing to a Layer
```
[14:30:05] TX: SysEx: Subscribe to Layer 'player2' 
           (F0 7D 02 70 6C 61 79 65 72 32 F7)
```
User typed "player2" and clicked Subscribe button.

### 3. Receiving Remote Nowdes Updates
```
[14:30:10] RX: SysEx: Receiver Table - 0 devices 
           (F0 7D 03 00 F7)
```
No remote Nowdes detected yet.

```
[14:30:15] RX: SysEx: Receiver Table - 1 device(s): 
           Nowde-EEFF (player2)
           (F0 7D 03 01 AA BB CC DD EE FF 70 6C 61 79 65 72 32 ...)
```
One remote Nowde detected on layer "player2".

```
[14:30:20] RX: SysEx: Receiver Table - 2 device(s): 
           Nowde-EEFF (player2), Nowde-1234 (player1)
           (F0 7D 03 02 ...)
```
Two remote Nowdes detected on different layers.

## Understanding the Hex Bytes

### Bridge Connected
```
F0 7D 01 F7
│  │  │  └─ SysEx End
│  │  └──── Command: Bridge Connected (0x01)
│  └─────── Manufacturer ID (0x7D)
└────────── SysEx Start
```

### Subscribe to Layer "player2"
```
F0 7D 02 70 6C 61 79 65 72 32 F7
│  │  │  └─────┬─────┘        └─ SysEx End
│  │  │        └─────────────────── "player2" in ASCII
│  │  └──────────────────────────── Command: Subscribe (0x02)
│  └─────────────────────────────── Manufacturer ID (0x7D)
└────────────────────────────────── SysEx Start
```

### Receiver Table
```
F0 7D 03 01 AA BB CC DD EE FF 70 6C 61 79 65 72 32 00... F7
│  │  │  │  └─────┬──────┘  └──────┬──────┘              └─ End
│  │  │  │        │                 └─ Layer name (16 bytes)
│  │  │  │        └─ MAC address (6 bytes)
│  │  │  └─ Device count (1 device)
│  │  └──── Command: Receiver Table (0x03)
│  └─────── Manufacturer ID (0x7D)
└────────── SysEx Start
```

## Auto-Scroll Feature
- Logs automatically scroll to show latest messages
- Keeps last 1000 lines to prevent memory overflow
- Older messages are automatically trimmed

## Tips

### For Debugging
1. Look for TX messages to confirm commands were sent
2. Look for RX messages to confirm responses received
3. Check hex bytes if human-readable format doesn't match expectations
4. Timestamps help correlate events

### For Monitoring
1. Watch for Receiver Table messages to see remote Nowdes joining/leaving
2. Device count changes indicate network activity
3. Layer names show which Nowdes are subscribed to which layers

### Common Issues
- **No TX messages**: Check if Nowde is connected (USB status)
- **No RX messages**: Check if Nowde firmware is running ESP-NOW
- **Garbled hex**: Possible MIDI buffer corruption (rare)
- **Missing devices in table**: Check remote Nowde ESP-NOW beacons
