# MilluBridge User Guide

Complete guide to using MilluBridge for media synchronization.

---

## Bridge GUI Overview

### Main Window Sections

#### 1. **Millumin Settings**
- **OSC Address**: `127.0.0.1` (localhost)
- **OSC Port**: `8000` (default)
- **OSC Status**: [OK] when receiving messages

#### 2. **Media Sync Settings**
- **Throttle (Hz)**: 1-60 Hz (default 10 Hz) - Update frequency
- **MTC Framerate**: Default 30fps - Match your video framerate
- **Freewheel Timeout**: Default 3.0s - Timeout before local playback
- **Desync Threshold**: Default 200ms - Max clock delta allowed

#### 3. **Millumin Layers** Table
Shows active layers from Millumin:
- **Layers**: Layer name (player1, player2, etc.)
- **State**: PLAYING (green) / STOPPED (gray)
- **Filename**: Current media file
- **Position**: Current playback position
- **Duration**: Total media duration

#### 4. **Local Nowde** (USB Connection)
- **USB Status**: [OK] when Sender connected
- **Device Name**: Shows "Nowde" device
- **Logs**: Toggle to show/hide SysEx communication

#### 5. **Remote Nowdes** Table
Shows all discovered receivers:
- **Nowde**: Device UUID (last 4 digits of MAC)
- **Version**: Firmware version
- **State**: ACTIVE (green) / MISSING (dark red)
- **Layer**: Assigned layer (click to edit)

---

## Common Tasks

### Assign Layer to Receiver

1. **Wait** for receiver to appear in Remote Nowdes table
2. **Click** Layer button for that receiver
3. **Modal opens** with two options:
   - **Select** from Millumin layers list (auto-populated)
   - **Type** custom layer name in text field
4. **Click** "Apply"
5. **Verify**: Layer button shows new assignment

**Note**: Layer is saved to receiver's EEPROM and survives power loss.

### Change Receiver Layer

Same process as assigning - just edit and click Apply. Old layer is overwritten.

### Monitor Synchronization

**OSC Logs** (Show Logs button):
- View incoming OSC messages from Millumin
- Filter: "Show All Messages" for debug, or only Millumin messages
- Auto-scrolls to latest

**Nowde Logs** (Show Logs button):
- SysEx TX/RX messages
- Media sync packets (every 10th logged to reduce spam)
- Connection status changes

**Millumin Layers Table**:
- See which layers are active
- Verify position updates
- Check media filenames

### Adjust Sync Performance

**When to change settings**:

| Scenario | Adjust | Value |
|----------|--------|-------|
| High network load | Throttle | Decrease (5 Hz) |
| Need faster sync | Throttle | Increase (30-60 Hz) |
| 24fps video | MTC Framerate | 24 |
| 25fps video (PAL) | MTC Framerate | 25 |
| Unstable network | Desync Threshold | Increase (500ms) |
| Very stable network | Desync Threshold | Decrease (100ms) |
| Long signal dropout acceptable | Freewheel Timeout | Increase (5-10s) |

---

## Media File Configuration

### Naming Convention

**Format**: `NNN_filename.ext`

**Examples**:
```
001_intro.mp4
002_main_scene.mov
050_transition.mp4
127_finale.mp4
```

**Index Parsing Rules**:
- 1-3 digits at start
- Underscore separator
- Range: 1-127 (MIDI limit)
- 0 reserved for stop

