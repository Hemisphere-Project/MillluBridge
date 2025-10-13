#!/usr/bin/env python3
"""Test SysEx logging functionality"""

import sys
sys.path.insert(0, 'src')

from midi.output_manager import OutputManager
from midi.input_manager import InputManager

def test_output_formatting():
    """Test output SysEx formatting"""
    print("Testing Output SysEx Formatting:")
    print("-" * 60)
    
    om = OutputManager()
    
    # Test Bridge Connected
    message1 = [0xF0, 0x7D, 0x01, 0xF7]
    formatted1 = om.format_sysex_message(message1)
    print(f"Bridge Connected: {formatted1}")
    
    # Test Subscribe Layer
    layer_name = "player2"
    layer_bytes = layer_name.encode('ascii')
    message2 = [0xF0, 0x7D, 0x02] + list(layer_bytes) + [0xF7]
    formatted2 = om.format_sysex_message(message2)
    print(f"Subscribe Layer: {formatted2}")
    
    print()

def test_input_formatting():
    """Test input SysEx formatting (receiver table)"""
    print("Testing Input SysEx Formatting:")
    print("-" * 60)
    
    received_messages = []
    
    def capture_sysex(msg_type, data):
        if msg_type == 'sysex_received':
            received_messages.append(data)
        elif msg_type == 'receiver_table':
            print(f"  Parsed data: {data}")
    
    im = InputManager(sysex_callback=capture_sysex)
    
    # Simulate receiver table with 1 device
    mac = [0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF]
    layer = "player2".encode('ascii')
    layer_padded = layer + bytes(16 - len(layer))  # Pad to 16 bytes
    
    sysex_data = [0xF0, 0x7D, 0x03, 0x01] + mac + list(layer_padded) + [0xF7]
    
    # Process the message
    im._handle_sysex_message(sysex_data)
    
    print(f"Formatted message: {received_messages[0] if received_messages else 'None'}")
    print()

def test_empty_table():
    """Test empty receiver table"""
    print("Testing Empty Receiver Table:")
    print("-" * 60)
    
    received_messages = []
    
    def capture_sysex(msg_type, data):
        if msg_type == 'sysex_received':
            received_messages.append(data)
    
    im = InputManager(sysex_callback=capture_sysex)
    
    # Empty table
    sysex_data = [0xF0, 0x7D, 0x03, 0x00, 0xF7]
    
    # Process the message
    im._handle_sysex_message(sysex_data)
    
    print(f"Formatted message: {received_messages[0] if received_messages else 'None'}")
    print()

if __name__ == '__main__':
    test_output_formatting()
    test_input_formatting()
    test_empty_table()
    print("✅ All tests completed!")
