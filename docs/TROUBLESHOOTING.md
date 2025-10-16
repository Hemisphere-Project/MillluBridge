# Troubleshooting Guide

Common issues, solutions, and debugging procedures for MilluBridge.

---

## Quick Diagnostics

### Bridge Not Seeing Nowde

**Symptom**: No devices appear in Bridge GUI

**Check**:
1. USB cable connected?
2. Device shows in system USB list?
   - macOS: `ls /dev/cu.usbserial*`
   - Windows: Device Manager → Ports (COM & LPT)
3. Correct MIDI port selected in Bridge?
4. Serial monitor shows boot messages?

**Fix**:
- Try different USB port
- Reinstall USB drivers (see Getting Started)
- Disconnect/reconnect USB cable
- Restart Bridge application

---

### No MIDI Output from Receiver

**Symptom**: Receiver connected but no MIDI output

**Checklist**:
- [ ] Receiver layer matches OSC layer name exactly
- [ ] DAW/software receiving MIDI from correct port?
- [ ] Millumin sending OSC to port 8000?
- [ ] Media filename has index prefix (e.g., `001_video.mp4`)?
- [ ] Serial monitor shows `[MIDI TX]` messages?

**Debug**:
```bash
# Check receiver serial output
cd Nowde
pio device monitor --port /dev/cu.usbserial-XXX

# Look for:
[MEDIA SYNC] Layer='layer1', Index=1, Pos=5000ms, State=playing
[MIDI TX] CC#100=1
[MIDI TX] MTC: 00:00:05:00
```

**Common causes**:
- Layer name mismatch (case-sensitive!)
- Media filename missing index prefix
- MIDI port not connected in DAW

---

### Sender Not Forwarding to Receivers

**Symptom**: Sender receives data but receivers get nothing

**Check ESP-NOW**:
1. Sender shows in Bridge GUI as "Connected"?
2. Receivers registered in sender table?
3. Serial monitor shows `[ESP-NOW TX]` messages?

**Debug sender**:
```
[ESP-NOW RX] Media Sync from bridge: layer='layer1'
[ESP-NOW TX] Media Sync #10 to 2 receivers
```

**Debug receiver**:
```
[ESP-NOW RX] Media Sync from sender XX:XX:XX:XX:XX:XX
```

**Fixes**:
- Verify Wi-Fi channel matches (both 2.4 GHz)
- Check distance (ESP-NOW range ~100m clear line of sight)
- Ensure both sender/receiver using same firmware version
- Power cycle both devices

---

### Layer Changes Not Persisting

**Symptom**: Receiver forgets layer after power cycle

**Expected behavior**: Layer saved to EEPROM, restored on boot

**Check serial output**:
```
[EEPROM] Layer saved: layer1
[EEPROM] Layer loaded: layer1
```

**If not appearing**:
- EEPROM may be corrupted
- Flash with `pio run --target erase` then re-upload firmware

**Manual test**:
```cpp
// Add to setup() temporarily:
DEBUG_SERIAL.println("[TEST] Saved layer: " + loadLayerFromEEPROM());
```

---

### MTC Timing Drift

**Symptom**: Video and audio gradually desync

**Expected drift**: < 50ms over 10 minutes with stable OSC feed

**Causes**:
1. **Freewheel mode activated**: No OSC updates for >3 seconds
2. **Clock desync**: Network latency >200ms
3. **OSC throttling**: Millumin sending <10 updates/second

**Check receiver serial**:
```
[MEDIA SYNC] WARNING: Clock desync 250ms, adjusting
[MEDIA SYNC] Freewheel mode activated
```

**Fixes**:
- Increase freewheel timeout (GUI: "Freewheel Timeout")
- Reduce clock desync threshold (GUI: "Desync Threshold")
- Check network stability
- Verify Millumin OSC output rate (should be 10+ Hz)

---

### Bridge CPU Spikes

**Symptom**: Bridge uses high CPU / freezes

**Normal usage**: 3-5% CPU during playback

**Causes**:
- Throttle interval too low (< 10ms = 100 Hz)
- Too many OSC messages from Millumin
- Large receiver table (10+ receivers)

**Monitor**:
```bash
# macOS Activity Monitor
ps aux | grep python

# Linux/WSL
top -p $(pgrep -f "python.*main.py")
```