**Without Index**:
Files without index prefix are treated as index 0 (no CC#100 sent, only MTC).

### Layer Organization

**Recommended structure in Millumin**:

```
Layer "player1":
  - 001_intro.mp4
  - 002_segment_a.mov
  - 003_segment_b.mov

Layer "player2":
  - 001_background_loop.mp4
  - 002_overlay.mov

Layer "main":
  - 001_full_show.mp4
```

**Receiver Assignment**:
- Receiver-1 → Layer "player1"
- Receiver-2 → Layer "player2"  
- Receiver-3 → Layer "main"

---

## Understanding Status Indicators

### OSC Status

| Indicator | Color | Meaning |
|-----------|-------|---------|
| `[OK]` | Green | Receiving OSC from Millumin |
| `[X]` | Red | Not receiving OSC |
| Text | Gray | "Listening..." or connection details |

**Troubleshooting**:
- `[X]` Red → Check Millumin OSC feedback enabled
- Stays red → Verify IP/port (127.0.0.1:8000)

### USB Status (Local Nowde)

| Indicator | Color | Meaning |
|-----------|-------|---------|
| `[OK]` | Green | Sender connected via USB |
| `[X]` | Red | No Sender device found |

**Troubleshooting**:
- `[X]` Red → Check USB cable connected
- Still red → Use Native USB port, not UART
- Still red → Check `pio device list`

### Remote Nowdes State

| State | Color | Meaning |
|-------|-------|---------|
| ACTIVE | Green | Receiver online and responding |
| MISSING | Dark Red | Receiver was seen but now timeout |

**Behavior**:
- MISSING devices stay in table (can reconnect)
- Timeout: 5 seconds without beacon
- Automatic reconnection when back in range

---

## MIDI Output Reference

### CC#100 (Media Index)

**Purpose**: Identify which media is playing

**Values**:
- `0` = Stopped
- `1-127` = Media index from filename

**Sent**:
- On media change (index changes)
- On stop (value becomes 0)
- **NOT** sent repeatedly during playback (change detection)

### MTC (MIDI Time Code)

**Purpose**: Position synchronization

**Format**: 8 quarter-frame messages per frame

**Framerate**: 30fps non-drop (default, configurable)

**Encoding**:
```
Hours:Minutes:Seconds:Frames
HH:MM:SS:FF

Example: 00:02:15:20
= 2 minutes, 15 seconds, 20 frames
```

**Sent**:
- Continuously during playback (~30 times per second)
- Updates even in freewheel mode
- Stops when media stopped

---

## Advanced Usage

### Multiple Layers

**Scenario**: Control 3 screens independently

**Setup**:
1. Create layers in Millumin: `player1`, `player2`, `player3`
2. Assign receivers:
   - Receiver-1 → `player1`
   - Receiver-2 → `player2`
   - Receiver-3 → `player3`
3. Add different media to each layer
4. Play layers independently or synchronized

**Result**: Each receiver only responds to its assigned layer.

### Redundant Receivers

**Scenario**: Backup receiver for critical output

**Setup**:
1. Assign two receivers to same layer:
   - Receiver-1 → `main`
   - Receiver-2 → `main`
2. Connect both to MIDI splitter or different devices

**Result**: Both receivers output identical MIDI (synchronized).

### Custom Layer Names

**Use Cases**:
- `main` / `backup` - Redundancy
- `video` / `audio` / `lights` - Discipline-specific
- `front` / `rear` / `ceiling` - Location-based

**Requirements**:
- Max 16 characters
- ASCII only recommended
- Case-sensitive

---

## Workflow Examples

### Example 1: Simple Video Mapping

**Goal**: Single video projected on wall with synchronized MIDI lighting

**Setup**:
1. Millumin layer: `player1`
2. Add videos: `001_scene1.mp4`, `002_scene2.mp4`
3. Receiver assigned to `player1`
4. Receiver MIDI out → Lighting controller

**Operation**:
- Play `001_scene1.mp4`
- Receiver outputs CC#100=1 + MTC
- Lighting controller triggers Scene 1
- Switch to `002_scene2.mp4`
- CC#100 changes to 2, triggers Scene 2

### Example 2: Multi-Screen Installation

**Goal**: 4 screens with independent content, synchronized playback

**Setup**:
1. Millumin layers: `player1`, `player2`, `player3`, `player4`
2. 4 receivers, each assigned to corresponding layer
3. Each receiver connected to separate media player

**Operation**:
- Cue all layers at t=0
- All receivers receive position sync via MTC
- Frame-accurate playback across all screens
- Independent control of each screen's content

### Example 3: Show Control

**Goal**: Coordinate video + audio + lighting + effects

**Setup**:
1. Millumin layers:
   - `video` → Projector system
   - `audio` → Audio playback
   - `lighting` → DMX controller
   - `effects` → Special effects trigger
2. 4 receivers, one per discipline

**Operation**:
- Single timeline in Millumin controls all
- Each system receives only relevant media
- Perfect synchronization via MTC
- Media index triggers scenes/cues

---

## Best Practices

### Performance Optimization

1. **Reduce Throttle Rate** if network congested:
   - 10 Hz (default) → 5 Hz
   - Less network traffic, slightly less responsive

2. **Disable Logs** during show:
   - Hide OSC Logs
   - Hide Nowde Logs
   - Reduces CPU usage

3. **Limit Active Layers**:
   - Only use layers you need
   - Unused layers still consume Bridge resources

### Reliability

1. **Test Layer Assignments**:
   - Power cycle receivers after assignment
   - Verify layer remembered (EEPROM saved)

2. **Monitor Connection Status**:
   - Watch for MISSING receivers before show
   - Address connectivity issues early

3. **Use Burst Stop**:
   - Automatic (5 messages on stop)
   - Ensures receivers get stop command

4. **Freewheel Tolerance**:
   - Default 3s handles brief WiFi interference
   - Increase for unstable environments

### Network Best Practices

1. **Minimize Interference**:
   - Keep receivers away from WiFi routers
   - Avoid dense WiFi areas
   - ESP-NOW uses WiFi channels but different protocol

2. **Line of Sight**:
   - ESP-NOW range increases with clear path
   - Walls/metal reduce range significantly

3. **Test Range**:
   - Verify connectivity at installation distances
   - Add extra margin for safety

---

## Keyboard Shortcuts

Currently no keyboard shortcuts implemented.

Future enhancements may include:
- `Cmd/Ctrl + L`: Focus layer assignment
- `Cmd/Ctrl + R`: Refresh receivers
- `Cmd/Ctrl + H`: Toggle logs

---

## Tips & Tricks

**Tip 1**: Double-click layer button for quick reassignment

**Tip 2**: Use Millumin layer names directly for clarity

**Tip 3**: Test with single receiver first, then scale up

**Tip 4**: Name receivers physically (tape labels) matching table UUIDs

**Tip 5**: Keep spare receiver programmed as backup

**Tip 6**: Log throttling (every 10th) prevents spam - check serial for all messages

**Tip 7**: Bridge auto-connects to first "Nowde" device found

---

## Next Steps

- **[Architecture](ARCHITECTURE.md)** - Understand protocols
- **[Developer Guide](DEVELOPER_GUIDE.md)** - Customize system
- **[Troubleshooting](TROUBLESHOOTING.md)** - Fix issues
