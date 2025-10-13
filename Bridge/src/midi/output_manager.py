import rtmidi


class OutputManager:
    def __init__(self):
        self.midi_out = rtmidi.MidiOut()
        self.current_port = None
        
        # SysEx constants (matching Nowde firmware)
        self.SYSEX_START = 0xF0
        self.SYSEX_END = 0xF7
        self.SYSEX_MANUFACTURER_ID = 0x7D
        self.SYSEX_CMD_BRIDGE_CONNECTED = 0x01
        self.SYSEX_CMD_SUBSCRIBE_LAYER = 0x02
        self.SYSEX_CMD_CHANGE_RECEIVER_LAYER = 0x04

    def get_ports(self):
        """Get list of available MIDI output ports"""
        ports = self.midi_out.get_ports()
        if not ports:
            return ["No MIDI ports available"]
        return ports

    def open_port(self, port_name):
        """Open a MIDI output port by name"""
        ports = self.midi_out.get_ports()
        if port_name in ports:
            port_index = ports.index(port_name)
            self.midi_out.open_port(port_index)
            self.current_port = port_name
            print(f"Opened MIDI port: {port_name}")
            return True
        return False

    def close_port(self):
        """Close the currently open MIDI port"""
        if self.current_port:
            self.midi_out.close_port()
            self.current_port = None
            print("Closed MIDI port")
    
    def send_bridge_connected(self):
        """Send 'Bridge Connected' SysEx message to activate sender mode"""
        if not self.current_port:
            return False
        
        # F0 7D 01 F7
        message = [self.SYSEX_START, self.SYSEX_MANUFACTURER_ID, 
                   self.SYSEX_CMD_BRIDGE_CONNECTED, self.SYSEX_END]
        self.midi_out.send_message(message)
        print("Sent Bridge Connected SysEx")
        return (True, self.format_sysex_message(message))
    
    def send_subscribe_layer(self, layer_name):
        """Send 'Subscribe to Layer' SysEx message to activate receiver mode"""
        if not self.current_port:
            return False
        
        # F0 7D 02 [layer_name...] F7
        # Limit layer name to 16 characters
        layer_bytes = layer_name[:16].encode('ascii')
        message = [self.SYSEX_START, self.SYSEX_MANUFACTURER_ID, 
                   self.SYSEX_CMD_SUBSCRIBE_LAYER] + list(layer_bytes) + [self.SYSEX_END]
        self.midi_out.send_message(message)
        print(f"Sent Subscribe Layer SysEx: {layer_name}")
        return (True, self.format_sysex_message(message))
    
    def send_change_receiver_layer(self, mac_address, layer_name):
        """Send 'Change Receiver Layer' SysEx message to update a specific receiver's layer"""
        if not self.current_port:
            return False
        
        # F0 7D 04 [mac(6 bytes)] [layer_name(16 bytes)] F7
        # Convert MAC string (e.g., "AA:BB:CC:DD:EE:FF") to 6 bytes
        mac_parts = mac_address.split(':')
        if len(mac_parts) != 6:
            print(f"Error: Invalid MAC address format: {mac_address}")
            return False
        
        try:
            mac_bytes = [int(part, 16) for part in mac_parts]
        except ValueError:
            print(f"Error: Invalid MAC address hex values: {mac_address}")
            return False
        
        # Pad or truncate layer name to exactly 16 bytes
        layer_bytes = (layer_name[:16] + '\x00' * 16)[:16].encode('ascii')
        
        message = ([self.SYSEX_START, self.SYSEX_MANUFACTURER_ID, 
                   self.SYSEX_CMD_CHANGE_RECEIVER_LAYER] + 
                   mac_bytes + list(layer_bytes) + [self.SYSEX_END])
        
        self.midi_out.send_message(message)
        print(f"Sent Change Receiver Layer SysEx: MAC={mac_address}, Layer={layer_name}")
        return (True, self.format_sysex_message(message))
    
    def format_sysex_message(self, message):
        """Format SysEx message for human-readable logging"""
        if not message or message[0] != self.SYSEX_START:
            return f"Raw: {list(message)}"
        
        # Check if it's our manufacturer ID
        if len(message) < 3 or message[1] != self.SYSEX_MANUFACTURER_ID:
            return f"SysEx (Unknown): {' '.join(f'{b:02X}' for b in message)}"
        
        cmd = message[2]
        
        if cmd == self.SYSEX_CMD_BRIDGE_CONNECTED:
            return "SysEx: Bridge Connected (F0 7D 01 F7)"
        
        elif cmd == self.SYSEX_CMD_SUBSCRIBE_LAYER:
            # Extract layer name
            layer_bytes = message[3:-1]  # Skip F0, 7D, CMD at start and F7 at end
            layer_name = bytes(layer_bytes).decode('ascii', errors='ignore').rstrip('\x00')
            hex_str = ' '.join(f'{b:02X}' for b in message)
            return f"SysEx: Subscribe to Layer '{layer_name}' ({hex_str})"
        
        elif cmd == self.SYSEX_CMD_CHANGE_RECEIVER_LAYER:
            # Extract MAC and layer name
            # Format: F0 7D 04 [MAC(6)] [Layer(16)] F7
            if len(message) >= 26:  # F0 7D 04 + 6 MAC + 16 Layer + F7
                mac_bytes = message[3:9]
                mac_str = ':'.join(f'{b:02X}' for b in mac_bytes)
                layer_bytes = message[9:-1]
                layer_name = bytes(layer_bytes).decode('ascii', errors='ignore').rstrip('\x00')
                hex_str = ' '.join(f'{b:02X}' for b in message)
                return f"SysEx: Change Receiver Layer MAC={mac_str}, Layer='{layer_name}' ({hex_str})"
            else:
                hex_str = ' '.join(f'{b:02X}' for b in message)
                return f"SysEx: Change Receiver Layer (malformed) ({hex_str})"
        
        else:
            hex_str = ' '.join(f'{b:02X}' for b in message)
            return f"SysEx (CMD 0x{cmd:02X}): {hex_str}"
