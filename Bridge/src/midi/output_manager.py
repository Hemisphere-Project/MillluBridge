# MilluBridge - MIDI Output Manager
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
        self.SYSEX_CMD_MEDIA_SYNC = 0x05

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
    
    def send_media_sync(self, layer_name, media_index, position_ms, state):
        """Send 'Media Sync' SysEx message with media index, position, and state
        
        Packet format (26 bytes total):
        F0 7D 05 [layer_name(16 bytes)] [media_index(1)] [position_ms(4)] [state(1)] F7
        
        Args:
            layer_name: Layer name (max 16 chars)
            media_index: Media index 0-127 (0=stop, 1-127=media number)
            position_ms: Position in milliseconds (uint32, 4 bytes)
            state: 0=stopped, 1=playing
        """
        if not self.current_port:
            return False
        
        # Pad or truncate layer name to exactly 16 bytes
        layer_bytes = (layer_name[:16] + '\x00' * 16)[:16].encode('ascii')
        
        # Clamp media index to valid range
        media_index = max(0, min(127, media_index))
        
        # Convert state to byte (0=stopped, 1=playing)
        state_byte = 1 if state == 'playing' else 0
        
        # Convert position_ms to 4 bytes (big-endian uint32)
        position_bytes = [
            (position_ms >> 24) & 0xFF,
            (position_ms >> 16) & 0xFF,
            (position_ms >> 8) & 0xFF,
            position_ms & 0xFF
        ]
        
        message = ([self.SYSEX_START, self.SYSEX_MANUFACTURER_ID, 
                   self.SYSEX_CMD_MEDIA_SYNC] + 
                   list(layer_bytes) + 
                   [media_index] + 
                   position_bytes + 
                   [state_byte] + 
                   [self.SYSEX_END])
        
        self.midi_out.send_message(message)
        # Don't print every sync message to avoid spam
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
        
        elif cmd == self.SYSEX_CMD_MEDIA_SYNC:
            # Extract layer, index, position, state
            # Format: F0 7D 05 [Layer(16)] [Index(1)] [Position(4)] [State(1)] F7
            if len(message) >= 26:  # F0 7D 05 + 16 Layer + 1 Index + 4 Position + 1 State + F7
                layer_bytes = message[3:19]
                layer_name = bytes(layer_bytes).decode('ascii', errors='ignore').rstrip('\x00')
                media_index = message[19]
                position_ms = (message[20] << 24) | (message[21] << 16) | (message[22] << 8) | message[23]
                state_byte = message[24]
                state_str = "playing" if state_byte == 1 else "stopped"
                position_s = position_ms / 1000.0
                return f"SysEx: Media Sync Layer='{layer_name}', Index={media_index}, Pos={position_s:.2f}s, State={state_str}"
            else:
                hex_str = ' '.join(f'{b:02X}' for b in message)
                return f"SysEx: Media Sync (malformed) ({hex_str})"
        
        else:
            hex_str = ' '.join(f'{b:02X}' for b in message)
            return f"SysEx (CMD 0x{cmd:02X}): {hex_str}"
