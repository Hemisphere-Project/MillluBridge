# Testing Checklist: Layer Persistence & GUI Editing

## Pre-Test Setup
- [ ] Flash updated firmware to Nowde devices (both Sender and Receivers)
- [ ] Start Bridge application on computer
- [ ] Connect Sender Nowde via USB
- [ ] Power on at least one Receiver Nowde

## Test 1: EEPROM Persistence (First Time)

### Steps
1. [ ] Open Bridge application
2. [ ] Wait for Sender to connect (USB Status: [OK])
3. [ ] Wait for receiver(s) to appear in Remote Nowdes table
4. [ ] Note the current Layer value (should be "-" or DEFAULT_RECEIVER_LAYER)
5. [ ] Click on Layer field for a receiver
6. [ ] Type a new layer name (e.g., "player1")
7. [ ] Press Enter

### Expected Results
- [ ] Nowde Logs show: "TX: SysEx: Change Receiver Layer MAC=xx:xx:xx:xx:xx:xx, Layer='player1'"
- [ ] Remote Nowdes table updates to show new layer "player1"
- [ ] Receiver serial output shows: "Layer saved to EEPROM: player1"

## Test 2: EEPROM Persistence (After Reboot)

### Steps
1. [ ] Power cycle the receiver (disconnect and reconnect power)
2. [ ] Watch receiver's serial output during boot

### Expected Results
- [ ] Serial shows: "[INIT] Auto-starting receiver mode"
- [ ] Serial shows: "Subscribed Layer: player1"
- [ ] Serial shows: "Source: EEPROM"
- [ ] Remote Nowdes table in Bridge shows layer "player1" (after discovery)

## Test 3: Multiple Receivers

### Steps
1. [ ] Power on multiple receivers (at least 2)
2. [ ] Wait for all to appear in Remote Nowdes table
3. [ ] Edit Layer for first receiver to "player1", press Enter
4. [ ] Edit Layer for second receiver to "player2", press Enter
5. [ ] Power cycle both receivers
6. [ ] Wait for them to reappear in Bridge

### Expected Results
- [ ] First receiver auto-starts with "player1"
- [ ] Second receiver auto-starts with "player2"
- [ ] GUI table shows correct layers for each receiver
- [ ] Each receiver only processes MIDI for its subscribed layer

## Test 4: Empty Layer Name (Error Handling)

### Steps
1. [ ] Click on Layer field for a receiver
2. [ ] Delete all text (make it empty)
3. [ ] Press Enter

### Expected Results
- [ ] Bridge shows error: "Error: Layer name cannot be empty"
- [ ] Layer field reverts to previous value
- [ ] No SysEx message sent

## Test 5: Layer Name Truncation

### Steps
1. [ ] Click on Layer field for a receiver
2. [ ] Type a very long layer name (more than 16 characters): "verylonglayername123456"
3. [ ] Press Enter

### Expected Results
- [ ] Layer name is truncated to 16 characters: "verylonglayerna"
- [ ] SysEx message sent with truncated name
- [ ] Receiver saves truncated name to EEPROM

## Test 6: State Indicators (Active/Missing)

### Steps
1. [ ] With receiver powered on, verify State shows "ACTIVE" (green)
2. [ ] Power off receiver
3. [ ] Wait for timeout period (typically 20-30 seconds)
4. [ ] Observe State change

### Expected Results
- [ ] State changes from "ACTIVE" (green) to "MISSING" (dark red)
- [ ] Receiver row remains in table (not removed)
- [ ] UUID, Version, and Layer text changes to dark red color

## Test 7: Millumin Integration

### Steps
1. [ ] Configure two receivers with different layers: "player1" and "player2"
2. [ ] In Millumin, create layers named "player1" and "player2"
3. [ ] Play media in "player1" layer
4. [ ] Observer which receiver(s) receive MIDI

### Expected Results
- [ ] Only receiver subscribed to "player1" receives MIDI messages
- [ ] Receiver subscribed to "player2" does NOT receive messages
- [ ] Bridge Nowde Logs show MIDI output for "player1" layer

## Test 8: Changing Layer While Playing