**Fixes**:
- Increase throttle interval (GUI: try 50ms = 20 Hz)
- Filter OSC messages in Millumin (send only active layers)
- Reduce receiver count

---

### SysEx Messages Not Received

**Symptom**: Bridge sends SysEx but Nowde doesn't respond

**Check serial output** (Nowde):
```
[SYSEX] Bridge Connected received
[SYSEX] Subscribe Layer received: layer1
```

**If not appearing**:
1. **MIDI port mismatch**: Bridge sending to wrong port
2. **SysEx blocked**: Some DAWs filter SysEx
3. **Buffer overflow**: Messages arriving too fast

**Test with USB directly connected**:
```python
# In Bridge, add debug print in send_bridge_connected():
print(f"Sending SysEx: {message}")
```

**Verify in serial monitor**:
- Should see `[SYSEX]` tag within 1 second
- If not, check MIDI port selection in Bridge

---

### ESP-NOW Packet Loss

**Symptom**: Intermittent dropouts, missing updates

**Expected**: < 1% packet loss in typical environment

**Check receiver serial**:
```
[ESP-NOW RX] Media Sync from sender XX:XX:XX:XX:XX:XX
```

**If frequent gaps**:
- **Distance**: Move sender closer to receivers
- **Interference**: Check for Wi-Fi congestion (2.4 GHz)
- **Power**: Use powered USB hub (not computer USB)

**Advanced check** (add to Nowde):
```cpp
static int packetsReceived = 0;
static int packetsExpected = 0;
void onDataReceived(...) {
  packetsReceived++;
  if (millis() % 10000 == 0) {
    Serial.printf("[STATS] RX: %d/%d (%.1f%%)\n", 
      packetsReceived, packetsExpected, 
      100.0 * packetsReceived / packetsExpected);
  }
}
```

---

### "Device Communication Lost"

**Symptom**: Receiver shows as "Missing" in sender table

**Timeout**: 5 seconds without beacon → marked missing

**Check**:
- Receiver still powered?
- Serial monitor shows `[ESP-NOW TX] Receiver info`?
- Sender shows `[ESP-NOW RX] Receiver beacon`?

**Debug**:
```
# Receiver should send every ~1 second:
[ESP-NOW TX] Receiver info: layer=layer1

# Sender should receive:
[ESP-NOW RX] Receiver beacon from XX:XX:XX:XX:XX:XX
```

**Fixes**:
- Power cycle receiver
- Move closer to sender
- Check for Wi-Fi interference
- Verify both on same channel

---

## Error Messages Reference

### Bridge Errors

| Message | Meaning | Solution |
|---------|---------|----------|
| `No MIDI ports available` | No USB MIDI devices found | Connect Nowde, check drivers |
| `Failed to send SysEx` | MIDI output error | Check port selection, restart Bridge |
| `OSC server error: Address already in use` | Port 8000 in use | Close other apps using port 8000 |

### Nowde Serial Errors

| Message | Meaning | Solution |
|---------|---------|----------|
| `[ERROR] ESP-NOW init failed` | Wi-Fi initialization failed | Power cycle device |
| `[ERROR] ESP-NOW send failed` | Transmission error | Check distance, interference |
| `[WARN] Unknown SysEx command` | Invalid/corrupted SysEx | Check Bridge version compatibility |
| `[WARN] Receiver table full` | Max 10 receivers registered | Remove old entries, restart sender |

---

## Performance Issues

### Latency Too High

**Target**: < 50ms Bridge → Receiver MIDI output

**Measure**:
1. Note timestamp in Millumin OSC message
2. Check Bridge serial: time of `send_media_sync()`
3. Check Receiver serial: time of `[MIDI TX]`

**If > 100ms**:
- Reduce throttle interval
- Check network latency (OSC over Ethernet preferred)
- Reduce ESP-NOW distance

### Memory Leaks (Nowde)

**Symptom**: Device crashes after hours/days

**Monitor**:
```cpp
// Add to loop():
if (millis() % 60000 == 0) {  // Every minute
  Serial.printf("[HEAP] Free: %d bytes\n", ESP.getFreeHeap());
}
```

**Expected**: Stable ~200-250 KB free

