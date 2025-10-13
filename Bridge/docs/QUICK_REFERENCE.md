# Quick Reference: Layer Management

## For End Users

### How to Set Up a Receiver for the First Time

1. **Power on receiver**
2. **Connect sender to Bridge via USB**
3. **Wait for receiver to appear in Remote Nowdes table**
4. **Click on Layer field** for that receiver
5. **Type layer name** (e.g., "player1")
6. **Press Enter**

✅ Done! Receiver will remember this layer forever (even after power loss)

### How to Change a Receiver's Layer

Same as above - just edit the Layer field in the table and press Enter.

### Understanding State Colors

| Color | Meaning |
|-------|---------|
| **Green (ACTIVE)** | Receiver is online and working |
| **Dark Red (MISSING)** | Receiver was seen but now offline/out of range |

---

## For Developers

### SysEx Protocol Quick Ref

| Command | Hex | Format | Purpose |
|---------|-----|--------|---------|
| Bridge Connected | `0x01` | `F0 7D 01 F7` | Start sender mode |
| Subscribe Layer | `0x02` | `F0 7D 02 [layer] F7` | Set receiver layer (USB) |
| Receiver Table | `0x03` | `F0 7D 03 [entries...] F7` | Report all receivers |
| Change Receiver Layer | `0x04` | `F0 7D 04 [MAC(6)] [layer(16)] F7` | Change specific receiver |

### EEPROM Functions (ESP32)

```cpp
// Save layer
saveLayerToEEPROM("player1");

// Load layer (returns "-" if none saved)
String layer = loadLayerFromEEPROM();
```

### Python Bridge API

```python
# Send layer change command
output_manager.send_change_receiver_layer("AA:BB:CC:DD:EE:FF", "player1")

# GUI callback
def on_layer_changed(self, mac_address, new_layer):
    # Called when user edits layer in table
```

---

## Troubleshooting

### Receiver doesn't auto-start after reboot
**Solution:** Check serial output for "Auto-starting receiver mode". If not present, layer wasn't saved. Re-edit layer in GUI.

### Layer edit in GUI doesn't work
**Solution:** Ensure USB Status shows [OK]. Make sure you press Enter after typing.

### Receiver lost its layer after firmware update
**Solution:** EEPROM survives firmware updates UNLESS you erase flash. Just edit layer again in GUI.

---

## File Locations

| File | Purpose |
|------|---------|
| `Nowde/src/main.cpp` | ESP32 firmware with EEPROM support |
| `Bridge/src/main.py` | GUI with editable layer table |
| `Bridge/src/midi/output_manager.py` | SysEx message builder |
| `Bridge/IMPLEMENTATION_COMPLETE.md` | Full implementation summary |
| `Bridge/LAYER_CHANGE_FLOW.md` | Visual diagrams |
| `Bridge/TESTING_CHECKLIST.md` | Test procedures |

---

## Common Layer Names

Based on Millumin conventions:
- `player1`, `player2`, `player3`, etc.
- `main`, `backup`, `overlay`
- `video1`, `audio1`, `fx1`

**Note:** Layer names are case-sensitive and limited to 16 characters.

---

## Architecture Overview

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  Millumin    │         │    Bridge    │         │ Sender Nowde │
│   (OSC)      │────────>│   (Python)   │<────USB>│              │
└──────────────┘         └──────────────┘         └──────────────┘
                                                          │
                                                       ESP-NOW
                                                          │
                                              ┌───────────┴───────────┐
                                              ▼                       ▼
                                    ┌──────────────┐      ┌──────────────┐
                                    │  Receiver 1  │      │  Receiver 2  │
                                    │ Layer: "p1"  │      │ Layer: "p2"  │
                                    │ [EEPROM]     │      │ [EEPROM]     │
                                    └──────────────┘      └──────────────┘
```

---

## Version History

### Current Version
- ✅ EEPROM persistence
- ✅ GUI editing
- ✅ Auto-start on boot
- ✅ Status tracking (Active/Missing)
- ✅ Version reporting

### Previous Version
- ⚠️ No persistence (layer lost on reboot)
- ⚠️ Manual USB commands only
- ⚠️ Receivers removed on timeout

---

## Contact & Support

For issues or questions:
1. Check serial debug output (115200 baud)
2. Review `TESTING_CHECKLIST.md`
3. Check `LAYER_CHANGE_FLOW.md` for message flow
4. Review `IMPLEMENTATION_COMPLETE.md` for details