### Steps
1. [ ] Start Millumin playing media in "player1" layer
2. [ ] Receiver is subscribed to "player1" and receiving MIDI
3. [ ] In Bridge GUI, change receiver's layer to "player2"
4. [ ] Continue playing "player1" in Millumin

### Expected Results
- [ ] Receiver immediately stops receiving MIDI for "player1"
- [ ] Layer change is saved to EEPROM
- [ ] Play media in "player2" layer, receiver now receives MIDI

## Test 9: USB Disconnect/Reconnect

### Steps
1. [ ] With Bridge running and receivers active
2. [ ] Disconnect Sender Nowde USB cable
3. [ ] Wait 5 seconds
4. [ ] Reconnect USB cable

### Expected Results
- [ ] USB Status changes from [OK] to [X] to [OK]
- [ ] Bridge sends "Bridge Connected" SysEx on reconnect
- [ ] Receiver table repopulates within a few seconds
- [ ] All layer values preserved in GUI table

## Test 10: Default Layer Behavior

### Steps
1. [ ] Flash a new/erased receiver (EEPROM cleared)
2. [ ] Power on receiver without sending any layer commands
3. [ ] Check receiver serial output

### Expected Results
- [ ] loadLayerFromEEPROM() returns DEFAULT_RECEIVER_LAYER ("-")
- [ ] Receiver does NOT auto-start receiver mode (layer is "-")
- [ ] Serial shows: "Waiting for USB MIDI commands..."

## Test 11: Concurrent Edits

### Steps
1. [ ] Have 3+ receivers active in Remote Nowdes table
2. [ ] Quickly edit layers for all receivers in sequence:
   - Receiver 1: "player1" → Enter
   - Receiver 2: "player2" → Enter
   - Receiver 3: "player3" → Enter
3. [ ] Do not wait between edits

### Expected Results
- [ ] All SysEx commands are queued and sent
- [ ] All receivers update their layers
- [ ] All receivers save to EEPROM correctly
- [ ] GUI table reflects all changes

## Test 12: Special Characters in Layer Names

### Steps
1. [ ] Try various layer names:
   - "player-1" (with dash)
   - "player_2" (with underscore)
   - "player 3" (with space)
   - "PLAYER4" (uppercase)
   - "123layer" (starts with number)

### Expected Results
- [ ] All ASCII characters are accepted
- [ ] Names are saved and restored correctly
- [ ] No crashes or errors
- [ ] Layer matching works with Millumin layer names

## Troubleshooting Reference

### Issue: Receiver doesn't auto-start after reboot
**Check:**
- [ ] Look for "Layer saved to EEPROM" message in serial output
- [ ] Verify saved layer is not "-" or empty
- [ ] Check ESP32 Preferences library is included
- [ ] Ensure NVS partition is available in platformio.ini

### Issue: GUI edit doesn't send SysEx
**Check:**
- [ ] USB Status shows [OK] (Sender connected)
- [ ] Press Enter after typing layer name
- [ ] Check Nowde Logs for error messages
- [ ] Verify MAC address format is correct

### Issue: Layer not saved to EEPROM
**Check:**
- [ ] Serial output shows "Layer saved to EEPROM: [layer_name]"
- [ ] Check if Preferences.begin() succeeds
- [ ] Verify ESP32 has sufficient NVS space
- [ ] Try erasing flash and reflashing firmware

### Issue: Remote Nowdes table not updating
**Check:**
- [ ] Receiver is broadcasting info via ESP-NOW
- [ ] Sender is receiving ESP-NOW messages
- [ ] Bridge is receiving SysEx 0x03 (Receiver Table)
- [ ] Check input_manager has ignore_types(sysex=False)

## Success Criteria

All tests pass if:
1. ✅ Layers persist across power cycles
2. ✅ GUI editing works for all receivers
3. ✅ EEPROM saves and loads correctly
4. ✅ Auto-start works on boot
5. ✅ State indicators show correct status
6. ✅ No crashes or data corruption
7. ✅ SysEx commands are properly formatted
8. ✅ ESP-NOW communication is reliable

## Notes Section
Use this space to record any observations or issues during testing:

---

---

---

