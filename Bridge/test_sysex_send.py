#!/usr/bin/env python3
# MilluBridge - SysEx Send Test
# Copyright (C) 2025 maigre - Hemisphere Project
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Test script to verify Bridge can send SysEx to Nowde
Run this with Nowde connected and serial monitor open
"""

import sys
import time
sys.path.insert(0, 'src')

from midi.output_manager import OutputManager

def test_sysex_sending():
    """Test sending SysEx messages to Nowde"""
    print("=" * 60)
    print("SysEx Sending Test")
    print("=" * 60)
    
    # Create output manager
    om = OutputManager()
    
    # List available ports
    ports = om.get_ports()
    print(f"\nAvailable MIDI ports:")
    for i, port in enumerate(ports):
        print(f"  {i+1}. {port}")
    
    # Find Nowde port
    nowde_port = None
    for port in ports:
        if port.startswith("Nowde"):
            nowde_port = port
            break
    
    if not nowde_port:
        print("\n❌ ERROR: No Nowde device found!")
        print("Make sure Nowde is connected via USB")
        return False
    
    print(f"\n✓ Found Nowde device: {nowde_port}")
    
    # Open port
    if not om.open_port(nowde_port):
        print(f"❌ ERROR: Failed to open port {nowde_port}")
        return False
    
    print(f"✓ Opened MIDI port")
    
    # Test 1: Send Bridge Connected
    print("\n" + "-" * 60)
    print("Test 1: Sending Bridge Connected SysEx")
    print("-" * 60)
    
    message = [0xF0, 0x7D, 0x01, 0xF7]
    print(f"Message bytes: {' '.join(f'{b:02X}' for b in message)}")
    print(f"Expected on Nowde serial:")
    print(f"  [MIDI RX] Header: 0x04, Bytes: F0 7D 01")
    print(f"  [SYSEX] CIN=0x4, Processing bytes...")
    print(f"  [SYSEX] Start detected (F0)")
    print(f"  [MIDI RX] Header: 0x05, Bytes: F7 00 00")
    print(f"  [SYSEX] End detected (F7), length=4 bytes")
    print(f"  [SYSEX] Data: F0 7D 01 F7")
    print(f"  === SENDER MODE ACTIVATED ===")
    
    om.midi_out.send_message(message)
    print(f"\n✓ Sent Bridge Connected")
    print(f"Check Nowde serial monitor for logs...")
    
    time.sleep(2)
    
    # Test 2: Send Subscribe to Layer
    print("\n" + "-" * 60)
    print("Test 2: Sending Subscribe to Layer 'player2' SysEx")
    print("-" * 60)
    
    layer_name = "player2"
    layer_bytes = layer_name.encode('ascii')
    message = [0xF0, 0x7D, 0x02] + list(layer_bytes) + [0xF7]
    print(f"Message bytes: {' '.join(f'{b:02X}' for b in message)}")
    print(f"Layer name: {layer_name}")
    print(f"Expected on Nowde serial:")
    print(f"  [MIDI RX] messages for each packet...")
    print(f"  [SYSEX] Data: F0 7D 02 70 6C 61 79 65 72 32 F7")
    print(f"  === RECEIVER MODE ACTIVATED ===")
    print(f"  Layer: player2")
    
    om.midi_out.send_message(message)
    print(f"\n✓ Sent Subscribe to Layer")
    print(f"Check Nowde serial monitor for logs...")
    
    time.sleep(1)
    
    # Close port
    om.close_port()
    
    print("\n" + "=" * 60)
    print("✅ Test completed successfully!")
    print("=" * 60)
    print("\nNEXT STEPS:")
    print("1. Check Nowde serial monitor output")
    print("2. Look for [MIDI RX] and [SYSEX] log messages")
    print("3. If no logs appear, the issue is likely:")
    print("   - USB cable/connection problem")
    print("   - Nowde not running latest firmware")
    print("   - Serial monitor not connected to correct port")
    print("4. If logs appear but no mode activation:")
    print("   - SysEx parsing issue in Nowde firmware")
    print("   - Check [SYSEX] Data: line matches expected bytes")
    
    return True

if __name__ == '__main__':
    print("\nMake sure:")
    print("  1. Nowde is connected via USB")
    print("  2. Nowde has latest firmware uploaded")
    print("  3. Serial monitor is running (screen or platformio monitor)")
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(0)
    
    test_sysex_sending()