**If decreasing**:
- Update to latest firmware
- Check for String concatenation in loops
- Report as bug with serial log

---

## Common Questions

### Q: Can I use multiple senders?

**A**: Not currently supported. Workaround: Use separate Bridge instances on different USB ports.

---

### Q: Maximum number of receivers?

**A**: 10 per sender (firmware limit). Can be increased by editing `MAX_RECEIVERS` in `main.cpp`.

---

### Q: Can I use 5 GHz Wi-Fi?

**A**: No, ESP-NOW only supports 2.4 GHz.

---

### Q: Do I need Wi-Fi router?

**A**: No! ESP-NOW works peer-to-peer without router/internet.

---

### Q: Can I change MIDI channel?

**A**: Yes, edit `sendMIDICC100()` and MTC functions in `main.cpp`. See Developer Guide.

---

### Q: Why media index 0-127 limit?

**A**: MIDI CC values are 7-bit (0-127). Use media index in filename prefix.

---

### Q: Can receivers talk to each other?

**A**: No, only sender → receiver communication is implemented.

---

## Advanced Debugging

### Capture SysEx with MIDI Monitor

**macOS**: Use MIDI Monitor app
**Windows**: Use MIDI-OX

**Look for**:
- Manufacturer ID: `7D`
- Command bytes: `01`, `02`, `04`, `05`
- Proper termination: `F7`

### Analyze ESP-NOW Packets

**Add to Nowde** (sender):
```cpp
void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.printf("[ESP-NOW DEBUG] Sent to %02X:%02X:%02X:%02X:%02X:%02X, Status: %s\n",
    mac_addr[0], mac_addr[1], mac_addr[2], mac_addr[3], mac_addr[4], mac_addr[5],
    status == ESP_NOW_SEND_SUCCESS ? "OK" : "FAIL");
}
```

**Add to Nowde** (receiver):
```cpp
void onDataReceived(...) {
  Serial.printf("[ESP-NOW DEBUG] Received %d bytes, Type: 0x%02X\n", len, incomingData[0]);
}
```

### Profile Bridge Performance

```python
import cProfile
import pstats

# Run Bridge with profiler
profiler = cProfile.Profile()
profiler.enable()

# ... run application ...

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

---

## Getting Help

### Before Reporting Issues

1. Check this troubleshooting guide
2. Review serial output from both Bridge and Nowde
3. Test with minimal setup (1 sender + 1 receiver)
4. Update to latest firmware

### What to Include in Bug Reports

- **Bridge version**: Check `About` in GUI
- **Nowde version**: Check serial output at boot
- **OS**: macOS/Windows/Linux + version
- **Hardware**: ESP32 model (usually ESP32-WROOM-32)
- **Steps to reproduce**: Detailed sequence
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Serial logs**: Both sender and receiver
- **Bridge console output**: If running from terminal

### Contact

- GitHub Issues: [MilluBridge Issues](https://github.com/Hemisphere-Project/MilluBridge/issues)
- Documentation: See `docs/` folder
- Developer Guide: For API reference and customization

---

## Reset Procedures

### Full Reset (Receiver)

1. **Erase EEPROM**:
   ```bash
   cd Nowde
   pio run --target erase
   ```

2. **Re-upload firmware**:
   ```bash
   pio run --target upload --upload-port /dev/cu.usbserial-XXX
   ```

3. **Verify**:
   ```
   [EEPROM] Layer loaded: - (default)
   ```

### Reset Sender Table

**Power cycle sender** → Table clears, receivers re-register automatically within 5 seconds.

### Factory Reset (Bridge)

**Delete settings**:
- macOS: `~/Library/Application Support/MilluBridge/`
- Windows: `%APPDATA%\MilluBridge\`
- Linux: `~/.config/MilluBridge/`

Then restart Bridge → defaults restored.

---

## Known Limitations

1. **Single sender only**: Multiple senders will conflict
2. **MIDI channel 1 fixed**: Requires code change for others
3. **10 receiver limit**: Increase `MAX_RECEIVERS` to expand
4. **2.4 GHz only**: ESP-NOW limitation
5. **No bi-directional feedback**: Receivers can't report back to Millumin
6. **Media index 1-127**: MIDI 7-bit limitation

See Developer Guide for workarounds and future enhancements.
