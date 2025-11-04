# OTA Firmware Upgrade

## Overview

The MilluBridge system now supports **Over-The-Air (OTA)** firmware upgrades for Nowde devices via USB MIDI. This eliminates the need for physical BOOT button access and makes firmware updates seamless.

## How It Works

### Architecture

1. **Bridge Application** (Python)
   - Downloads firmware from GitHub
   - Sends firmware to Nowde via SysEx messages
   - Shows progress in GUI

2. **Nowde Firmware** (ESP32-S3)
   - Receives firmware chunks via MIDI
   - Writes to secondary app partition using ESP32 Update library
   - Validates and reboots to new firmware

### Protocol

Three SysEx commands are used:

#### 1. OTA_BEGIN (0x05)
```
F0 7D 05 [size(4 bytes, 7-bit encoded)] F7
```
- Tells Nowde to prepare for firmware update
- Size is the total firmware size in bytes
- Nowde begins Update.begin() to prepare flash

#### 2. OTA_DATA (0x06)
```
F0 7D 06 [data(7-bit encoded)] F7
```
- Sends firmware data in chunks
- Each chunk is ~200 bytes raw (~230 bytes encoded)
- Nowde writes to flash partition
- Multiple DATA messages sent until complete

#### 3. OTA_END (0x07)
```
F0 7D 07 F7
```
- Finalizes the firmware update
- Nowde validates firmware and reboots
- Device boots with new firmware

### 7-bit Encoding

MIDI SysEx cannot contain bytes 0x80-0xFF, so all binary data is 7-bit encoded:
- Every 7 bytes becomes 8 bytes
- MSBs are packed into first byte
- Remaining bytes are 7-bit safe (0x00-0x7F)

## Usage

### From Bridge GUI

1. Connect to Nowde device
2. Click "Upgrade Firmware" button
3. Watch progress bar
4. Device automatically reboots with new firmware

### Process Timeline

```
[Download]     10%  - Download firmware.bin from GitHub
[OTA BEGIN]    15%  - Send firmware size to Nowde
[OTA DATA]  15-90%  - Upload firmware in chunks
[OTA END]      95%  - Finalize and validate
[Reboot]      100%  - Device reboots automatically
```

## Implementation Details

### ESP32 Partition Scheme

The platformio.ini uses `default_16MB.csv` partition scheme which provides:
- OTA_0: Primary app partition
- OTA_1: Secondary app partition (for updates)
- Factory partition (fallback)

### Firmware Size

Current firmware is ~923 KB, sent in:
- ~200 byte chunks (raw data)
- ~230 byte SysEx messages (after encoding + headers)
- Total: ~4,600 messages
- Transfer time: ~46 seconds at 10ms per chunk

### Error Handling

- Download failures: Network errors caught, device remains functional
- OTA failures: Update aborted, device stays on current firmware
- Validation failures: Device rolls back to previous firmware

## Advantages Over Bootloader Method

1. ✅ **No Physical Access**: No BOOT button required
2. ✅ **No Serial Drivers**: Works entirely over USB MIDI
3. ✅ **No External Tools**: No esptool or PlatformIO needed
4. ✅ **Graceful Fallback**: Device stays operational if update fails
5. ✅ **Progress Reporting**: Real-time progress shown in GUI
6. ✅ **Cross-Platform**: Same process on macOS, Linux, Windows

## Future Enhancements

- [ ] Firmware version checking before download
- [ ] Delta updates (only changed sectors)
- [ ] Batch updates (multiple devices simultaneously)
- [ ] ESP-NOW OTA (wireless updates to all receivers)

## Technical References

- ESP32 OTA Documentation: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/ota.html
- MIDI SysEx Specification: https://www.midi.org/specifications
- 7-bit Encoding: Custom implementation in `output_manager.py` and `sysex.cpp`

