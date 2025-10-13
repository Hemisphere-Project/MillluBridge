# Quick Reference: SysEx Logging in Bridge

## 📍 Where to Find Logs

**Bridge GUI** → **Local Nowde** section → Click **"Show Logs"** button → **Nowde Logs** section appears

## 🔤 Log Format

```
[HH:MM:SS] TX/RX: <Message Description> (<Hex Bytes>)
```

- **TX** = Transmitted (Bridge → Nowde)
- **RX** = Received (Nowde → Bridge)
- **Timestamp** = When message was sent/received
- **Description** = Human-readable message type
- **Hex Bytes** = Raw SysEx data for debugging

## 📨 Message Types

### 1. Bridge Connected (TX)
```
[14:30:00] TX: SysEx: Bridge Connected (F0 7D 01 F7)
```
**When:** Automatically sent when Nowde USB is connected  
**Purpose:** Activates sender mode on Nowde

### 2. Subscribe to Layer (TX)
```
[14:30:05] TX: SysEx: Subscribe to Layer 'player2' (F0 7D 02 70 6C 61 79 65 72 32 F7)
```
**When:** User enters layer name and clicks "Subscribe" button  
**Purpose:** Activates receiver mode, Nowde listens for that layer

### 3. Receiver Table (RX)
```
[14:30:10] RX: SysEx: Receiver Table - 2 device(s): Nowde-EEFF (player2), Nowde-1234 (player1) (F0 7D 03 02 ...)
```
**When:** Sent by Nowde every ~5 seconds when in sender mode  
**Purpose:** Reports which remote Nowdes are detected via ESP-NOW

## 🔍 What to Look For

### ✅ Normal Operation
- TX: Bridge Connected appears when Nowde connects
- TX: Subscribe to Layer appears when you click Subscribe
- RX: Receiver Table appears periodically (every 5s)
- Device count changes as remote Nowdes join/leave

### ⚠️ Troubleshooting
- **No TX messages** → Nowde not connected (check USB Status)
- **No RX messages** → Nowde firmware not running / ESP-NOW not active
- **Empty Receiver Table (0 devices)** → No remote Nowdes broadcasting beacons
- **Devices disappearing from table** → Remote Nowde timeout (60s no beacon)

## 🧪 Test It

Run test script to verify formatting:
```bash
cd /Users/hmini25/Documents/MillluBridge/Bridge
.venv/bin/python test_sysex_logging.py
```

## 📚 Documentation Files

- **`SYSEX_LOGGING_SUMMARY.md`** - Complete implementation summary
- **`SYSEX_LOGGING.md`** - Technical details
- **`NOWDE_LOGS_REFERENCE.md`** - Visual examples and hex breakdown
- **`test_sysex_logging.py`** - Test script

## 💡 Pro Tips

1. **Hex bytes** are included for deep debugging - you can decode them manually if needed
2. **Auto-scroll** keeps latest messages visible
3. **1000 line limit** prevents memory overflow
4. **Timestamps** help correlate Bridge actions with Nowde serial logs
5. **Device names** in Receiver Table are auto-generated from MAC address last 2 bytes

## 🎯 Common Workflows

### Setup Remote Nowde Network
1. Connect Nowde #1 via USB → See "TX: Bridge Connected"
2. Connect Nowde #2 standalone → Should appear in Receiver Table
3. Subscribe Nowde #2 to layer → Enter "player2", click Subscribe → See "TX: Subscribe to Layer"
4. Monitor "RX: Receiver Table" to confirm network activity

### Debug Communication Issues
1. Check TX messages → Confirm commands are being sent
2. Check RX messages → Confirm responses received
3. Compare timestamps → Measure latency
4. Check hex bytes → Verify protocol format
5. Cross-reference with Nowde serial logs

---

**Everything is logged automatically - just open the logs and watch! 🚀**
