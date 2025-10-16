# MilluBridge - Bridge Application
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

import dearpygui.dearpygui as dpg
from osc.server import OSCServer
from midi.output_manager import OutputManager
from midi.input_manager import InputManager
import time
import threading
import re
import json
import os

class MediaSyncManager:
    """Manages media synchronization state and throttling for each layer"""
    
    def __init__(self, output_manager, throttle_interval=0.1):
        self.output_manager = output_manager
        self.throttle_interval = throttle_interval  # seconds (default 10Hz = 0.1s)
        self.layers_state = {}  # {layer_name: {index, position, state, last_sent_time, last_sent_index}}
    
    def parse_media_index(self, filename):
        """Parse media index from filename (1-3 digits at start)"""
        if not filename:
            return 0
        
        # Match 1-3 digits at the start of filename
        match = re.match(r'^(\d{1,3})_', filename)
        if match:
            index = int(match.group(1))
            # Clamp to MIDI valid range (1-127, 0 reserved for stop)
            return min(max(index, 1), 127)
        return 0  # No index found
    
    def update_layer(self, layer_name, filename, position, duration, state):
        """Update layer state and send MIDI if needed"""
        current_time = time.time()
        # Media index is always 0 when stopped, otherwise parse from filename
        media_index = 0 if state == 'stopped' else self.parse_media_index(filename)
        
        # Initialize layer state if needed
        if layer_name not in self.layers_state:
            self.layers_state[layer_name] = {
                'index': 0,
                'position': 0.0,
                'state': 'stopped',
                'last_sent_time': 0,
                'last_sent_index': -1
            }
        
        layer_state = self.layers_state[layer_name]
        
        # Update state
        layer_state['index'] = media_index
        layer_state['position'] = position
        layer_state['state'] = state
        
        # Determine if we should send (throttled updates for all states)
        should_send = False
        
        # Send on index change (media change)
        if media_index != layer_state['last_sent_index']:
            should_send = True
        # Throttled updates for all states (playing or stopped)
        elif (current_time - layer_state['last_sent_time']) >= self.throttle_interval:
            should_send = True
        
        if should_send:
            # Send media sync via SysEx 0x05
            position_ms = int(position * 1000)  # Convert to milliseconds
            self.output_manager.send_media_sync(
                layer_name=layer_name,
                media_index=media_index,
                position_ms=position_ms,
                state=state
            )
            
            layer_state['last_sent_time'] = current_time
            layer_state['last_sent_index'] = media_index
    
    def set_throttle_interval(self, interval):
        """Update throttle interval (in seconds)"""
        self.throttle_interval = max(0.01, interval)  # Minimum 10ms

