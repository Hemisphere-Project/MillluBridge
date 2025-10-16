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
        self.SYSEX_CMD_RECEIVER_TABLE = 0x03
        
        # SysEx parsing state
        self.sysex_buffer = []
        self.in_sysex = False

    def get_ports(self):
        """Get list of available MIDI input ports"""
        ports = self.midi_in.get_ports()
        if not ports:
            return ["No MIDI ports available"]
        return ports

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
        
        # Validate format
        if sysex_data[0] != self.SYSEX_START or \
           sysex_data[1] != self.SYSEX_MANUFACTURER_ID or \
           sysex_data[-1] != self.SYSEX_END:
            return
        
        command = sysex_data[2]
        
        if command == self.SYSEX_CMD_RECEIVER_TABLE:
            formatted_msg = self._parse_receiver_table(sysex_data)
            # Call sysex callback with formatted message for logging
            if self.sysex_callback:
                self.sysex_callback('sysex_received', formatted_msg)
    
    def _parse_receiver_table(self, sysex_data):
        """Parse receiver table SysEx message"""
        # Format: F0 7D 03 [count] [mac1(6) layer1(16) version1(8) status1(1)] ... F7
        if len(sysex_data) < 5:  # Minimum with count
            return "SysEx: Receiver Table (invalid format)"
        
        count = sysex_data[3]
        remote_nowdes = []
        
        # Each entry is 31 bytes (6 MAC + 16 layer + 8 version + 1 status)
        idx = 4
        for i in range(count):
            if idx + 31 > len(sysex_data) - 1:  # -1 for SYSEX_END
                break
            
            # Extract MAC address (6 bytes)
            mac_bytes = sysex_data[idx:idx+6]
            mac_str = ':'.join(f'{b:02X}' for b in mac_bytes)
            
            # Extract layer name (16 bytes)
            layer_bytes = sysex_data[idx+6:idx+22]
            # Convert to string, removing null bytes
            layer_str = bytes(layer_bytes).decode('ascii', errors='ignore').rstrip('\x00')
            
            # Extract version (8 bytes)
            version_bytes = sysex_data[idx+22:idx+30]
            # Convert to string, removing null bytes
            version_str = bytes(version_bytes).decode('ascii', errors='ignore').rstrip('\x00')
            
            # Extract status (1 byte): 1 = connected, 0 = missing
            status = sysex_data[idx+30]
            connected = (status == 1)
            
            # Generate UUID from last 3 bytes of MAC (6 hex chars)
            uuid = mac_str[-8:].replace(':', '')  # Last 3 bytes = 6 hex chars
            
            remote_nowdes.append({
                'mac': mac_str,
                'uuid': uuid,
                'layer': layer_str,
                'version': version_str,
                'connected': connected,
                'name': f"Nowde-{uuid}"
            })
            
            idx += 31
        
        # Call the SysEx callback with parsed data
        if self.sysex_callback:
            self.sysex_callback('receiver_table', remote_nowdes)
        
        # Format human-readable message
        hex_str = ' '.join(f'{b:02X}' for b in sysex_data)
        if count == 0:
            return f"SysEx: Receiver Table - 0 devices ({hex_str})"
        else:
            devices_str = ', '.join([f"{n['uuid']} v{n['version']} ({n['layer']}) {'✓' if n['connected'] else '✗'}" for n in remote_nowdes])
            return f"SysEx: Receiver Table - {count} device(s): {devices_str} ({hex_str})"

    def close_port(self):
        """Close the currently open MIDI input port"""
        if self.current_port:
            self.midi_in.close_port()
            self.current_port = None
            print("Closed MIDI input port")
