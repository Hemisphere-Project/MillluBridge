# MilluBridge - MIDI Input Manager
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
import threading


class InputManager:
    def __init__(self, callback=None, sysex_callback=None):
        self.midi_in = rtmidi.MidiIn()
        # Enable SysEx messages (don't ignore them)
        self.midi_in.ignore_types(sysex=False)
        
        self.current_port = None
        self.callback = callback
        self.sysex_callback = sysex_callback
        self.listener_thread = None
        self.is_listening = False
        
        # SysEx constants (matching Nowde firmware)
        self.SYSEX_START = 0xF0
        self.SYSEX_END = 0xF7
        self.SYSEX_MANUFACTURER_ID = 0x7D
        
        # Nowde → Bridge Responses (0x20-0x3F)
        self.SYSEX_CMD_HELLO = 0x20
        self.SYSEX_CMD_CONFIG_STATE = 0x21
        self.SYSEX_CMD_RUNNING_STATE = 0x22
        self.SYSEX_CMD_ERROR_REPORT = 0x30
        
        # SysEx parsing state
        self.sysex_buffer = []
        self.in_sysex = False
    
    def _decode_7bit(self, encoded_data):
        """Decode 7-bit MIDI format back to 8-bit data
        Every 8 bytes of input becomes 7 bytes of output (MSBs unpacked from first byte)
        """
        decoded = []
        idx = 0
        
        while idx < len(encoded_data):
            # Read MSB byte
            msb_byte = encoded_data[idx]
            idx += 1
            
            # Decode up to 7 data bytes
            chunk_size = min(7, len(encoded_data) - idx)
            for i in range(chunk_size):
                if idx >= len(encoded_data):
                    break
                byte_val = encoded_data[idx]
                idx += 1
                # Restore MSB if it was set
                if msb_byte & (1 << i):
                    byte_val |= 0x80
                decoded.append(byte_val)
        
        return decoded

    def get_ports(self):
        """Get list of available MIDI input ports"""
        try:
            ports = self.midi_in.get_ports()
            if not ports:
                return ["No MIDI ports available"]
            return ports
        except Exception as e:
            # Port list changed during enumeration (device unplugged)
            print(f"Warning: Error enumerating MIDI input ports: {e}")
            return []

    def open_port(self, port_name):
        """Open a MIDI input port by name"""
        # Close existing port if open
        self.close_port()
        
        ports = self.midi_in.get_ports()
        if port_name in ports:
            port_index = ports.index(port_name)
            self.midi_in.open_port(port_index)
            self.current_port = port_name
            
            # Set up callback for incoming messages
            self.midi_in.set_callback(self._on_midi_message)
            
            print(f"Opened MIDI input port: {port_name}")
            return True
        return False

    def _on_midi_message(self, event, data=None):
        """Internal callback for MIDI messages"""
        message, deltatime = event
        
        # Process SysEx messages
        self._process_sysex(message)
        
        # Forward to general callback
        if self.callback:
            self.callback(message, deltatime)
    
    def _process_sysex(self, message):
        """Process incoming MIDI message for SysEx data"""
        for byte in message:
            if byte == self.SYSEX_START:
                self.in_sysex = True
                self.sysex_buffer = [byte]
            elif self.in_sysex:
                self.sysex_buffer.append(byte)
                
                if byte == self.SYSEX_END:
                    # Complete SysEx message received
                    self._handle_sysex_message(self.sysex_buffer)
                    self.in_sysex = False
                    self.sysex_buffer = []
    
    def _handle_sysex_message(self, sysex_data):
        """Parse and handle complete SysEx message"""
        # Validate minimum length: F0 7D CMD F7 = 4 bytes
        if len(sysex_data) < 4:
            return
        
        # Silently ignore non-matching manufacturer IDs (system SysEx, etc.)
        if sysex_data[0] != self.SYSEX_START or \
           sysex_data[-1] != self.SYSEX_END:
            return
        
        if sysex_data[1] != self.SYSEX_MANUFACTURER_ID:
            return
        
        command = sysex_data[2]
        formatted_msg = None
        
        if command == self.SYSEX_CMD_HELLO:
            hello_data, formatted_msg = self._parse_hello(sysex_data)
            if self.sysex_callback and hello_data:
                self.sysex_callback('hello', hello_data)
        
        elif command == self.SYSEX_CMD_CONFIG_STATE:
            config_data, formatted_msg = self._parse_config_state(sysex_data)
            if self.sysex_callback and config_data:
                self.sysex_callback('config_state', config_data)
        
        elif command == self.SYSEX_CMD_RUNNING_STATE:
            running_data, formatted_msg = self._parse_running_state(sysex_data)
            if self.sysex_callback and running_data:
                self.sysex_callback('running_state', running_data)
        
        elif command == self.SYSEX_CMD_ERROR_REPORT:
            error_data, formatted_msg = self._parse_error_report(sysex_data)
            if self.sysex_callback and error_data:
                self.sysex_callback('error_report', error_data)
        
        else:
            formatted_msg = f"SysEx: Unknown command 0x{command:02X}"
        
        # Log formatted message
        if formatted_msg and self.sysex_callback:
            self.sysex_callback('sysex_received', formatted_msg)
    def _parse_hello(self, sysex_data):
        """Parse HELLO SysEx message (F0 7D 20 [version(8,encoded:10)] [uptimeMs(4,encoded:5)] [bootReason(1)] F7)
        Sent by Nowde on boot/reboot
        Total: 3 (header) + 10 (version encoded) + 5 (uptime encoded) + 1 (reason) + 1 (F7) = 20 bytes
        """
        expected_len = 20
        if len(sysex_data) < expected_len:
            return None, f"SysEx: HELLO (invalid format - expected {expected_len} bytes, got {len(sysex_data)})"
        
        idx = 3
        
        # Version (10 bytes encoded -> 8 bytes decoded)
        version_encoded = sysex_data[idx:idx+10]
        version_decoded = self._decode_7bit(version_encoded)
        if len(version_decoded) < 8:
            return None, "SysEx: HELLO (invalid version encoding)"
        version_str = bytes(version_decoded[:8]).decode('ascii', errors='ignore').rstrip('\x00')
        idx += 10
        
        # Uptime (5 bytes encoded -> 4 bytes decoded)
        uptime_encoded = sysex_data[idx:idx+5]
        uptime_decoded = self._decode_7bit(uptime_encoded)
        if len(uptime_decoded) < 4:
            return None, "SysEx: HELLO (invalid uptime)"
        
        uptime_ms = (uptime_decoded[0] << 24) | (uptime_decoded[1] << 16) | (uptime_decoded[2] << 8) | uptime_decoded[3]
        idx += 5
        
        # Boot reason (1 byte)
        boot_reason = sysex_data[idx]
        
        # ESP32 reset reason names
        reset_reasons = {
            1: "POWERON",
            3: "SOFTWARE",
            4: "WATCHDOG",
            5: "DEEP_SLEEP",
            6: "BROWNOUT",
            7: "SDIO",
            12: "CPU0_RESET",
            13: "CPU1_RESET"
        }
        
        boot_reason_str = reset_reasons.get(boot_reason, f"UNKNOWN_0x{boot_reason:02X}")
        
        hello_data = {
            'version': version_str,
            'uptime_ms': uptime_ms,
            'boot_reason': boot_reason,
            'boot_reason_str': boot_reason_str
        }
        
        formatted = f"SysEx: HELLO - Version: {version_str}, Uptime: {uptime_ms}ms, Boot: {boot_reason_str}"
        return hello_data, formatted
    
    def _parse_config_state(self, sysex_data):
        """Parse CONFIG_STATE SysEx message (F0 7D 20 [rfSimEnabled] [rfSimMaxDelayHi(7-bit)] [rfSimMaxDelayLo(7-bit)] F7)"""
        if len(sysex_data) < 7:
            return None, "SysEx: CONFIG_STATE (invalid format)"
        
        rf_sim_enabled = sysex_data[3] != 0
        # Decode from two 7-bit bytes (MIDI SysEx compatible, 14-bit range = 0-16383)
        rf_sim_max_delay_ms = ((sysex_data[4] & 0x7F) << 7) | (sysex_data[5] & 0x7F)
        
        config = {
            'rf_simulation_enabled': rf_sim_enabled,
            'rf_simulation_max_delay_ms': rf_sim_max_delay_ms
        }
        
        formatted = f"SysEx: CONFIG_STATE - RF Sim: {'ON' if rf_sim_enabled else 'OFF'}, Max Delay: {rf_sim_max_delay_ms}ms"
        return config, formatted
    
    def _parse_running_state(self, sysex_data):
        """Parse RUNNING_STATE SysEx message
        Format: F0 7D 22 [uptime(4,encoded:5)] [meshSynced(1)] [numReceivers(1)] 
                [receiver1_data(36,encoded:42)...] F7
        All multi-byte fields are 7-bit encoded
        """
        if len(sysex_data) < 11:  # Minimum: F0 7D 21 + 5 uptime(encoded) + 1 sync + 1 count + F7
            return None, "SysEx: RUNNING_STATE (invalid format)"
        
        idx = 3  # Start after F0 7D 21
        
        # Decode uptime (5 bytes encoded -> 4 bytes decoded)
        uptime_encoded = sysex_data[idx:idx+5]
        uptime_decoded = self._decode_7bit(uptime_encoded)
        if len(uptime_decoded) < 4:
            return None, "SysEx: RUNNING_STATE (invalid uptime)"
        
        uptime_ms = (uptime_decoded[0] << 24) | (uptime_decoded[1] << 16) | (uptime_decoded[2] << 8) | uptime_decoded[3]
        uptime_s = uptime_ms / 1000.0
        idx += 5
        
        # Parse mesh clock synced (1 byte, safe as-is)
        if idx >= len(sysex_data) - 1:
            return None, "SysEx: RUNNING_STATE (truncated at mesh_synced)"
        mesh_synced = sysex_data[idx] != 0
        idx += 1
        
        # Parse receiver count (1 byte, safe as-is)
        if idx >= len(sysex_data) - 1:
            return None, "SysEx: RUNNING_STATE (truncated at num_receivers)"
        num_receivers = sysex_data[idx]
        idx += 1
        
        receivers = []
        
        # Parse each receiver (42 bytes encoded -> 36 bytes decoded)
        for i in range(num_receivers):
            if idx + 42 > len(sysex_data) - 1:  # -1 for SYSEX_END
                break
            
            # Decode receiver data (42 bytes encoded -> 36 bytes decoded)
            receiver_encoded = sysex_data[idx:idx+42]
            receiver_decoded = self._decode_7bit(receiver_encoded)
            
            if len(receiver_decoded) < 36:
                break
            
            # MAC (6 bytes)
            mac_bytes = receiver_decoded[0:6]
            mac_str = ':'.join(f'{b:02X}' for b in mac_bytes)
            
            # Layer (16 bytes)
            layer_bytes = receiver_decoded[6:22]
            layer_str = bytes(layer_bytes).decode('ascii', errors='ignore').rstrip('\x00')
            
            # Version (8 bytes)
            version_bytes = receiver_decoded[22:30]
            version_str = bytes(version_bytes).decode('ascii', errors='ignore').rstrip('\x00')
            
            # Last seen (4 bytes, milliseconds ago)
            last_seen_ms = (receiver_decoded[30] << 24) | (receiver_decoded[31] << 16) | (receiver_decoded[32] << 8) | receiver_decoded[33]
            
            # Active (1 byte)
            active = receiver_decoded[34] != 0
            
            # Media index (1 byte) - current playing media index (0 = stopped)
            media_index = receiver_decoded[35]
            
            # Generate UUID from last 3 bytes of MAC
            uuid = mac_str[-8:].replace(':', '')
            
            receivers.append({
                'mac': mac_str,
                'uuid': uuid,
                'layer': layer_str,
                'version': version_str,
                'last_seen_ms': last_seen_ms,
                'active': active,
                'media_index': media_index,
                'name': f"Nowde-{uuid}"
            })
            
            idx += 42
        
        running_state = {
            'uptime_ms': uptime_ms,
            'uptime_s': uptime_s,
            'mesh_synced': mesh_synced,
            'receivers': receivers
        }
        
        formatted = f"SysEx: RUNNING_STATE - Uptime: {uptime_s:.1f}s, Mesh: {'SYNCED' if mesh_synced else 'NOT SYNCED'}, Receivers: {num_receivers}"
        if receivers:
            receivers_str = ', '.join([f"{r['uuid']} v{r['version']}({r['layer']})" for r in receivers])
            formatted += f" [{receivers_str}]"
        
        return running_state, formatted
    
    def _parse_error_report(self, sysex_data):
        """Parse ERROR_REPORT SysEx message (F0 7D 30 [errorCode] [contextLength] [context...] F7)"""
        if len(sysex_data) < 6:  # Minimum: F0 7D 30 + code + length + F7
            return None, "SysEx: ERROR_REPORT (invalid format)"
        
        error_code = sysex_data[3]
        context_length = sysex_data[4]
        
        context_bytes = []
        if context_length > 0 and len(sysex_data) >= 6 + context_length:
            context_bytes = sysex_data[5:5+context_length]
        
        # Error code names
        error_names = {
            0x01: "CONFIG_INVALID",
            0x02: "SYSEX_PARSE_ERROR",
            0x03: "ESPNOW_SEND_FAILED",
            0x04: "MESH_CLOCK_LOST_SYNC",
            0x05: "RECEIVER_TIMEOUT",
            0xFF: "UNKNOWN_ERROR"
        }
        
        error_name = error_names.get(error_code, f"UNKNOWN_0x{error_code:02X}")
        
        error_data = {
            'error_code': error_code,
            'error_name': error_name,
            'context_bytes': context_bytes
        }
        
        # Format context for display
        context_str = ""
        if context_bytes:
            # If looks like MAC address (6 bytes), format as MAC
            if len(context_bytes) == 6:
                context_str = " MAC: " + ':'.join(f'{b:02X}' for b in context_bytes)
            else:
                context_str = " Context: " + ' '.join(f'{b:02X}' for b in context_bytes)
        
        formatted = f"SysEx: ERROR_REPORT - {error_name} (0x{error_code:02X}){context_str}"
        return error_data, formatted
    def close_port(self):
        """Close the currently open MIDI input port"""
        if self.current_port:
            self.midi_in.close_port()
            self.current_port = None
            print("Closed MIDI input port")
