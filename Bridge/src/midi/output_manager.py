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
        
        # Bridge → Nowde Direct (0x01-0x0F)
        self.SYSEX_CMD_QUERY_CONFIG = 0x01
        self.SYSEX_CMD_PUSH_FULL_CONFIG = 0x02
        self.SYSEX_CMD_QUERY_RUNNING_STATE = 0x03
        self.SYSEX_CMD_ENTER_BOOTLOADER = 0x04
        
        # Bridge → Receivers via Sender (0x10-0x1F)
        self.SYSEX_CMD_MEDIA_SYNC = 0x10
        self.SYSEX_CMD_CHANGE_RECEIVER_LAYER = 0x11
        
        # Nowde → Bridge Responses (0x20-0x3F)
        self.SYSEX_CMD_CONFIG_STATE = 0x20
        self.SYSEX_CMD_RUNNING_STATE = 0x21
        self.SYSEX_CMD_ERROR_REPORT = 0x30
    
    def encode_7bit(self, data_bytes):
        """Encode bytes to 7-bit MIDI-safe format.
        Every 7 bytes becomes 8 bytes (MSBs packed in first byte).
        
        Args:
            data_bytes: List of integers (0-255) to encode
        Returns:
            List of 7-bit safe bytes (0-127)
        """
        result = []
        i = 0
        while i < len(data_bytes):
            # Pack MSBs of next 7 bytes into first output byte
            chunk_size = min(7, len(data_bytes) - i)
            msb_byte = 0
            for j in range(chunk_size):
                if data_bytes[i + j] & 0x80:
                    msb_byte |= (1 << j)
            result.append(msb_byte)
            
            # Add 7-bit data (clear MSB)
            for j in range(chunk_size):
                result.append(data_bytes[i + j] & 0x7F)
            
            i += chunk_size
        
        return result
        
        # Bridge → Nowde Direct (0x01-0x0F)
        self.SYSEX_CMD_QUERY_CONFIG = 0x01
        self.SYSEX_CMD_PUSH_FULL_CONFIG = 0x02
        self.SYSEX_CMD_QUERY_RUNNING_STATE = 0x03
        
        # Bridge → Receivers via Sender (0x10-0x1F)
        self.SYSEX_CMD_MEDIA_SYNC = 0x10
        self.SYSEX_CMD_CHANGE_RECEIVER_LAYER = 0x11
        
        # Nowde → Bridge Responses (0x20-0x3F)
        self.SYSEX_CMD_CONFIG_STATE = 0x20
        self.SYSEX_CMD_RUNNING_STATE = 0x21
        self.SYSEX_CMD_ERROR_REPORT = 0x30

    def get_ports(self):
        """Get list of available MIDI output ports"""
        try:
            ports = self.midi_out.get_ports()
            if not ports:
                return ["No MIDI ports available"]
            return ports
        except Exception as e:
            # Port list changed during enumeration (device unplugged)
            print(f"Warning: Error enumerating MIDI output ports: {e}")
            return []

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
    
    def send_query_config(self):
        """Send QUERY_CONFIG to request current config and activate sender mode"""
        if not self.current_port:
            return False
        
        # F0 7D 01 F7
        message = [self.SYSEX_START, self.SYSEX_MANUFACTURER_ID, 
                   self.SYSEX_CMD_QUERY_CONFIG, self.SYSEX_END]
        self.midi_out.send_message(message)
        print("Sent QUERY_CONFIG SysEx")
        return (True, self.format_sysex_message(message))
    
    def send_push_full_config(self, rf_sim_enabled, rf_sim_max_delay_ms):
        """Send PUSH_FULL_CONFIG to apply configuration to sender
        
        Args:
            rf_sim_enabled: Boolean - enable RF simulation
            rf_sim_max_delay_ms: Int - maximum delay in milliseconds (0-16383)
        """
        if not self.current_port:
            return False
        
        # F0 7D 02 [rfSimEnabled(1)] [rfSimMaxDelayHi(7-bit)] [rfSimMaxDelayLo(7-bit)] F7
        # Use 7-bit encoding for MIDI SysEx compatibility (14-bit range = 0-16383)
        enabled_byte = 1 if rf_sim_enabled else 0
        delay_hi = (rf_sim_max_delay_ms >> 7) & 0x7F  # Upper 7 bits
        delay_lo = rf_sim_max_delay_ms & 0x7F          # Lower 7 bits
        
        message = [self.SYSEX_START, self.SYSEX_MANUFACTURER_ID, 
                   self.SYSEX_CMD_PUSH_FULL_CONFIG, enabled_byte, delay_hi, delay_lo, self.SYSEX_END]
        self.midi_out.send_message(message)
        print(f"Sent PUSH_FULL_CONFIG: RF Sim={'ON' if rf_sim_enabled else 'OFF'}, MaxDelay={rf_sim_max_delay_ms}ms")
        return (True, self.format_sysex_message(message))
    
    def send_query_running_state(self):
        """Send QUERY_RUNNING_STATE to request runtime state and receiver table"""
        if not self.current_port:
            return False
        
        # F0 7D 03 F7
        message = [self.SYSEX_START, self.SYSEX_MANUFACTURER_ID, 
                   self.SYSEX_CMD_QUERY_RUNNING_STATE, self.SYSEX_END]
        self.midi_out.send_message(message)
        # print("Sent QUERY_RUNNING_STATE SysEx")
        return (True, self.format_sysex_message(message))
    
    def send_enter_bootloader(self):
        """Send ENTER_BOOTLOADER command to trigger firmware update mode"""
        if not self.current_port:
            return False, "No MIDI port open"
        
        # F0 7D 04 F7
        message = [self.SYSEX_START, self.SYSEX_MANUFACTURER_ID, 
                   self.SYSEX_CMD_ENTER_BOOTLOADER, self.SYSEX_END]
        self.midi_out.send_message(message)
        print("Sent ENTER_BOOTLOADER SysEx")
        return (True, self.format_sysex_message(message))
    
    def send_change_receiver_layer(self, mac_address, layer_name):
        """Send 'Change Receiver Layer' SysEx message to update a specific receiver's layer
        
        Format (7-bit encoded):
        F0 7D 11 [mac_encoded(7 bytes)] [layer_encoded(19 bytes)] F7
        MAC: 6 bytes -> 7 bytes encoded
        Layer: 16 bytes -> 19 bytes encoded (2 chunks: 7+7+2 bytes)
        """
        if not self.current_port:
            return False
        
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
        layer_bytes = list((layer_name[:16] + '\x00' * 16)[:16].encode('ascii'))
        
        # 7-bit encode MAC (6 bytes -> 7 bytes encoded)
        mac_encoded = self.encode_7bit(mac_bytes)
        
        # 7-bit encode layer name (16 bytes -> 19 bytes encoded)
        layer_encoded = self.encode_7bit(layer_bytes)
        
        message = ([self.SYSEX_START, self.SYSEX_MANUFACTURER_ID, 
                   self.SYSEX_CMD_CHANGE_RECEIVER_LAYER] + 
                   mac_encoded + layer_encoded + [self.SYSEX_END])
        
        self.midi_out.send_message(message)
        print(f"Sent Change Receiver Layer SysEx: MAC={mac_address}, Layer={layer_name}")
        return (True, self.format_sysex_message(message))
    
    def send_media_sync(self, layer_name, media_index, position_ms, state):
        """Send 'Media Sync' SysEx message with media index, position, and state
        
        Packet format (encoded):
        F0 7D 10 [layer_name(16 bytes)] [media_index(1)] [position_ms_encoded(5 bytes)] [state(1)] F7
        
        Args:
            layer_name: Layer name (max 16 chars)
            media_index: Media index 0-127 (0=stop, 1-127=media number)
            position_ms: Position in milliseconds (uint32, 4 bytes raw -> 5 bytes encoded)
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
        
        # Convert position_ms to 4 bytes (big-endian uint32) and 7-bit encode
        position_bytes_raw = [
            (position_ms >> 24) & 0xFF,
            (position_ms >> 16) & 0xFF,
            (position_ms >> 8) & 0xFF,
            position_ms & 0xFF
        ]
        position_bytes_encoded = self.encode_7bit(position_bytes_raw)
        
        message = ([self.SYSEX_START, self.SYSEX_MANUFACTURER_ID, 
                   self.SYSEX_CMD_MEDIA_SYNC] + 
                   list(layer_bytes) + 
                   [media_index] + 
                   position_bytes_encoded + 
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
        
        if cmd == self.SYSEX_CMD_QUERY_CONFIG:
            return "SysEx: QUERY_CONFIG (F0 7D 01 F7)"
        
        elif cmd == self.SYSEX_CMD_PUSH_FULL_CONFIG:
            if len(message) >= 7:
                rf_sim = "ON" if message[3] != 0 else "OFF"
                max_delay = (message[4] << 8) | message[5]
                return f"SysEx: PUSH_FULL_CONFIG RF={rf_sim}, MaxDelay={max_delay}ms"
            else:
                hex_str = ' '.join(f'{b:02X}' for b in message)
                return f"SysEx: PUSH_FULL_CONFIG (malformed) ({hex_str})"
        
        elif cmd == self.SYSEX_CMD_QUERY_RUNNING_STATE:
            return "SysEx: QUERY_RUNNING_STATE (F0 7D 03 F7)"
        
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
            # Format: F0 7D 10 [Layer(16)] [Index(1)] [Position_encoded(5)] [State(1)] F7
            if len(message) >= 27:  # F0 7D 10 + 16 Layer + 1 Index + 5 Position_encoded + 1 State + F7
                layer_bytes = message[3:19]
                layer_name = bytes(layer_bytes).decode('ascii', errors='ignore').rstrip('\x00')
                media_index = message[19]
                # Decode 7-bit encoded position (5 bytes -> 4 bytes)
                position_encoded = message[20:25]
                msb_byte = position_encoded[0]
                position_bytes = []
                for i in range(4):
                    byte_val = position_encoded[i + 1]
                    if msb_byte & (1 << i):
                        byte_val |= 0x80
                    position_bytes.append(byte_val)
                position_ms = (position_bytes[0] << 24) | (position_bytes[1] << 16) | (position_bytes[2] << 8) | position_bytes[3]
                state_byte = message[25]
                state_str = "playing" if state_byte == 1 else "stopped"
                position_s = position_ms / 1000.0
                return f"SysEx: Media Sync Layer='{layer_name}', Index={media_index}, Pos={position_s:.2f}s, State={state_str}"
            else:
                hex_str = ' '.join(f'{b:02X}' for b in message)
                return f"SysEx: Media Sync (malformed) ({hex_str})"
        
        else:
            hex_str = ' '.join(f'{b:02X}' for b in message)
            return f"SysEx (CMD 0x{cmd:02X}): {hex_str}"