class MilluBridge:
    def __init__(self, osc_address=None, osc_port=None):
        # Load config first
        self.config_file = "config.json"
        self.config = self.load_config()
        
        # Use provided values or fall back to config
        self.osc_address = osc_address or self.config['gui_preferences']['osc_address']
        self.osc_port = osc_port or self.config['gui_preferences']['osc_port']
        self.osc_server = None
        self.output_manager = OutputManager()
        self.input_manager = InputManager(
            sysex_callback=self.handle_sysex_message
        )
        self.selected_port = None
        self.is_running = False
        self.last_osc_time = 0
        self.status_check_thread = None
        self.midi_refresh_thread = None
        self.media_sync_thread = None
        self.running_state_thread = None
        self.stop_midi_refresh = False
        self.stop_media_sync = False
        self.stop_running_state = False
        self.current_nowde_device = None
        self.sender_initialized = False  # Set to True after receiving HELLO
        
        # Millumin layer tracking
        self.layers = {}  # {layer_name: {state, filename, position, duration}}
        self.layer_rows = {}  # {layer_name: row_tag} - track row tags for updates
        self.show_all_messages = False
        
        # Remote Nowdes tracking
        self.remote_nowdes = {}  # {mac: {name, version, layer}}
        
        # Layer editing modal state
        self.editing_layer_mac = None  # Track which device is being edited
        
        # Media synchronization settings (configurable)
        self.sync_settings = {
            'mtc_framerate': 30,  # fps
            'freewheel_timeout': 3.0,  # seconds
            'clock_desync_threshold': 200,  # milliseconds
            'throttle_interval': 0.1  # seconds (10Hz)
        }
        
        # Media sync manager
        self.media_sync = MediaSyncManager(self.output_manager, 
                                          throttle_interval=self.sync_settings['throttle_interval'])
        
        # Create DearPyGUI context
        dpg.create_context()
        
        # Setup window
        self.setup_gui()
        
        # Start MIDI device refresh thread
        self.start_midi_refresh_thread()
        
        # Start media sync thread for continuous updates
        self.start_media_sync_thread()
        
        # Start running state query thread
        self.start_running_state_thread()
        
        # Auto-start bridge
        self.start_bridge()

    def load_config(self):
        """Load configuration from config.json, forcing RF sim to disabled"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                
                # Force RF simulation OFF on load (safety measure)
                if 'sender_config' in config:
                    config['sender_config']['rf_simulation_enabled'] = False
                
                # Apply defaults for missing keys
                if 'gui_preferences' not in config:
                    config['gui_preferences'] = {}
                
                config['gui_preferences'].setdefault('osc_address', '127.0.0.1')
                config['gui_preferences'].setdefault('osc_port', 8000)
                config['gui_preferences'].setdefault('media_sync_throttle_hz', 10)
                config['gui_preferences'].setdefault('window_position', [100, 100])
                
                if 'sender_config' not in config:
                    config['sender_config'] = {}
                
                config['sender_config'].setdefault('rf_simulation_enabled', False)
                config['sender_config'].setdefault('rf_simulation_max_delay_ms', 400)
                
                print(f"Config loaded from {self.config_file}")
                return config
            else:
                print(f"No config file found, using defaults")
                return self.get_default_config()
                
        except Exception as e:
            print(f"Error loading config: {e}, using defaults")
            return self.get_default_config()
    
    def get_default_config(self):
        """Return default configuration"""
        return {
            "sender_config": {
                "rf_simulation_enabled": False,
                "rf_simulation_max_delay_ms": 400
            },
            "gui_preferences": {
                "window_position": [100, 100],
                "osc_address": "127.0.0.1",
                "osc_port": 8000,
                "media_sync_throttle_hz": 10
            }
        }
    
    def save_config(self):
        """Save current configuration to config.json"""
        try:
            # Update config from current state
            self.config['gui_preferences']['osc_address'] = self.osc_address
            self.config['gui_preferences']['osc_port'] = self.osc_port
            
            # Calculate throttle Hz from interval
            if self.sync_settings['throttle_interval'] > 0:
                self.config['gui_preferences']['media_sync_throttle_hz'] = int(1.0 / self.sync_settings['throttle_interval'])
            
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            print(f"Config saved to {self.config_file}")
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def setup_gui(self):
        """Setup the DearPyGUI interface"""
        with dpg.window(label="MilluBridge - OSC to MIDI Bridge", tag="primary_window", 
                       width=900, height=700, no_close=True):
            
            # OSC Settings section
            dpg.add_text("Millumin Settings", color=(150, 200, 255))
            with dpg.group(horizontal=True):
                dpg.add_text("OSC Address:")
                dpg.add_input_text(tag="osc_address_input", default_value=self.osc_address, 
                                 width=150, on_enter=True, callback=self.on_osc_settings_changed)
                dpg.add_text("OSC Port:")
                dpg.add_input_text(tag="osc_port_input", default_value=str(self.osc_port), 
                                 width=100, on_enter=True, callback=self.on_osc_settings_changed)
            
            # OSC Status indicator
            with dpg.group(horizontal=True):
                dpg.add_text("OSC Status:", tag="status_label")
                dpg.add_text("[X]", tag="status_indicator", color=(255, 0, 0))  # Red by default
                dpg.add_text("", tag="status_text", color=(150, 150, 150))
                dpg.add_button(label="Show Logs", tag="osc_logs_toggle_btn", callback=self.toggle_osc_logs, width=100)
            
            # OSC setup note (shown when not receiving)
            dpg.add_text("Note: You should enable OSC sender feedback in Millumin > Device Manager > OSC section", 
                        tag="osc_setup_note", color=(150, 150, 150))
            
            dpg.add_separator()
            
            # Media Sync Settings
            dpg.add_text("Media Sync Settings", color=(150, 200, 255))
            with dpg.group(horizontal=True):
                dpg.add_text("Throttle (Hz):")
                dpg.add_slider_int(tag="throttle_hz_slider", default_value=10, 
                                  min_value=1, max_value=60, width=150,
                                  callback=self.on_throttle_changed)
                dpg.add_text("MTC Framerate:")
                dpg.add_input_int(tag="mtc_framerate_input", 
                                 default_value=self.sync_settings['mtc_framerate'],
                                 width=60, step=0, on_enter=True,
                                 callback=self.on_sync_setting_changed)
                dpg.add_text("fps")
            
            with dpg.group(horizontal=True):
                dpg.add_text("Freewheel Timeout:")
                dpg.add_input_float(tag="freewheel_timeout_input",
                                   default_value=self.sync_settings['freewheel_timeout'],
                                   width=60, step=0, format="%.1f", on_enter=True,
                                   callback=self.on_sync_setting_changed)
                dpg.add_text("s")
                dpg.add_text("   Desync Threshold:")
                dpg.add_input_int(tag="desync_threshold_input",
                                 default_value=self.sync_settings['clock_desync_threshold'],
                                 width=60, step=0, on_enter=True,
                                 callback=self.on_sync_setting_changed)
                dpg.add_text("ms")
            
            # OSC Logs section (hidden by default)
            with dpg.group(tag="osc_logs_section", show=False):
                dpg.add_separator()
                
                dpg.add_text("OSC Logs", color=(150, 200, 255))
                with dpg.group(horizontal=True):
                    dpg.add_checkbox(label="Show All Messages", tag="show_all_toggle", 
                                   callback=self.on_toggle_filter, default_value=False)
                
                # Use child window for auto-scrolling log
                with dpg.child_window(tag="osc_log_window", width=-1, height=150, border=True):
                    dpg.add_text("Waiting for OSC messages...", tag="osc_log_text", wrap=850)
            
            dpg.add_separator()
            
            # Millumin Layers section
            dpg.add_text("Millumin Layers", color=(150, 200, 255))
            with dpg.table(header_row=True, tag="layers_table", 
                          borders_innerH=True, borders_outerH=True, 
                          borders_innerV=True, borders_outerV=True,
                          row_background=True, resizable=True, height=150):
                dpg.add_table_column(label="Layers", width_fixed=True, init_width_or_weight=150)
                dpg.add_table_column(label="State", width_fixed=True, init_width_or_weight=60)
                dpg.add_table_column(label="Filename", width_stretch=True)
                dpg.add_table_column(label="Position", width_fixed=True, init_width_or_weight=80)
                dpg.add_table_column(label="Duration", width_fixed=True, init_width_or_weight=80)
            
            dpg.add_separator()
            
            # MIDI Settings section
            dpg.add_text("Local Nowde", color=(150, 200, 255))
            
            # Nowde connection status
            with dpg.group(horizontal=True):
                dpg.add_text("USB Status:")
                dpg.add_text("[X]", tag="nowde_status_indicator", color=(255, 0, 0))  # Red by default
                dpg.add_text("Not connected", tag="nowde_status_text", color=(150, 150, 150))
                dpg.add_button(label="Show Logs", tag="nowde_logs_toggle_btn", callback=self.toggle_nowde_logs, width=100)
            
            # RF Simulation control
            with dpg.group(horizontal=True):
                dpg.add_checkbox(label="Simulate Bad RF", tag="rf_sim_checkbox",
                               default_value=self.config['sender_config']['rf_simulation_enabled'],
                               callback=self.on_rf_sim_changed)
                dpg.add_text("Max Delay:")
                dpg.add_slider_int(tag="rf_sim_max_delay_slider",
                                 default_value=self.config['sender_config']['rf_simulation_max_delay_ms'],
                                 min_value=1, max_value=1000, width=150,
                                 callback=self.on_rf_sim_max_delay_changed)
                dpg.add_text("ms")
            
            # Nowde Logs section (hidden by default)
            with dpg.group(tag="nowde_logs_section", show=False):
                dpg.add_separator()
                
                dpg.add_text("Nowde Logs", color=(150, 200, 255))
                
                # Use child window for auto-scrolling log
                with dpg.child_window(tag="midi_log_window", width=-1, height=150, border=True):
                    dpg.add_text("Waiting for Nowde messages...", tag="midi_log_text", wrap=850)
            
            dpg.add_separator()
            
            # Remote Nowdes section
            dpg.add_text("Remote Nowdes", color=(150, 200, 255))
            with dpg.table(header_row=True, tag="remote_nowdes_table", 
                          borders_innerH=True, borders_outerH=True, 
                          borders_innerV=True, borders_outerV=True,
                          row_background=True, resizable=True, height=150):
                dpg.add_table_column(label="Nowde", width_fixed=True, init_width_or_weight=100)
                dpg.add_table_column(label="Version", width_fixed=True, init_width_or_weight=80)
                dpg.add_table_column(label="Last Seen", width_fixed=True, init_width_or_weight=100)
                dpg.add_table_column(label="State", width_fixed=True, init_width_or_weight=80)
                dpg.add_table_column(label="Layer", width_stretch=True)

    def handle_sysex_message(self, msg_type, data):
        """Handle parsed SysEx messages from Nowde"""
        if msg_type == 'hello':
            # Sender just booted/rebooted - reinitialize connection
            version = data['version']
            uptime_ms = data['uptime_ms']
            boot_reason = data['boot_reason_str']
            
            was_initialized = self.sender_initialized
            
            if not was_initialized:
                self.update_osc_log(f"Nowde HELLO received: v{version}, uptime {uptime_ms}ms, reason: {boot_reason}")
            else:
                self.update_osc_log(f"Nowde REBOOT detected: v{version}, uptime {uptime_ms}ms, reason: {boot_reason}")
            
            self.log_nowde_message(f"HELLO: v{version}, Boot reason: {boot_reason}")
            
            # Mark sender as initialized
            self.sender_initialized = True
            
            # Clear stale state
            self.remote_nowdes.clear()
            self.update_remote_nowdes_table()
            
            # Push our config to sender (don't query again - we already did that)
            if self.current_nowde_device and self.output_manager.current_port:
                # Push saved config to sender
                rf_sim_enabled = self.config['sender_config']['rf_simulation_enabled']
                rf_sim_max_delay = self.config['sender_config']['rf_simulation_max_delay_ms']
                
                result = self.output_manager.send_push_full_config(rf_sim_enabled, rf_sim_max_delay)
                if result and result[0]:
                    success, formatted_msg = result
                    self.log_nowde_message(f"TX: {formatted_msg}")
                    self.update_osc_log("Sender initialized - config pushed")
                
                # Query running state to get receiver table
                time.sleep(0.1)
                result = self.output_manager.send_query_running_state()
                if result and result[0]:
                    success, formatted_msg = result
                    self.log_nowde_message(f"TX: {formatted_msg}")
        
        elif msg_type == 'config_state':
            # Update config from sender's response
            self.config['sender_config']['rf_simulation_enabled'] = data['rf_simulation_enabled']
            self.config['sender_config']['rf_simulation_max_delay_ms'] = data['rf_simulation_max_delay_ms']
            
            # Update GUI if RF sim checkbox exists
            if dpg.does_item_exist("rf_sim_checkbox"):
                dpg.set_value("rf_sim_checkbox", data['rf_simulation_enabled'])
            
            # Log
            self.update_osc_log(f"Config received from sender: RF Sim={'ON' if data['rf_simulation_enabled'] else 'OFF'}")
        
        elif msg_type == 'running_state':
            # Incrementally update remote Nowdes table from receiver list
            # Don't clear the dict - just update/add entries
            received_macs = set()
            for receiver in data['receivers']:
                self.remote_nowdes[receiver['mac']] = receiver
                received_macs.add(receiver['mac'])
            
            # Remove receivers that are no longer in the list
            macs_to_remove = set(self.remote_nowdes.keys()) - received_macs
            for mac in macs_to_remove:
                del self.remote_nowdes[mac]
            
            # Update GUI
            self.update_remote_nowdes_table()
            
            # Log
            mesh_status = "SYNCED" if data['mesh_synced'] else "NOT SYNCED"
            self.update_osc_log(f"Running state: Uptime {data['uptime_s']:.1f}s, Mesh {mesh_status}, {len(data['receivers'])} receiver(s)")
        
        elif msg_type == 'error_report':
            # Log error from Nowde
            error_msg = f"Nowde Error: {data['error_name']} (0x{data['error_code']:02X})"
            if data['context_bytes']:
                error_msg += f" Context: {' '.join(f'{b:02X}' for b in data['context_bytes'])}"
            self.update_osc_log(error_msg)
            self.log_nowde_message(f"ERROR: {error_msg}")
        
        elif msg_type == 'sysex_received':
            # Log received SysEx in human-readable format
            self.log_nowde_message(f"RX: {data}")
    
    def on_layer_changed(self, mac_address, new_layer):
        """Handle layer change from GUI"""
        if not self.current_nowde_device:
            self.update_osc_log("Error: No Nowde connected")
            return
        
        # Validate layer name (strip whitespace, limit length)
        new_layer = new_layer.strip()[:16]
        
        if not new_layer:
            self.update_osc_log("Error: Layer name cannot be empty")
            return
        
        # Send Change Receiver Layer SysEx
        result = self.output_manager.send_change_receiver_layer(mac_address, new_layer)
        if result and result[0]:
            success, formatted_msg = result
            self.update_osc_log(f"Sent Change Receiver Layer: MAC={mac_address}, Layer={new_layer}")
            self.log_nowde_message(f"TX: {formatted_msg}")
        else:
            self.update_osc_log("Error: Failed to send Change Receiver Layer command")
    
    def open_layer_editor(self, mac_address):
        """Open modal dialog to edit layer for a specific Nowde"""
        self.editing_layer_mac = mac_address
        
        # Get current layer value
        current_layer = self.remote_nowdes.get(mac_address, {}).get('layer', '')
        
        # Create or show modal window
        if dpg.does_item_exist("layer_editor_modal"):
            dpg.delete_item("layer_editor_modal")
        
        with dpg.window(label="Edit Layer", tag="layer_editor_modal", modal=True, 
                       width=400, height=400, pos=[250, 150], no_resize=True):
            
            dpg.add_text(f"Editing layer for: {self.remote_nowdes[mac_address]['uuid']}")
            dpg.add_separator()
            
            dpg.add_text("Custom Layer Name:")
            dpg.add_input_text(tag="layer_custom_input", default_value=current_layer, 
                             width=-1,
                             callback=lambda s, a: self.on_custom_input_changed(s, a))
            
            dpg.add_text("(Press Enter or click Apply to confirm)", color=(150, 150, 150))
            
            dpg.add_separator()
            dpg.add_text("Or select from Millumin layers:")
            
            # Add listbox with Millumin layers
            layer_names = sorted(list(self.layers.keys()))
            # Add "-" as first option for "no layer"
            listbox_items = ["-"] + layer_names
            dpg.add_listbox(tag="layer_listbox", items=listbox_items, 
                          num_items=min(8, len(listbox_items)),
                          width=-1,
                          default_value="-",  # Default to "no layer"
                          callback=lambda s, a: self.select_layer_from_list(a))
            
            dpg.add_separator()
            
            # Buttons
            with dpg.group(horizontal=True):
                dpg.add_button(label="Apply", width=180, 
                             callback=lambda: self.apply_layer_edit_from_modal())
                dpg.add_button(label="Cancel", width=180, 
                             callback=lambda: dpg.delete_item("layer_editor_modal"))
    
    def on_custom_input_changed(self, sender, app_data):
        """When user types in custom input, clear listbox selection"""
        # Clear listbox selection when typing (app_data is the current text value)
        if dpg.does_item_exist("layer_listbox"):
            # Get current layers to check if typed value matches one
            layer_names = sorted(list(self.layers.keys()))
            if app_data not in layer_names:
                # Only clear if the typed value doesn't match a layer exactly
                # Setting to empty list item index or invalid value deselects
                try:
                    dpg.set_value("layer_listbox", "")
                except:
                    pass
    
    def select_layer_from_list(self, layer_name):
        """When user clicks on a layer in the listbox, update the input field"""
        if dpg.does_item_exist("layer_custom_input"):
            dpg.set_value("layer_custom_input", layer_name)
    
    def apply_layer_edit_from_modal(self):
        """Apply the layer change from the modal dialog"""
        if not self.editing_layer_mac:
            return
        
        # Get the new layer value from input
        new_layer = dpg.get_value("layer_custom_input") if dpg.does_item_exist("layer_custom_input") else ""
        
        # Close modal
        if dpg.does_item_exist("layer_editor_modal"):
            dpg.delete_item("layer_editor_modal")
        
        # Apply the change
        if new_layer:
            self.on_layer_changed(self.editing_layer_mac, new_layer)
        
        # Clear editing state
        self.editing_layer_mac = None
    
    def update_remote_nowdes_table(self):
        """Update the Remote Nowdes table in the GUI"""
        if not dpg.does_item_exist("remote_nowdes_table"):
            return
        
        # Track which rows we've seen (to remove stale ones)
        seen_macs = set(self.remote_nowdes.keys())
        existing_rows = set()
        
        # Get existing rows
        children = dpg.get_item_children("remote_nowdes_table", slot=1)
        if children:
            for child in children:
                # Extract MAC from row tag (format: "nowde_row_AA:BB:CC:DD:EE:FF")
                tag = dpg.get_item_alias(child)
                if tag and tag.startswith("nowde_row_"):
                    mac = tag[10:]  # Remove "nowde_row_" prefix
                    if mac not in seen_macs:
                        # Remove stale row
                        dpg.delete_item(child)
                    else:
                        existing_rows.add(mac)
        
        # Update or add rows for each remote Nowde, sorted by UUID
        for mac, nowde in sorted(self.remote_nowdes.items(), key=lambda x: x[1].get('uuid', '')):
            # Determine colors based on active status
            active = nowde.get('active', True)
            last_seen_ms = nowde.get('last_seen_ms', 0)
            
            if active and last_seen_ms < 5000:  # Active if seen in last 5 seconds
                # Active: normal colors
                state_text = "ACTIVE"
                state_color = (0, 255, 0)  # Green
                uuid_color = (255, 255, 255)
                version_color = (255, 255, 255)
                layer_color = (255, 255, 255)
            else:
                # Missing: dark red colors
                state_text = "MISSING"
                state_color = (139, 0, 0)  # Dark red
                uuid_color = (150, 80, 80)
                version_color = (150, 80, 80)
                layer_color = (150, 80, 80)
            
            row_tag = f"nowde_row_{mac}"
            uuid_tag = f"nowde_uuid_{mac}"
            version_tag = f"nowde_version_{mac}"
            lastseen_tag = f"nowde_lastseen_{mac}"
            state_tag = f"nowde_state_{mac}"
            layer_btn_tag = f"layer_btn_{mac}"
            
            if mac in existing_rows:
                # Update existing row
                if dpg.does_item_exist(uuid_tag):
                    dpg.set_value(uuid_tag, nowde['uuid'])
                    dpg.configure_item(uuid_tag, color=uuid_color)
                if dpg.does_item_exist(version_tag):
                    dpg.set_value(version_tag, nowde.get('version', '?'))
                    dpg.configure_item(version_tag, color=version_color)
                if dpg.does_item_exist(lastseen_tag):
                    dpg.set_value(lastseen_tag, f"{last_seen_ms}ms ago")
                    dpg.configure_item(lastseen_tag, color=uuid_color)
                if dpg.does_item_exist(state_tag):
                    dpg.set_value(state_tag, state_text)
                    dpg.configure_item(state_tag, color=state_color)
                if dpg.does_item_exist(layer_btn_tag):
                    dpg.configure_item(layer_btn_tag, label=nowde.get('layer', '-'))
            else:
                # Create new row
                with dpg.table_row(parent="remote_nowdes_table", tag=row_tag):
                    dpg.add_text(nowde['uuid'], tag=uuid_tag, color=uuid_color)
                    dpg.add_text(nowde.get('version', '?'), tag=version_tag, color=version_color)
                    dpg.add_text(f"{last_seen_ms}ms ago", tag=lastseen_tag, color=uuid_color)
                    dpg.add_text(state_text, tag=state_tag, color=state_color)
                    dpg.add_button(
                        tag=layer_btn_tag,
                        label=nowde.get('layer', '-'),
                        width=150,
                        callback=lambda s, a, u: self.open_layer_editor(u['mac']),
                        user_data={'mac': mac}
                    )
    
    def handle_osc_message(self, message):
        self.last_osc_time = time.time()
        self.update_osc_status(True)
        
        # Parse Millumin messages
        is_millumin = self.parse_millumin_message(message)
        
        # Log message (filtered or all)
        if self.show_all_messages or is_millumin:
            self.update_osc_log(message)
    
    def parse_millumin_message(self, message):
        """Parse Millumin OSC messages and update layer tracking"""
        # Message format: "/millumin/layer:player2/media/time: (60.70, 596.45)"
        if not message.startswith("/millumin/layer:"):
            return False
        
        try:
            # Split address and args by ": "
            if ": " not in message:
                return False
            
            address, args_str = message.split(": ", 1)
            
            # Extract layer name from /millumin/layer:<name>/rest/of/path
            # Remove "/millumin/layer:" prefix
            path = address[16:]  # Skip "/millumin/layer:"
            
            # Split by first "/" to get layer name and route
            if "/" not in path:
                return False
            
            layer_name, route = path.split("/", 1)
            route = "/" + route  # Add back the leading slash
            
            # Parse arguments - remove parentheses and split by comma
            args_str = args_str.strip().strip("()")
            if args_str:
                # Split by comma and convert to appropriate types
                args = []
                for arg in args_str.split(","):
                    arg = arg.strip()
                    # Try to parse as number
                    try:
                        if "." in arg:
                            args.append(float(arg))
                        else:
                            args.append(int(arg))
                    except ValueError:
                        # It's a string, remove quotes if present
                        args.append(arg.strip("'\""))
                args = tuple(args)
            else:
                args = ()
            
            # Initialize layer if not exists
            if layer_name not in self.layers:
                self.layers[layer_name] = {
                    "state": "stopped",
                    "filename": "",
                    "position": 0.0,
                    "duration": 0.0
                }
            
            layer = self.layers[layer_name]
            
            # Handle different routes
            if route == "/media/time" and len(args) >= 2:
                layer["position"] = float(args[0])
                layer["duration"] = float(args[1])
                layer["state"] = "playing"
            
            elif route == "/mediaStarted" and len(args) >= 2:
                # mediaStarted format: (index, filename, duration)
                layer["filename"] = str(args[1]) if len(args) > 1 else ""
                layer["duration"] = float(args[2]) if len(args) > 2 else 0.0
                layer["position"] = 0.0
                layer["state"] = "playing"
            
            elif route == "/mediaStopped" and len(args) >= 2:
                # mediaStopped format: (index, filename, duration)
                # Clear filename when stopped so media index will be 0
                layer["filename"] = ""
                layer["duration"] = 0.0
                layer["position"] = 0.0  # Reset position to 0
                layer["state"] = "stopped"
            
            # Send to media sync manager (always update, even for stopped state)
            if self.current_nowde_device:
                self.media_sync.update_layer(
                    layer_name=layer_name,
                    filename=layer["filename"],
                    position=layer["position"],
                    duration=layer["duration"],
                    state=layer["state"]
                )
            
            # Update UI table
            self.update_layers_table()
            return True
            
        except Exception as e:
            # If parsing fails, it's not a valid Millumin message
            return False

    def update_osc_log(self, message):
        """Update the OSC log display with auto-scroll"""
        if dpg.does_item_exist("osc_log_text"):
            current_log = dpg.get_value("osc_log_text")
            
            # Clear initial message on first real message
            if current_log.strip() == "Waiting for OSC messages...":
                current_log = ""
            
            new_log = current_log + f"{message}\n"
            
            # Keep only last 1000 lines
            lines = new_log.split('\n')
            if len(lines) > 1000:
                new_log = '\n'.join(lines[-1000:])
            
            dpg.set_value("osc_log_text", new_log)
            
            # Auto-scroll to bottom
            if dpg.does_item_exist("osc_log_window"):
                # Get the y scroll max and set it to scroll to bottom
                dpg.set_y_scroll("osc_log_window", dpg.get_y_scroll_max("osc_log_window"))
    
    def update_layers_table(self):
        """Update the Millumin layers table without clearing and recreating"""
        if not dpg.does_item_exist("layers_table"):
            return
        
        # Update or add rows for each layer
        for layer_name, layer_data in sorted(self.layers.items()):
            row_tag = f"layer_row_{layer_name}"
            
            if layer_name not in self.layer_rows:
                # Create new row
                with dpg.table_row(parent="layers_table", tag=row_tag):
                    dpg.add_text(layer_name, tag=f"{row_tag}_name")
                    
                    # State with color
                    state = layer_data["state"]
                    color = (0, 255, 0) if state == "playing" else (150, 150, 150)
                    dpg.add_text(state.upper(), tag=f"{row_tag}_state", color=color)
                    
                    dpg.add_text(layer_data["filename"], tag=f"{row_tag}_filename")
                    dpg.add_text(f"{layer_data['position']:.2f}s", tag=f"{row_tag}_position")
                    dpg.add_text(f"{layer_data['duration']:.2f}s", tag=f"{row_tag}_duration")
                
                self.layer_rows[layer_name] = row_tag
            else:
                # Update existing row
                state = layer_data["state"]
                if state == "playing": color = (0, 255, 0)
                elif state == "paused": color = (255, 255, 0)
                elif state == "stopped": color = (255, 0, 0)
                else: color = (150, 150, 150)
                
                if dpg.does_item_exist(f"{row_tag}_state"):
                    dpg.set_value(f"{row_tag}_state", state.upper())
                    dpg.configure_item(f"{row_tag}_state", color=color)
                
                if dpg.does_item_exist(f"{row_tag}_filename"):
                    dpg.set_value(f"{row_tag}_filename", layer_data["filename"])
                
                if dpg.does_item_exist(f"{row_tag}_position"):
                    dpg.set_value(f"{row_tag}_position", f"{layer_data['position']:.2f}s")
                
                if dpg.does_item_exist(f"{row_tag}_duration"):
                    dpg.set_value(f"{row_tag}_duration", f"{layer_data['duration']:.2f}s")
    
    def on_toggle_filter(self, sender, app_data):
        """Toggle between showing all messages or only Millumin messages"""
        self.show_all_messages = dpg.get_value("show_all_toggle")
    
    def toggle_osc_logs(self):
        """Toggle visibility of OSC logs section"""
        if dpg.does_item_exist("osc_logs_section"):
            is_visible = dpg.is_item_shown("osc_logs_section")
            if is_visible:
                dpg.hide_item("osc_logs_section")
                dpg.set_value("osc_logs_toggle_btn", "Show Logs")
            else:
                dpg.show_item("osc_logs_section")
                dpg.set_value("osc_logs_toggle_btn", "Hide Logs")
    
    def toggle_nowde_logs(self):
        """Toggle visibility of Nowde logs section"""
        if dpg.does_item_exist("nowde_logs_section"):
            is_visible = dpg.is_item_shown("nowde_logs_section")
            if is_visible:
                dpg.hide_item("nowde_logs_section")
                dpg.set_value("nowde_logs_toggle_btn", "Show Logs")
            else:
                dpg.show_item("nowde_logs_section")
                dpg.set_value("nowde_logs_toggle_btn", "Hide Logs")
    
    def log_nowde_message(self, message):
        """Log Nowde communication message (including SysEx)"""
        if dpg.does_item_exist("midi_log_text"):
            current_log = dpg.get_value("midi_log_text")
            
            # Clear initial message on first real message
            if current_log.strip() == "Waiting for Nowde messages...":
                current_log = ""
            
            timestamp = time.strftime("%H:%M:%S")
            new_log = current_log + f"[{timestamp}] {message}\n"
            
            # Keep only last 1000 lines
            lines = new_log.split('\n')
            if len(lines) > 1000:
                new_log = '\n'.join(lines[-1000:])
            
            dpg.set_value("midi_log_text", new_log)
            
            # Auto-scroll to bottom
            if dpg.does_item_exist("midi_log_window"):
                dpg.set_y_scroll("midi_log_window", dpg.get_y_scroll_max("midi_log_window"))
    
    def refresh_midi_devices(self):
        """Find and connect to first Nowde device (single-device mode)"""
        # Get all available ports (union of input and output)
        try:
            out_ports = set(self.output_manager.get_ports())
            in_ports = set(self.input_manager.get_ports())
            all_ports = sorted(list(out_ports | in_ports))
        except Exception as e:
            print(f"Error getting MIDI ports: {e}")
            # If we can't enumerate ports and had a device, assume disconnection
            if self.current_nowde_device:
                self.disconnect_nowde_device()
            return
        
        # Check if currently connected device is still available
        if self.current_nowde_device:
            device_still_present = self.current_nowde_device in all_ports
            
            if device_still_present:
                # Current device still present and working, keep connection
                return
            else:
                # Current device disconnected
                self.disconnect_nowde_device()
        
        # Only try to connect if we don't have a device
        # Find first device starting with "Nowde"
        if not self.current_nowde_device:
            nowde_device = None
            for port in all_ports:
                if port.startswith("Nowde"):
                    nowde_device = port
                    break
            
            # Connect to the first Nowde found
            if nowde_device:
                self.connect_nowde_device(nowde_device)
    
    def connect_nowde_device(self, device_name):
        """Connect to a Nowde device"""
        # Close existing ports
        self.output_manager.close_port()
        self.input_manager.close_port()
        
        # Open output for OSC→MIDI
        out_success = self.output_manager.open_port(device_name)
        # Open input for monitoring
        in_success = self.input_manager.open_port(device_name)
        
        if out_success or in_success:
            self.current_nowde_device = device_name
            self.selected_port = device_name
            self.update_nowde_status(True, device_name)
            self.update_osc_log(f"Nowde connected: {device_name}")
            
            # Send QUERY_CONFIG to trigger sender to send HELLO + CONFIG_STATE
            # This handles both fresh boot and reconnection scenarios
            if out_success:
                time.sleep(0.1)  # Small delay for port to stabilize
                result = self.output_manager.send_query_config()
                if result and result[0]:
                    success, formatted_msg = result
                    self.log_nowde_message(f"TX: {formatted_msg}")
                    self.update_osc_log("Sent QUERY_CONFIG, waiting for HELLO response...")
        else:
            self.update_osc_log(f"Failed to connect to: {device_name}")
    
    def disconnect_nowde_device(self):
        """Disconnect from Nowde device"""
        if self.current_nowde_device:
            self.output_manager.close_port()
            self.input_manager.close_port()
            self.update_osc_log(f"Nowde disconnected: {self.current_nowde_device}")
            self.current_nowde_device = None
            self.selected_port = None
            self.sender_initialized = False  # Reset initialization flag
            
            # Clear remote nowdes table
            self.remote_nowdes.clear()
            self.update_remote_nowdes_table()
            
            self.update_nowde_status(False, None)
    
    def update_nowde_status(self, connected, device_name=None):
        """Update the Nowde status indicator"""
        if dpg.does_item_exist("nowde_status_indicator"):
            if connected:
                dpg.set_value("nowde_status_indicator", "[OK]")
                dpg.configure_item("nowde_status_indicator", color=(0, 255, 0))
            else:
                dpg.set_value("nowde_status_indicator", "[X]")
                dpg.configure_item("nowde_status_indicator", color=(255, 0, 0))
        
        if dpg.does_item_exist("nowde_status_text"):
            if connected and device_name:
                dpg.set_value("nowde_status_text", f"{device_name}")
                dpg.configure_item("nowde_status_text", color=(0, 255, 0))
            else:
                dpg.set_value("nowde_status_text", "Not connected")
                dpg.configure_item("nowde_status_text", color=(150, 150, 150))
    
    def start_midi_refresh_thread(self):
        """Start background thread to auto-refresh MIDI devices"""
        self.stop_midi_refresh = False
        self.midi_refresh_thread = threading.Thread(target=self.auto_refresh_midi_devices, daemon=True)
        self.midi_refresh_thread.start()
    
    def start_media_sync_thread(self):
        """Start background thread to continuously send media sync packets"""
        self.stop_media_sync = False
        self.media_sync_thread = threading.Thread(target=self.continuous_media_sync, daemon=True)
        self.media_sync_thread.start()
    
    def continuous_media_sync(self):
        """Background thread to continuously send sync packets for all layers"""
        while not self.stop_media_sync:
            time.sleep(self.sync_settings['throttle_interval'])
            
            # Send sync for all tracked layers
            if self.current_nowde_device and self.layers:
                for layer_name, layer_data in self.layers.items():
                    self.media_sync.update_layer(
                        layer_name=layer_name,
                        filename=layer_data["filename"],
                        position=layer_data["position"],
                        duration=layer_data["duration"],
                        state=layer_data["state"]
                    )
    
    def start_running_state_thread(self):
        """Start background thread to query running state every second"""
        self.stop_running_state = False
        
        def running_state_loop():
            while not self.stop_running_state:
                try:
                    # Query running state only if sender is initialized (received HELLO)
                    if self.current_nowde_device and self.output_manager.current_port and self.sender_initialized:
                        self.output_manager.send_query_running_state()
                    time.sleep(1.0)  # 1Hz query rate
                except Exception as e:
                    print(f"Error in running state thread: {e}")
                    time.sleep(1)
        
        self.running_state_thread = threading.Thread(target=running_state_loop, daemon=True)
        self.running_state_thread.start()
        print("Running state query thread started")
    
    def auto_refresh_midi_devices(self):
        """Background thread to periodically check for Nowde devices"""
        last_ports = set()
        
        while not self.stop_midi_refresh:
            time.sleep(2)  # Check every 2 seconds
            
            try:
                # Get all available ports (union of input and output)
                out_ports = set(self.output_manager.get_ports())
                in_ports = set(self.input_manager.get_ports())
                current_ports = out_ports | in_ports
                
                # Only update if ports changed
                if current_ports != last_ports:
                    self.refresh_midi_devices()
                    last_ports = current_ports
            except Exception as e:
                # Handle errors during port enumeration (e.g., device unplugged mid-query)
                print(f"Warning: Error in MIDI device refresh: {e}")
                time.sleep(0.5)  # Short delay before retry

    def update_osc_status(self, active):
        """Update the OSC status indicator"""
        if dpg.does_item_exist("status_indicator"):
            if active:
                dpg.set_value("status_indicator", "[OK]")
                dpg.configure_item("status_indicator", color=(0, 255, 0))
            else:
                dpg.set_value("status_indicator", "[X]")
                dpg.configure_item("status_indicator", color=(255, 0, 0))
        
        if dpg.does_item_exist("status_text"):
            if active:
                text = f"Receiving on {self.osc_address}:{self.osc_port}"
                # color = (0, 255, 0)
                color = (150, 150, 150)
            else:
                if self.is_running:
                    text = f"Listening on {self.osc_address}:{self.osc_port}"
                    color = (150, 150, 150)
                else:
                    text = "Stopped"
                    color = (150, 150, 150)
            dpg.set_value("status_text", text)
            dpg.configure_item("status_text", color=color)
        
        # Show/hide OSC setup note
        if dpg.does_item_exist("osc_setup_note"):
            if active:
                # Hide note when receiving OSC
                dpg.hide_item("osc_setup_note")
            else:
                # Show note when not receiving OSC
                dpg.show_item("osc_setup_note")

    def on_throttle_changed(self, sender, app_data):
        """Callback when throttle slider changes"""
        hz = dpg.get_value("throttle_hz_slider")
        interval = 1.0 / hz
        self.sync_settings['throttle_interval'] = interval
        self.media_sync.set_throttle_interval(interval)
        self.update_osc_log(f"Throttle updated: {hz}Hz ({interval*1000:.1f}ms interval)")
    
    def on_sync_setting_changed(self, sender, app_data):
        """Callback when sync settings are changed"""
        # Update settings from GUI
        if dpg.does_item_exist("mtc_framerate_input"):
            self.sync_settings['mtc_framerate'] = max(1, dpg.get_value("mtc_framerate_input"))
        if dpg.does_item_exist("freewheel_timeout_input"):
            self.sync_settings['freewheel_timeout'] = max(0.1, dpg.get_value("freewheel_timeout_input"))
        if dpg.does_item_exist("desync_threshold_input"):
            self.sync_settings['clock_desync_threshold'] = max(10, dpg.get_value("desync_threshold_input"))
        
        # Send updated settings to Nowde via SysEx (if connected)
        if self.current_nowde_device:
            self.send_sync_settings_to_nowde()
        
        self.update_osc_log(f"Sync settings updated: {self.sync_settings}")
    
    def send_sync_settings_to_nowde(self):
        """Send sync configuration to Nowde (for future SysEx command)"""
        # Placeholder for future SysEx command to configure Nowde settings
        # For now, these settings are only used in Bridge
        pass
    
    def on_rf_sim_changed(self, sender, app_data):
        """Callback when RF simulation checkbox is toggled"""
        rf_sim_enabled = dpg.get_value("rf_sim_checkbox")
        
        # Update config
        self.config['sender_config']['rf_simulation_enabled'] = rf_sim_enabled
        
        # Send to Nowde if connected
        if self.current_nowde_device:
            rf_sim_max_delay = self.config['sender_config']['rf_simulation_max_delay_ms']
            result = self.output_manager.send_push_full_config(rf_sim_enabled, rf_sim_max_delay)
            if result and result[0]:
                success, formatted_msg = result
                self.log_nowde_message(f"TX: {formatted_msg}")
                self.update_osc_log(f"RF Simulation: {'ENABLED' if rf_sim_enabled else 'DISABLED'}")
            else:
                self.update_osc_log("Error: Failed to send RF simulation config")
                # Revert checkbox on failure
                dpg.set_value("rf_sim_checkbox", not rf_sim_enabled)
        else:
            self.update_osc_log("Warning: No Nowde connected, RF simulation setting saved for next connection")
        
        # Save config to file
        self.save_config()
    
    def on_rf_sim_max_delay_changed(self, sender, app_data):
        """Callback when RF simulation max delay slider changes"""
        rf_sim_max_delay = dpg.get_value("rf_sim_max_delay_slider")
        
        # Update config
        self.config['sender_config']['rf_simulation_max_delay_ms'] = rf_sim_max_delay
        
        # Send to Nowde if connected and RF sim is enabled
        if self.current_nowde_device:
            rf_sim_enabled = self.config['sender_config']['rf_simulation_enabled']
            result = self.output_manager.send_push_full_config(rf_sim_enabled, rf_sim_max_delay)
            if result and result[0]:
                success, formatted_msg = result
                self.log_nowde_message(f"TX: {formatted_msg}")
                self.update_osc_log(f"RF Simulation Max Delay: {rf_sim_max_delay}ms")
            else:
                self.update_osc_log("Error: Failed to send RF simulation config")
        else:
            self.update_osc_log("Warning: No Nowde connected, RF simulation setting saved for next connection")
        
        # Save config to file
        self.save_config()
    
    def on_osc_settings_changed(self, sender, app_data):
        """Callback when OSC settings are changed"""
        new_address = dpg.get_value("osc_address_input")
        try:
            new_port = int(dpg.get_value("osc_port_input"))
        except ValueError:
            self.update_osc_log("ERROR: Invalid port number!")
            return
        
        # Check if settings actually changed
        if new_address != self.osc_address or new_port != self.osc_port:
            self.osc_address = new_address
            self.osc_port = new_port
            self.update_osc_log(f"OSC settings changed to {self.osc_address}:{self.osc_port}")
            # Save config
            self.save_config()
            # Restart the bridge with new settings
            self.restart_bridge()
    
    def on_midi_device_changed(self, sender, app_data):
        """Callback when MIDI device is changed (not used with auto-selection)"""
        pass
    
    def start_bridge(self):
        """Start the OSC-MIDI bridge"""
        # Initialize OSC server
        if self.osc_server:
            self.osc_server.stop()
        
        self.osc_server = OSCServer(self.handle_osc_message, address=self.osc_address, port=self.osc_port)
        
        # Auto-detect and connect to first Nowde device
        self.refresh_midi_devices()
        
        # Start OSC server
        self.is_running = True
        self.osc_server.start()
        self.last_osc_time = time.time()
        self.update_osc_log(f"Bridge started on {self.osc_address}:{self.osc_port}")
        
        # Start status check thread
        if self.status_check_thread is None or not self.status_check_thread.is_alive():
            self.status_check_thread = threading.Thread(target=self.check_osc_status, daemon=True)
            self.status_check_thread.start()
    
    def stop_bridge(self):
        """Stop the OSC-MIDI bridge"""
        self.is_running = False
        if self.osc_server:
            self.osc_server.stop()
        self.disconnect_nowde_device()
        self.update_osc_status(False)
        self.update_osc_log("Bridge stopped!")
    
    def restart_bridge(self):
        """Restart the bridge with new settings"""
        self.stop_bridge()
        time.sleep(0.1)  # Small delay to ensure clean shutdown
        self.start_bridge()
    
    def restart_midi_device(self, device_name):
        """Restart MIDI device (kept for compatibility but not used with auto-selection)"""
        pass
    
    def on_quit(self):
        """Callback for Quit button"""
        self.stop_midi_refresh = True
        self.stop_media_sync = True
        if self.is_running:
            self.stop_bridge()
        dpg.stop_dearpygui()
    
    def check_osc_status(self):
        """Background thread to check OSC status"""
        while self.is_running:
            if time.time() - self.last_osc_time > 2:
                self.update_osc_status(False)
            time.sleep(0.5)

    def run(self):
        """Run the DearPyGUI application"""
        # Setup DearPyGUI
        dpg.create_viewport(title="MilluBridge - OSC to MIDI Bridge", width=920, height=750)
        dpg.setup_dearpygui()
        
        # Set primary window
        dpg.set_primary_window("primary_window", True)
        
        # Show viewport
        dpg.show_viewport()
        
        # Main loop
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
        
        # Cleanup
        self.stop_midi_refresh = True
        self.stop_media_sync = True
        self.stop_running_state = True
        if self.is_running:
            self.stop_bridge()
        
        dpg.destroy_context()

if __name__ == '__main__':
    app = MilluBridge()
    app.run()