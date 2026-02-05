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
from dali_control.manager import DaliManager
import time
import threading
import re
import json
import os
from pathlib import Path
import subprocess
import glob
import tempfile
import requests


VERSION = "1.2"

PERSIST_SETTINGS = False  # Toggle when external config storage becomes safe again


def get_config_path():
    """Get platform-appropriate config file path
    
    Returns path to config.json in:
    - macOS: ~/Library/Application Support/MilluBridge/config.json
    - Linux: ~/.config/millubridge/config.json
    - Windows: %APPDATA%/MilluBridge/config.json
    - Fallback: ./config.json (current directory)
    """
    try:
        if os.name == 'posix':
            # macOS and Linux
            if os.uname().sysname == 'Darwin':
                # macOS
                config_dir = Path.home() / "Library" / "Application Support" / "MilluBridge"
            else:
                # Linux
                config_dir = Path.home() / ".config" / "millubridge"
        elif os.name == 'nt':
            # Windows
            appdata = os.getenv('APPDATA')
            config_dir = Path(appdata) / "MilluBridge" if appdata else Path(".")
        else:
            # Fallback
            config_dir = Path(".")
        
        # Create directory if it doesn't exist
        if config_dir != Path("."):
            try:
                config_dir.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError) as e:
                print(f"Warning: Could not create config directory {config_dir}: {e}")
                print("Falling back to current directory for config")
                config_dir = Path(".")
        
        return config_dir / "config.json"
    except Exception as e:
        print(f"Error determining config path: {e}, using current directory")
        return Path(".") / "config.json"

class MediaSyncManager:
    """Manages media synchronization state and throttling for each layer"""
    
    def __init__(self, output_manager, bridge, throttle_interval=0.1):
        self.output_manager = output_manager
        self.bridge = bridge
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
            # Send media sync via SysEx 0x10
            position_ms = int(position * 1000)  # Convert to milliseconds
            # Apply frame correction offset (convert frames to milliseconds based on FPS)
            frame_correction_frames = self.bridge.sync_settings['frame_correction_frames']
            fps = self.bridge.sync_settings['mtc_framerate']
            frame_correction_ms = int((frame_correction_frames / fps) * 1000) if fps > 0 else 0
            corrected_position_ms = max(0, position_ms + frame_correction_ms)
            self.output_manager.send_media_sync(
                layer_name=layer_name,
                media_index=media_index,
                position_ms=corrected_position_ms,
                state=state
            )
            
            layer_state['last_sent_time'] = current_time
            layer_state['last_sent_index'] = media_index
    
    def set_throttle_interval(self, interval):
        """Update throttle interval (in seconds)"""
        self.throttle_interval = max(0.01, interval)  # Minimum 10ms

class MilluBridge:
    def __init__(self, osc_port=None):
        # Load config first
        if PERSIST_SETTINGS:
            self.config_file = str(get_config_path())
            self.config = self.load_config()
        else:
            self.config_file = None
            self.config = self.get_default_config()
        
        # OSC address is always 0.0.0.0 to listen on all interfaces
        self.osc_address = "0.0.0.0"
        # Use provided port or fall back to config
        self.osc_port = osc_port or self.config['gui_preferences']['osc_port']
        self.osc_server = None
        self.output_manager = OutputManager()
        self.input_manager = InputManager(
            sysex_callback=self.handle_sysex_message
        )
        self.dali_manager = DaliManager(status_callback=self.on_dali_status_changed)
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
        
        # MIDI device name mapping (display name -> full name)
        self.nowde_device_map = {}  # {display_name: full_name}
        
        # Millumin layer tracking
        self.layers = {}  # {layer_name: {state, filename, position, duration}}
        self.layer_rows = {}  # {layer_name: row_tag} - track row tags for updates
        self.show_all_messages = False
        
        # Lights tracking
        self.lights = {}  # {channel: value} - track light channel values
        self.light_rows = {}  # {channel: row_tag} - track row tags for updates
        self.dali_channels_present = {}  # {channel: bool} - track if DALI channel is responding
        self.dali_scan_thread = None
        self.stop_dali_scan = False
        self.lights_lock = threading.Lock()  # Protect lights table updates
        
        # Remote Nowdes tracking
        self.remote_nowdes = {}  # {mac: {name, version, layer}}
        self.remote_nowdes_last_update = {}  # {mac: timestamp} - track when we last received update from Nowde
        self.running_state_session = None  # Aggregate chunked RUNNING_STATE responses
        
        # Layer editing modal state
        self.editing_layer_mac = None  # Track which device is being edited
        
        # Simulation state
        self.simulation_settings = {
            'mac': {}  # {mac: 'Disabled' | 'Stop' | '1'-'10'}
        }
        self.simulation_clock_running = False
        self.simulation_clock_duration = 30.0  # seconds
        self.simulation_clock_position = 0.0  # current position
        self.simulation_clock_thread = None
        self.stop_simulation_clock = False
        
        # Media synchronization settings (configurable)
        self.sync_settings = {
            'mtc_framerate': 30,  # fps
            'freewheel_timeout': 3.0,  # seconds
            'clock_desync_threshold': 200,  # milliseconds
            'throttle_interval': 0.1,  # seconds (10Hz)
            'frame_correction_frames': self.config['gui_preferences'].get('frame_correction_frames', 0)  # frames (global timestamp offset)
        }
        
        # Media sync manager
        self.media_sync = MediaSyncManager(self.output_manager, 
                                          self,
                                          throttle_interval=self.sync_settings['throttle_interval'])
        
        # Create DearPyGUI context
        dpg.create_context()
        
        # Configure DearPyGUI to not save ini file (prevents file access permission prompts on macOS)
        # Window positions are saved in our config.json instead
        dpg.configure_app(init_file="")
        
        # Setup window
        self.setup_gui()
        
        # Start MIDI device refresh thread
        self.start_midi_refresh_thread()
        
        # Start media sync thread for continuous updates
        self.start_media_sync_thread()
        
        # Start running state query thread
        self.start_running_state_thread()
        
        # Start DALI scan thread for channel detection
        self.start_dali_scan_thread()
        
        # Auto-start bridge
        self.start_bridge()

    def load_config(self):
        """Load configuration from config.json, forcing RF sim to disabled"""
        if not PERSIST_SETTINGS:
            return self.get_default_config()
        first_run = False
        
        try:
            # Load config from proper location (no migration needed for .app bundles)
            if os.path.exists(self.config_file):
                try:
                    with open(self.config_file, 'r') as f:
                        config = json.load(f)
                except (IOError, OSError, PermissionError) as e:
                    print(f"Error reading config file: {e}, using defaults")
                    return self.get_default_config()
                
                # Force RF simulation OFF on load (safety measure)
                if 'sender_config' in config:
                    config['sender_config']['rf_simulation_enabled'] = False
                
                # Apply defaults for missing keys
                if 'gui_preferences' not in config:
                    config['gui_preferences'] = {}
                
                config['gui_preferences'].setdefault('osc_port', 8000)
                config['gui_preferences'].setdefault('media_sync_throttle_hz', 10)
                config['gui_preferences'].setdefault('frame_correction_frames', 0)
                config['gui_preferences'].setdefault('window_position', [100, 100])
                
                if 'sender_config' not in config:
                    config['sender_config'] = {}
                
                config['sender_config'].setdefault('rf_simulation_enabled', False)
                config['sender_config'].setdefault('rf_simulation_max_delay_ms', 400)
                
                print(f"Config loaded from {self.config_file}")
                return config
            else:
                print(f"No config file found, creating with defaults")
                first_run = True
                config = self.get_default_config()
                
                # Save default config for first run (with error handling)
                try:
                    with open(self.config_file, 'w') as f:
                        json.dump(config, f, indent=2)
                    print(f"✅ Default config saved to {self.config_file}")
                except (IOError, OSError, PermissionError) as e:
                    print(f"⚠️ Could not save default config: {e}")
                    print("Config will be kept in memory only")
                
                return config
                
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
                "osc_port": 8000,
                "media_sync_throttle_hz": 10,
                "frame_correction_frames": 0
            }
        }
    
    def save_config(self):
        """Save current configuration to config.json"""
        if not PERSIST_SETTINGS:
            return False
        try:
            # Update config from current state
            self.config['gui_preferences']['osc_port'] = self.osc_port
            
            # Calculate throttle Hz from interval
            if self.sync_settings['throttle_interval'] > 0:
                self.config['gui_preferences']['media_sync_throttle_hz'] = int(1.0 / self.sync_settings['throttle_interval'])
            
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            print(f"Config saved to {self.config_file}")
            return True
        except (IOError, OSError, PermissionError) as e:
            print(f"Error saving config (file access): {e}")
            return False
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def setup_gui(self):
        """Setup the DearPyGUI interface"""
        with dpg.window(label="MilluBridge - OSC to MIDI Bridge", tag="primary_window", 
                       width=900, height=700, no_close=True):
            
            # Header with version in top right
            with dpg.table(header_row=False, borders_innerH=False, borders_innerV=False, 
                          borders_outerH=False, borders_outerV=False):
                dpg.add_table_column(width_stretch=True)
                dpg.add_table_column(width_fixed=True)
                with dpg.table_row():
                    dpg.add_text("Millumin Settings", color=(150, 200, 255))
                    dpg.add_text(f"v{VERSION}", color=(120, 120, 120))
            with dpg.group(horizontal=True):
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
                                  min_value=1, max_value=60, width=100,
                                  callback=self.on_throttle_changed)
                dpg.add_text("  MTC:")
                dpg.add_input_int(tag="mtc_framerate_input", 
                                 default_value=self.sync_settings['mtc_framerate'],
                                 width=30, step=0, on_enter=True,
                                 callback=self.on_sync_setting_changed)
                dpg.add_text("fps  ")
            
                dpg.add_text("Freewheel:")
                dpg.add_input_float(tag="freewheel_timeout_input",
                                   default_value=self.sync_settings['freewheel_timeout'],
                                   width=30, step=0, format="%.1f", on_enter=True,
                                   callback=self.on_sync_setting_changed)
                dpg.add_text("s. ")
                dpg.add_text("Desync max:")
                dpg.add_input_int(tag="desync_threshold_input",
                                 default_value=self.sync_settings['clock_desync_threshold'],
                                 width=40, step=0, on_enter=True,
                                 callback=self.on_sync_setting_changed)
                dpg.add_text("ms")
            
            with dpg.group(horizontal=True):
                dpg.add_text("Correction:")
                dpg.add_input_int(tag="frame_correction_input",
                                 default_value=self.sync_settings['frame_correction_frames'],
                                 width=80, step=1, on_enter=True,
                                 callback=self.on_sync_setting_changed)
                dpg.add_text("frames (global timestamp offset)")
            
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
            
            # Split layout: Millumin Layers (left 3/4) and Lights (right 1/4)
            with dpg.group(horizontal=True):
                # Left 3/4 - Millumin Layers section
                with dpg.child_window(width=-250, height=200, border=False):
                    dpg.add_text("MilluBridge Layers", color=(150, 200, 255))
                    with dpg.table(header_row=True, tag="layers_table", 
                                  borders_innerH=True, borders_outerH=True, 
                                  borders_innerV=True, borders_outerV=True,
                                  row_background=True, resizable=True, height=-1):
                        dpg.add_table_column(label="Layers", width_fixed=True, init_width_or_weight=150)
                        dpg.add_table_column(label="State", width_fixed=True, init_width_or_weight=60)
                        dpg.add_table_column(label="Filename", width_stretch=True)
                        dpg.add_table_column(label="Position", width_fixed=True, init_width_or_weight=80)
                        dpg.add_table_column(label="Duration", width_fixed=True, init_width_or_weight=80)
                
                # Right 1/4 - Lights section
                with dpg.child_window(width=-1, height=200, border=False):
                    dpg.add_text("MilluBridge Lights", color=(150, 200, 255))
                    with dpg.table(header_row=True, tag="lights_table",
                                  borders_innerH=True, borders_outerH=True,
                                  borders_innerV=True, borders_outerV=True,
                                  row_background=True, resizable=True, height=-1):
                        dpg.add_table_column(label="Channel", width_fixed=True, init_width_or_weight=80)
                        dpg.add_table_column(label="Value", width_fixed=True, init_width_or_weight=60)
                        dpg.add_table_column(label="Status", width_stretch=True)
            
            dpg.add_separator()
            
            # Split layout: Local Nowde (left 3/4) and Dali Master (right 1/4)
            with dpg.group(horizontal=True):
                # Left 2/3 - Local Nowde section
                with dpg.child_window(width=-250, height=120, border=False):
                    dpg.add_text("Local Nowde", color=(150, 200, 255))
                    # Nowde device selection
                    with dpg.group(horizontal=True):
                        dpg.add_text("Select Device:")
                        dpg.add_combo(tag="nowde_device_combo", items=["Scanning..."], width=250,
                                     callback=self.on_nowde_device_selected)
                        dpg.add_button(label="Refresh", callback=self.manual_refresh_nowde_devices, width=80)
                    
                    with dpg.group(horizontal=True):
                        dpg.add_text("USB Status:")
                        dpg.add_text("[X]", tag="nowde_status_indicator", color=(255, 0, 0))  # Red by default
                        dpg.add_text("Not connected", tag="nowde_status_text", color=(150, 150, 150))
                        dpg.add_button(label="Show Logs", tag="nowde_logs_toggle_btn", callback=self.toggle_nowde_logs, width=100)
                    
                    # Nowde version and firmware upgrade
                    with dpg.group(horizontal=True):
                        dpg.add_text("Nowde Version:")
                        dpg.add_text("--", tag="firmware_version_text", color=(150, 150, 150))
                        dpg.add_spacer(width=20)
                        dpg.add_button(label="Upgrade Firmware", tag="upgrade_nowde_btn",
                                     callback=self.upgrade_nowde_firmware, width=150)
                    dpg.add_progress_bar(tag="firmware_upload_progress", 
                                        default_value=0.0, width=-1, show=False)
                    dpg.add_text("", tag="firmware_upload_status", color=(150, 150, 150))
                
                # Right 1/3 - Dali Master section
                with dpg.child_window(width=-1, height=120, border=False):
                    dpg.add_text("Dali Master", color=(150, 200, 255))
                    
                    # DALI status
                    with dpg.group(horizontal=True):
                        dpg.add_text("USB Status:")
                        dpg.add_text("[X]", tag="dali_status_indicator", color=(255, 0, 0))  # Red by default
                        dpg.add_text("Not connected", tag="dali_status_text", color=(150, 150, 150))
                    
                    dpg.add_spacer(height=10)
                    
                    # DALI control buttons
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Blackout", callback=self.dali_blackout, width=115)
                        dpg.add_button(label="All On", callback=self.dali_all_on, width=115)
            
            dpg.add_separator()
            
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
                dpg.add_table_column(label="State", width_fixed=True, init_width_or_weight=80)
                dpg.add_table_column(label="Index", width_fixed=True, init_width_or_weight=60)
                dpg.add_table_column(label="Layer", width_fixed=True, init_width_or_weight=150)
                dpg.add_table_column(label="Simulate", width_fixed=True, init_width_or_weight=100)
            
            dpg.add_separator()
            
            # Simulation Clock control
            dpg.add_text("Media Simulation", color=(150, 200, 255))
            with dpg.group(horizontal=True):
                dpg.add_text("Duration:")
                dpg.add_slider_float(tag="sim_clock_duration_slider",
                                    default_value=30.0,
                                    min_value=5.0, max_value=120.0,
                                    width=150, format="%.1f",
                                    callback=self.on_sim_clock_duration_changed)
                dpg.add_text("s")
                dpg.add_button(label="Start/Stop", tag="sim_clock_btn",
                             callback=self.toggle_simulation_clock, width=100)
                dpg.add_text("Stopped", tag="sim_clock_status", color=(150, 150, 150))
                dpg.add_spacer(width=10)
                dpg.add_text("Position:")
                dpg.add_text("0.0s / 30.0s", tag="sim_clock_position_text", color=(150, 150, 150))
            
            # RF Simulation control
            with dpg.group(horizontal=True):
                dpg.add_checkbox(label="Simulate Bad RF", tag="rf_sim_checkbox",
                               default_value=self.config['sender_config']['rf_simulation_enabled'],
                               callback=self.on_rf_sim_changed)
                dpg.add_slider_int(tag="rf_sim_max_delay_slider",
                                 default_value=self.config['sender_config']['rf_simulation_max_delay_ms'],
                                 min_value=1, max_value=1000, width=100,
                                 callback=self.on_rf_sim_max_delay_changed)
                dpg.add_text("ms")

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
            
            # Update firmware version display
            dpg.set_value("firmware_version_text", version)
            dpg.configure_item("firmware_version_text", color=(100, 255, 100))  # Green when connected
            
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
            import time
            current_time = time.time()

            total_receivers = data.get('total_receivers', len(data['receivers']))
            chunk_index = data.get('chunk_index', 0)
            chunk_count = max(1, data.get('chunk_count', 1))
            chunk_payload = data.get('chunk_receiver_count', len(data['receivers']))

            session = self.running_state_session
            reset_session = False

            if session is None:
                reset_session = True
            else:
                timed_out = (current_time - session.get('timestamp', 0)) > 5.0
                mismatched = session.get('chunk_count') != chunk_count or session.get('total_receivers') != total_receivers
                if chunk_index == 0 or timed_out or mismatched:
                    reset_session = True

            if reset_session:
                session = {
                    'timestamp': current_time,
                    'chunk_count': chunk_count,
                    'total_receivers': total_receivers,
                    'received_chunks': set(),
                    'chunks': {}
                }
                self.running_state_session = session

            if chunk_index >= chunk_count:
                clamped_index = max(0, chunk_count - 1)
                print(f"[DEBUG] RUNNING_STATE: chunk index {chunk_index} out of range, clamping to {clamped_index}")
                chunk_index = clamped_index

            session['timestamp'] = current_time
            session['received_chunks'].add(chunk_index)
            session['chunks'][chunk_index] = data['receivers']

            if len(session['received_chunks']) == session['chunk_count']:
                receivers = []
                for idx in range(session['chunk_count']):
                    receivers.extend(session['chunks'].get(idx, []))

                self._apply_running_state_receivers(
                    receivers,
                    current_time,
                    data.get('mesh_synced', False),
                    data.get('uptime_s', 0.0),
                    total_receivers
                )
                self.running_state_session = None
        
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
    
    def _apply_running_state_receivers(self, receivers, current_time, mesh_synced, uptime_s, total_receivers):
        """Apply a fully aggregated RUNNING_STATE update to the remote Nowde table."""
        received_macs = set()
        receiver_count = len(receivers)

        # Only log detailed receiver info if count changed
        if receiver_count != len(self.remote_nowdes):
            print(
                f"\n[DEBUG] RUNNING_STATE: {receiver_count} receivers from Nowde"
                + (f" (expected {total_receivers})" if receiver_count != total_receivers else "")
            )
            for idx, receiver in enumerate(receivers):
                print(
                    f"  [{idx}] MAC: {receiver['mac']}, Layer: '{receiver['layer']}', "
                    f"Version: {receiver['version']}, LastSeen: {receiver['last_seen_ms']}ms, "
                    f"Active: {receiver['active']}, MediaIdx: {receiver['media_index']}"
                )

        for receiver in receivers:
            self.remote_nowdes[receiver['mac']] = receiver
            self.remote_nowdes_last_update[receiver['mac']] = current_time
            received_macs.add(receiver['mac'])

        # For devices not present in this update, increment their last_seen_ms so UI ageing works
        for mac in list(self.remote_nowdes.keys()):
            if mac not in received_macs:
                # Store the base time when device first went missing (don't overwrite if already set)
                if '_base_last_seen_ms' not in self.remote_nowdes[mac]:
                    self.remote_nowdes[mac]['_base_last_seen_ms'] = self.remote_nowdes[mac].get('last_seen_ms', 0)
                    self.remote_nowdes[mac]['_missing_since'] = current_time
                
                # Calculate elapsed time since device first went missing
                missing_since = self.remote_nowdes[mac].get('_missing_since', current_time)
                elapsed_ms = int((current_time - missing_since) * 1000)
                
                # Update last_seen_ms = base + elapsed
                base_last_seen = self.remote_nowdes[mac]['_base_last_seen_ms']
                self.remote_nowdes[mac]['last_seen_ms'] = base_last_seen + elapsed_ms

        # Update GUI (handles 15-minute removal logic)
        self.update_remote_nowdes_table()

        mesh_status = "SYNCED" if mesh_synced else "NOT SYNCED"
        self.update_osc_log(
            f"Running state: Uptime {uptime_s:.1f}s, Mesh {mesh_status}, {total_receivers} receiver(s)"
        )

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
    
    def format_device_name(self, full_name):
        """Format device name for display - keep only part before ':' """
        if ':' in full_name:
            return full_name.split(':', 1)[0]
        return full_name
    
    def update_remote_nowdes_table(self):
        """Update the Remote Nowdes table in the GUI"""
        if not dpg.does_item_exist("remote_nowdes_table"):
            return
        
        # Track which rows we've seen (to remove stale ones after 15 min)
        seen_macs = set(self.remote_nowdes.keys())
        existing_rows = set()
        
        # Initialize simulation settings for new devices
        for mac in seen_macs:
            if mac not in self.simulation_settings['mac']:
                self.simulation_settings['mac'][mac] = 'Disabled'
        
        # Get existing rows
        children = dpg.get_item_children("remote_nowdes_table", slot=1)
        if children:
            for child in children:
                # Extract MAC from row tag (format: "nowde_row_AA:BB:CC:DD:EE:FF")
                tag = dpg.get_item_alias(child)
                if tag and tag.startswith("nowde_row_"):
                    mac = tag[10:]  # Remove "nowde_row_" prefix
                    
                    # If USB midi sender is disconnected, clear all rows immediately
                    if len(seen_macs) == 0:
                        dpg.delete_item(child)
                        continue
                    
                    # For devices in the dict, check if they've been GONE for 15 minutes
                    if mac in seen_macs:
                        nowde = self.remote_nowdes[mac]
                        last_seen_ms = nowde.get('last_seen_ms', 0)
                        # Remove if GONE (>10s) for more than 15 minutes total (900000ms)
                        if last_seen_ms > 900000:  # 15 minutes since last seen
                            dpg.delete_item(child)
                            # Also remove from dict to stop tracking it
                            del self.remote_nowdes[mac]
                        else:
                            existing_rows.add(mac)
        
        # Update or add rows for each remote Nowde, sorted by UUID
        for mac, nowde in sorted(self.remote_nowdes.items(), key=lambda x: x[1].get('uuid', '')):
            # Determine colors based on last seen time (3-state)
            active = nowde.get('active', True)
            last_seen_ms = nowde.get('last_seen_ms', 0)
            media_index = nowde.get('media_index', 0)
            
            if active and last_seen_ms < 3000:  # < 3s = ACTIVE
                state_text = "ACTIVE"
                state_color = (0, 255, 0)  # Green
                text_color = (255, 255, 255)
            elif last_seen_ms < 10000:  # 3s-10s = MISSING (matches ESP32 removal timeout)
                state_text = "MISSING"
                state_color = (255, 255, 0)  # Yellow
                text_color = (200, 200, 150)
            else:  # > 10s = GONE
                state_text = "GONE"
                state_color = (255, 0, 0)  # Red
                text_color = (150, 80, 80)
            
            row_tag = f"nowde_row_{mac}"
            uuid_tag = f"nowde_uuid_{mac}"
            version_tag = f"nowde_version_{mac}"
            state_tag = f"nowde_state_{mac}"
            index_tag = f"nowde_index_{mac}"
            layer_btn_tag = f"layer_btn_{mac}"
            sim_combo_tag = f"sim_combo_{mac}"
            
            if mac in existing_rows:
                # Update existing row
                if dpg.does_item_exist(uuid_tag):
                    dpg.set_value(uuid_tag, nowde['uuid'])
                    dpg.configure_item(uuid_tag, color=text_color)
                if dpg.does_item_exist(version_tag):
                    dpg.set_value(version_tag, nowde.get('version', '?'))
                    dpg.configure_item(version_tag, color=text_color)
                if dpg.does_item_exist(state_tag):
                    dpg.set_value(state_tag, state_text)
                    dpg.configure_item(state_tag, color=state_color)
                if dpg.does_item_exist(index_tag):
                    index_str = str(media_index) if media_index > 0 else "-"
                    dpg.set_value(index_tag, index_str)
                    dpg.configure_item(index_tag, color=text_color)
                if dpg.does_item_exist(layer_btn_tag):
                    dpg.configure_item(layer_btn_tag, label=nowde.get('layer', '-'))
                # Simulation combo is handled by callback, no need to update
            else:
                # Create new row
                sim_options = ['Disabled', 'Stop'] + [str(i) for i in range(1, 11)]
                current_sim = self.simulation_settings['mac'].get(mac, 'Disabled')
                
                with dpg.table_row(parent="remote_nowdes_table", tag=row_tag):
                    dpg.add_text(nowde['uuid'], tag=uuid_tag, color=text_color)
                    dpg.add_text(nowde.get('version', '?'), tag=version_tag, color=text_color)
                    dpg.add_text(state_text, tag=state_tag, color=state_color)
                    index_str = str(media_index) if media_index > 0 else "-"
                    dpg.add_text(index_str, tag=index_tag, color=text_color)
                    dpg.add_button(
                        tag=layer_btn_tag,
                        label=nowde.get('layer', '-'),
                        width=140,
                        callback=lambda s, a, u: self.open_layer_editor(u['mac']),
                        user_data={'mac': mac}
                    )
                    dpg.add_combo(
                        tag=sim_combo_tag,
                        items=sim_options,
                        default_value=current_sim,
                        width=90,
                        callback=lambda s, a, u: self.on_simulation_mode_changed(u['mac'], a),
                        user_data={'mac': mac}
                    )
        
        # Auto-manage simulation clock based on current remote states
        # (e.g., if all simulating devices disconnected, stop the clock)
        self._auto_manage_simulation_clock()
    
    def handle_osc_message(self, message):
        self.last_osc_time = time.time()
        self.update_osc_status(True)
        
        # Parse Millumin messages (layers)
        is_millumin = self.parse_millumin_message(message)
        
        # Parse light messages
        is_light = self.parse_light_message(message)
        
        # Log message (filtered or all)
        if self.show_all_messages or is_millumin or is_light:
            self.update_osc_log(message)
    
    def is_layer_in_simulation(self, layer_name):
        """Check if any Remote Nowde is simulating this layer"""
        for mac, nowde in self.remote_nowdes.items():
            if nowde.get('layer') == layer_name:
                sim_mode = self.simulation_settings['mac'].get(mac, 'Disabled')
                if sim_mode != 'Disabled':
                    return True
        return False
    
    def parse_light_message(self, message):
        """Parse light OSC messages and update light tracking"""
        # Message format: "/L1: (255,)" or "/L1: 255" or "/L1 255"
        if not message.startswith("/L"):
            return False
        
        try:
            # Split address and value
            # Handle both formats: "/L1: 255" and "/L1 255"
            if ": " in message:
                address, value_str = message.split(": ", 1)
            elif " " in message:
                address, value_str = message.split(" ", 1)
            else:
                return False
            
            # Extract channel number from /L<channel>
            channel_str = address[2:]  # Skip "/L"
            
            # Parse channel number
            try:
                channel = int(channel_str)
            except ValueError:
                return False
            
            # Parse value (remove parentheses, commas, and whitespace)
            value_str = value_str.strip().strip("()").strip(",").strip()
            
            # Handle empty value
            if not value_str:
                return False
            
            try:
                value = int(float(value_str))  # Convert to int (handles both int and float strings)
            except ValueError:
                return False
            
            # Clamp value to 0-255 range
            value = max(0, min(255, value))
            
            # Update lights dictionary (thread-safe)
            with self.lights_lock:
                self.lights[channel] = value
            
            # Immediately push to DALI if connected
            if self.dali_manager and self.dali_manager.is_connected:
                dali_address = channel - 1  # L1 -> DALI 0, L2 -> DALI 1, etc.
                if 0 <= dali_address <= 63:
                    self.dali_manager.set_level(dali_address, value)
            
            # Update UI table
            self.update_lights_table()
            
            return True
            
        except Exception as e:
            # If parsing fails, it's not a valid light message
            return False
    
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
            
            # Check if this layer is being simulated - if so, discard real messages
            if self.is_layer_in_simulation(layer_name):
                # Silently ignore real OSC for simulated layers
                return True  # Return True to indicate message was "handled" (by ignoring it)
            
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
                # Only set state to playing if we have a filename (media has started)
                # This prevents sending mediaIndex=0 when /media/time arrives before /mediaStarted
                if layer["filename"]:
                    layer["state"] = "playing"
            
            elif route == "/mediaStarted" and len(args) >= 2:
                # mediaStarted format: (index, filename, duration)
                layer["filename"] = str(args[1]) if len(args) > 1 else ""
                layer["duration"] = float(args[2]) if len(args) > 2 else 0.0
                layer["position"] = 0.0
                layer["state"] = "playing"
            
            elif route == "/mediaStopped" and len(args) >= 2:
                # mediaStopped format: (index, filename, duration)
                stopped_filename = str(args[1]) if len(args) > 1 else ""
                
                # Only apply stop if the stopped filename matches current playing filename
                # This prevents old mediaStopped messages from stopping newly started media
                # when switching media without explicit stop (Millumin behavior)
                if layer["filename"] == stopped_filename or layer["filename"] == "":
                    layer["filename"] = ""
                    layer["duration"] = 0.0
                    layer["position"] = 0.0
                    layer["state"] = "stopped"
                # else: ignore - a new media is already playing
            
            # Send to media sync manager (only if we have valid state)
            # Skip sending if state=stopped and we have no filename (prevents spurious updates)
            if self.current_nowde_device:
                # Only send updates when:
                # 1. Playing with a valid filename, OR
                # 2. Stopped (to signal stop)
                should_send = (layer["state"] == "playing" and layer["filename"]) or (layer["state"] == "stopped")
                
                if should_send:
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
        
        # Get current layers (excluding simulated ones), sorted alphabetically
        current_layers = sorted(
            [(name, data) for name, data in self.layers.items() if not self.is_layer_in_simulation(name)],
            key=lambda x: x[0].lower()
        )
        current_layer_names = [name for name, _ in current_layers]
        existing_layer_names = [name for name in self.layer_rows.keys() if not self.is_layer_in_simulation(name)]
        
        # Check if we need to rebuild the table (new layer or order changed)
        needs_rebuild = current_layer_names != existing_layer_names
        
        if needs_rebuild:
            # Clear all existing rows
            for layer_name in list(self.layer_rows.keys()):
                row_tag = f"layer_row_{layer_name}"
                if dpg.does_item_exist(row_tag):
                    dpg.delete_item(row_tag)
            self.layer_rows.clear()
        
        # Update or add rows for each layer, sorted alphabetically
        for layer_name, layer_data in current_layers:
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
    
    def update_lights_table(self):
        """Update the Lights table - always rebuild for consistency"""
        if not dpg.does_item_exist("lights_table"):
            return
        
        with self.lights_lock:
            # Always clear and rebuild to avoid stale state issues
            for channel in list(self.light_rows.keys()):
                row_tag = f"light_row_{channel}"
                if dpg.does_item_exist(row_tag):
                    dpg.delete_item(row_tag)
            self.light_rows.clear()
            
            # Take snapshots of current state
            declared_channels = dict(self.lights)  # {channel: value}
            presence_status = dict(self.dali_channels_present)  # {channel: bool}
        
        # Collect detected-only channels (from DALI scan, present but not declared)
        detected_only_channels = set()
        for channel, is_present in presence_status.items():
            if is_present and channel not in declared_channels and 1 <= channel <= 16:
                detected_only_channels.add(channel)
        
        # Sort: declared channels first, then detected-only at bottom
        declared_sorted = sorted(declared_channels.keys())
        detected_sorted = sorted(detected_only_channels)
        
        # Add declared channels (normal display)
        for channel in declared_sorted:
            value = declared_channels[channel]
            row_tag = f"light_row_{channel}"
            
            # Get DALI presence status for this channel
            is_present = presence_status.get(channel, None)
            if is_present is None:
                status_text = "..."
                status_color = (150, 150, 150)
            elif is_present:
                status_text = "OK"
                status_color = (0, 255, 0)
            else:
                status_text = "No Response"
                status_color = (255, 165, 0)
            
            with dpg.table_row(parent="lights_table", tag=row_tag):
                # Clickable channel name for identify
                dpg.add_button(
                    label=f"L{channel}", 
                    tag=f"{row_tag}_channel",
                    callback=lambda s, a, u: self.identify_channel(u),
                    user_data=channel,
                    width=-1
                )
                dpg.add_text(str(value), tag=f"{row_tag}_value")
                dpg.add_text(status_text, tag=f"{row_tag}_status", color=status_color)
            
            self.light_rows[channel] = row_tag
        
        # Add detected-only channels at bottom (greyed display, no value)
        for channel in detected_sorted:
            row_tag = f"light_row_{channel}"
            
            # These are always present (that's why they're in detected_only)
            status_text = "OK"
            status_color = (0, 255, 0)
            
            with dpg.table_row(parent="lights_table", tag=row_tag):
                # Clickable channel name for identify (greyed style)
                dpg.add_button(
                    label=f"L{channel}", 
                    tag=f"{row_tag}_channel",
                    callback=lambda s, a, u: self.identify_channel(u),
                    user_data=channel,
                    width=-1
                )
                dpg.bind_item_theme(f"{row_tag}_channel", "greyed_button_theme") if dpg.does_item_exist("greyed_button_theme") else None
                dpg.add_text("", tag=f"{row_tag}_value")
                dpg.add_text(status_text, tag=f"{row_tag}_status", color=status_color)
            
            self.light_rows[channel] = row_tag
    
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
        """Refresh available Nowde devices and update dropdown"""
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
        
        # Filter for Nowde devices
        nowde_devices = [port for port in all_ports if port.startswith("Nowde")]
        
        # Update combo box with available Nowde devices
        if dpg.does_item_exist("nowde_device_combo"):
            if nowde_devices:
                # Create display names (short) and map them to full names
                self.nowde_device_map = {}
                display_names = []
                for dev in nowde_devices:
                    display_name = self.format_device_name(dev)
                    display_names.append(display_name)
                    self.nowde_device_map[display_name] = dev
                
                dpg.configure_item("nowde_device_combo", items=display_names)
                # If connected device is still in the list, keep it selected
                if self.current_nowde_device in nowde_devices:
                    idx = nowde_devices.index(self.current_nowde_device)
                    dpg.set_value("nowde_device_combo", display_names[idx])
                # If no device connected, auto-connect to first available
                elif not self.current_nowde_device:
                    dpg.set_value("nowde_device_combo", display_names[0])
                    self.connect_nowde_device(nowde_devices[0])
            else:
                dpg.configure_item("nowde_device_combo", items=["No Nowde devices found"])
                dpg.set_value("nowde_device_combo", "No Nowde devices found")
        
        # Check if currently connected device is still available
        if self.current_nowde_device:
            device_still_present = self.current_nowde_device in all_ports
            
            if not device_still_present:
                # Current device disconnected
                self.disconnect_nowde_device()
    
    def manual_refresh_nowde_devices(self):
        """Manual refresh button callback"""
        self.refresh_midi_devices()
        self.update_osc_log("Refreshed Nowde device list")
    
    def on_nowde_device_selected(self, sender, app_data):
        """Callback when user selects a Nowde device from dropdown"""
        selected_display_name = app_data
        
        # Ignore placeholder values
        if selected_display_name in ["Scanning...", "No Nowde devices found"]:
            return
        
        # Map display name back to full device name
        selected_device = self.nowde_device_map.get(selected_display_name, selected_display_name)
        
        # If already connected to this device, do nothing
        if self.current_nowde_device == selected_device:
            return
        
        # Connect to the selected device
        self.connect_nowde_device(selected_device)
    
    def connect_nowde_device(self, device_name):
        """Connect to a Nowde device"""
        # Close existing ports and clear remote nowdes if switching devices
        if self.current_nowde_device and self.current_nowde_device != device_name:
            # Switching to a different device - clear remote nowdes table
            self.remote_nowdes.clear()
            self.update_remote_nowdes_table()
            self.update_osc_log(f"Switched from {self.current_nowde_device} to {device_name} - remote table cleared")
        
        self.output_manager.close_port()
        self.input_manager.close_port()
        
        # Open output for OSC→MIDI
        out_success = self.output_manager.open_port(device_name)
        # Open input for monitoring
        in_success = self.input_manager.open_port(device_name)
        
        if out_success or in_success:
            self.current_nowde_device = device_name
            self.selected_port = device_name
            
            # Update combo box selection
            if dpg.does_item_exist("nowde_device_combo"):
                dpg.set_value("nowde_device_combo", self.format_device_name(device_name))
            
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
            
            # Reset firmware version display
            if dpg.does_item_exist("firmware_version_text"):
                dpg.set_value("firmware_version_text", "--")
                dpg.configure_item("firmware_version_text", color=(150, 150, 150))
            
            # Clear remote nowdes table and tracking
            self.remote_nowdes.clear()
            self.remote_nowdes_last_update.clear()
            self.update_remote_nowdes_table()
            
            # Update combo box to show no selection
            if dpg.does_item_exist("nowde_device_combo"):
                current_items = dpg.get_item_configuration("nowde_device_combo").get("items", [])
                if current_items and current_items[0] != "No Nowde devices found":
                    dpg.set_value("nowde_device_combo", "")
            
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
                dpg.set_value("nowde_status_text", f"{self.format_device_name(device_name)}")
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
        """Start background thread to query running state periodically"""
        self.stop_running_state = False
        
        def running_state_loop():
            while not self.stop_running_state:
                try:
                    # Query running state only if sender is initialized (received HELLO)
                    if self.current_nowde_device and self.output_manager.current_port and self.sender_initialized:
                        self.output_manager.send_query_running_state()
                    time.sleep(2.0)  # 0.5Hz query rate to reduce large SysEx bursts
                except Exception as e:
                    print(f"Error in running state thread: {e}")
                    time.sleep(1)
        
        self.running_state_thread = threading.Thread(target=running_state_loop, daemon=True)
        self.running_state_thread.start()
        print("Running state query thread started")
    
    def start_dali_scan_thread(self):
        """Start background thread to scan for DALI channel presence"""
        self.stop_dali_scan = False
        
        def dali_scan_loop():
            # Initial delay to let connection stabilize
            time.sleep(2)
            
            while not self.stop_dali_scan:
                try:
                    # Scan DALI addresses 0-15 (L1-L16)
                    if self.dali_manager and self.dali_manager.is_connected:
                        # Collect all scan results first
                        scan_results = {}
                        for dali_address in range(16):
                            channel = dali_address + 1  # DALI 0 -> L1, DALI 1 -> L2, etc.
                            is_present = self.dali_manager.check_channel_present(dali_address)
                            scan_results[channel] = is_present
                        
                        # Update all results atomically
                        with self.lights_lock:
                            self.dali_channels_present.clear()
                            self.dali_channels_present.update(scan_results)
                        
                        detected = [ch for ch, present in scan_results.items() if present]
                        if detected:
                            print(f"[DALI] Scan complete: detected L{', L'.join(map(str, detected))}")
                        
                        # Update UI once after all scanning is done
                        self.update_lights_table()
                    
                    # Scan every 30 seconds (conservative to avoid congestion)
                    time.sleep(30)
                except Exception as e:
                    print(f"Error in DALI scan thread: {e}")
                    time.sleep(30)
        
        self.dali_scan_thread = threading.Thread(target=dali_scan_loop, daemon=True)
        self.dali_scan_thread.start()
    
    def identify_channel(self, channel: int):
        """Run identify pattern (OFF/ON/OFF/ON/OFF) on a DALI channel"""
        if not self.dali_manager or not self.dali_manager.is_connected:
            self.update_osc_log(f"DALI: Cannot identify L{channel} - not connected")
            return
        
        def identify_sequence():
            dali_address = channel - 1
            if not (0 <= dali_address <= 63):
                return
            
            # Get original value
            with self.lights_lock:
                original_value = self.lights.get(channel, 0)
            
            try:
                # OFF/ON/OFF/ON/OFF pattern
                pattern = [0, 254, 0, 254, 0, 254, 0]
                for level in pattern:
                    self.dali_manager.set_level(dali_address, level)
                    time.sleep(0.2)
                
                # Restore original value
                self.dali_manager.set_level(dali_address, original_value)
            except Exception as e:
                print(f"Error in identify sequence: {e}")
        
        # Run in background thread to not block GUI
        threading.Thread(target=identify_sequence, daemon=True).start()
        self.update_osc_log(f"DALI: Identifying L{channel}")
    
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
                text = f"Receiving on port {self.osc_port}"
                # color = (0, 255, 0)
                color = (150, 150, 150)
            else:
                if self.is_running:
                    text = f"Listening on port {self.osc_port}"
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
        if dpg.does_item_exist("frame_correction_input"):
            self.sync_settings['frame_correction_frames'] = dpg.get_value("frame_correction_input")
        
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
    
    def upgrade_nowde_firmware(self):
        """Upgrade Nowde firmware from GitHub"""
        if not self.current_nowde_device:
            self.update_osc_log("ERROR: No Nowde connected")
            if dpg.does_item_exist("firmware_upload_status"):
                dpg.set_value("firmware_upload_status", "No Nowde connected")
                dpg.configure_item("firmware_upload_status", color=(255, 0, 0))
            return
        
        # Update status
        if dpg.does_item_exist("firmware_upload_status"):
            dpg.set_value("firmware_upload_status", "Fetching firmware from GitHub...")
            dpg.configure_item("firmware_upload_status", color=(255, 255, 0))
        if dpg.does_item_exist("firmware_upload_progress"):
            dpg.configure_item("firmware_upload_progress", show=True)
            dpg.set_value("firmware_upload_progress", 0.0)
        
        self.update_osc_log("Starting firmware upgrade...")
        
        # Run in background thread to not block GUI
        thread = threading.Thread(target=self._upgrade_firmware_thread, daemon=True)
        thread.start()
    
    def _upgrade_firmware_thread(self):
        """Background thread for firmware upgrade via OTA"""
        firmware_file = None
        try:
            # Step 1: Download firmware from GitHub
            self.update_osc_log("Downloading firmware from GitHub...")
            firmware_url = "https://github.com/Hemisphere-Project/MillluBridge/raw/refs/heads/main/Nowde/bin/firmware.bin"
            
            if dpg.does_item_exist("firmware_upload_status"):
                dpg.set_value("firmware_upload_status", "Downloading...")
            
            # Download with timeout
            response = requests.get(firmware_url, timeout=30)
            response.raise_for_status()
            
            firmware_data = response.content
            firmware_size = len(firmware_data)
            self.update_osc_log(f"✅ Downloaded firmware ({firmware_size} bytes)")
            
            if dpg.does_item_exist("firmware_upload_progress"):
                dpg.set_value("firmware_upload_progress", 0.1)
            
            # Step 2: Send OTA_BEGIN
            if dpg.does_item_exist("firmware_upload_status"):
                dpg.set_value("firmware_upload_status", "Starting OTA update...")
            
            self.update_osc_log("Starting OTA update...")
            result = self.output_manager.send_ota_begin(firmware_size)
            
            if not result or not result[0]:
                raise Exception("Failed to send OTA_BEGIN")
            
            time.sleep(0.2)  # Give device time to prepare
            
            if dpg.does_item_exist("firmware_upload_progress"):
                dpg.set_value("firmware_upload_progress", 0.15)
            
            # Step 3: Send firmware data in chunks
            if dpg.does_item_exist("firmware_upload_status"):
                dpg.set_value("firmware_upload_status", "Uploading firmware...")
            
            self.update_osc_log("Uploading firmware data...")
            
            # Use smaller chunks to avoid buffer overflow
            # 100 bytes raw -> ~115 bytes encoded + headers = ~120 bytes total SysEx message
            chunk_size = 100
            sent_bytes = 0
            chunk_count = 0
            
            # Conservative timing to avoid USB buffer overflow
            # ESP32 needs time to decode, write to flash, and process
            chunk_delay = 0.025  # 25ms per chunk
            
            for i in range(0, firmware_size, chunk_size):
                chunk = firmware_data[i:i+chunk_size]
                result = self.output_manager.send_ota_data(chunk)
                
                if not result or not result[0]:
                    raise Exception(f"Failed to send OTA_DATA at offset {i}")
                
                sent_bytes += len(chunk)
                chunk_count += 1
                progress = 0.15 + (sent_bytes / firmware_size) * 0.75  # 15% to 90%
                
                if dpg.does_item_exist("firmware_upload_progress"):
                    dpg.set_value("firmware_upload_progress", progress)
                
                # Log progress every 10%
                percent = (sent_bytes * 100) // firmware_size
                if percent % 10 == 0 and sent_bytes > 0:
                    self.update_osc_log(f"  Progress: {percent}% ({sent_bytes}/{firmware_size} bytes, {chunk_delay*1000:.0f}ms/chunk)")
                
                # Every 100 chunks, give device extra time for flash writes
                if chunk_count % 100 == 0:
                    time.sleep(0.15)  # 150ms pause
                else:
                    time.sleep(chunk_delay)
            
            # Log final byte count
            self.update_osc_log(f"✅ Sent all {sent_bytes} bytes ({chunk_count} chunks)")
            
            # Wait for device to finish writing all buffered data to flash
            self.update_osc_log("Waiting for device to finish writing to flash...")
            time.sleep(2)
            
            if dpg.does_item_exist("firmware_upload_progress"):
                dpg.set_value("firmware_upload_progress", 0.9)
            
            # Step 4: Send OTA_END
            if dpg.does_item_exist("firmware_upload_status"):
                dpg.set_value("firmware_upload_status", "Finalizing update...")
            
            self.update_osc_log("Finalizing firmware update...")
            result = self.output_manager.send_ota_end()
            
            if not result or not result[0]:
                raise Exception("Failed to send OTA_END")
            
            if dpg.does_item_exist("firmware_upload_progress"):
                dpg.set_value("firmware_upload_progress", 0.95)
            
            # Step 5: Device will reboot automatically
            if dpg.does_item_exist("firmware_upload_status"):
                dpg.set_value("firmware_upload_status", "✅ Update complete! Device rebooting...")
                dpg.configure_item("firmware_upload_status", color=(0, 255, 0))
            
            self.update_osc_log("✅ Firmware update successful! Device rebooting...")
            
            # Fully disconnect and close all MIDI connections before reboot
            self.update_osc_log("Closing MIDI connections...")
            
            # Disconnect device (clears state and closes ports)
            if self.current_nowde_device:
                self.disconnect_nowde_device()
            
            # Ensure all MIDI ports are fully closed
            self.output_manager.close_port()
            self.input_manager.close_port()
            
            # Wait longer for device to fully reboot and re-enumerate USB
            # ESP32 needs time to: validate firmware, switch partitions, reboot, and reconnect
            self.update_osc_log("Waiting for device to reboot and re-enumerate USB...")
            time.sleep(8)  # 8 seconds for full reboot cycle
            
            if dpg.does_item_exist("firmware_upload_progress"):
                dpg.set_value("firmware_upload_progress", 1.0)
            
            # Refresh MIDI devices to detect reconnected device
            # This will auto-connect and start listening for HELLO message
            self.update_osc_log("Scanning for reconnected device...")
            self.refresh_midi_devices()
            
            # HELLO message will arrive asynchronously and update version display
            self.update_osc_log("✅ Firmware update complete - waiting for device HELLO...")
            
            # Hide progress bar and status after a delay
            time.sleep(2)
            if dpg.does_item_exist("firmware_upload_progress"):
                dpg.configure_item("firmware_upload_progress", show=False)
            if dpg.does_item_exist("firmware_upload_status"):
                dpg.set_value("firmware_upload_status", "")
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Download failed: {str(e)}"
            self.update_osc_log(f"❌ {error_msg}")
            
            if dpg.does_item_exist("firmware_upload_status"):
                dpg.set_value("firmware_upload_status", "Download failed - check network")
                dpg.configure_item("firmware_upload_status", color=(255, 0, 0))
            
            if dpg.does_item_exist("firmware_upload_progress"):
                dpg.configure_item("firmware_upload_progress", show=False)
            
        except Exception as e:
            error_msg = f"OTA update failed: {str(e)}"
            self.update_osc_log(f"❌ {error_msg}")
            
            if dpg.does_item_exist("firmware_upload_status"):
                dpg.set_value("firmware_upload_status", str(e))
                dpg.configure_item("firmware_upload_status", color=(255, 0, 0))
            
            if dpg.does_item_exist("firmware_upload_progress"):
                dpg.configure_item("firmware_upload_progress", show=False)
            
            # Try to reconnect to MIDI anyway
            time.sleep(1)
            self.refresh_midi_devices()
    
    def on_osc_settings_changed(self, sender, app_data):
        """Callback when OSC settings are changed"""
        try:
            new_port = int(dpg.get_value("osc_port_input"))
        except ValueError:
            self.update_osc_log("ERROR: Invalid port number!")
            return
        
        # Check if port actually changed
        if new_port != self.osc_port:
            self.osc_port = new_port
            self.update_osc_log(f"OSC port changed to {self.osc_port}")
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
        self.update_osc_log(f"Bridge started on port {self.osc_port} (listening on all interfaces)")
        
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
    
    def on_simulation_mode_changed(self, mac, mode):
        """Callback when simulation mode is changed for a Remote Nowde"""
        self.simulation_settings['mac'][mac] = mode
        self.update_osc_log(f"Simulation for {self.remote_nowdes.get(mac, {}).get('uuid', mac)}: {mode}")
        
        # Auto-start/stop simulation clock based on whether any remote needs it
        self._auto_manage_simulation_clock()
    
    def _auto_manage_simulation_clock(self):
        """Automatically start/stop simulation clock based on remote Nowde simulation states"""
        # Check if any remote Nowde has simulation enabled (not "Disabled")
        any_simulation_active = False
        for mac in self.remote_nowdes.keys():
            sim_mode = self.simulation_settings['mac'].get(mac, 'Disabled')
            if sim_mode != 'Disabled':
                any_simulation_active = True
                break
        
        # Start clock if needed and not running
        if any_simulation_active and not self.simulation_clock_running:
            self.update_osc_log("Auto-starting simulation clock (remote simulation enabled)")
            self.toggle_simulation_clock()
        # Stop clock if not needed and running
        elif not any_simulation_active and self.simulation_clock_running:
            self.update_osc_log("Auto-stopping simulation clock (no remote simulations)")
            self.toggle_simulation_clock()
    
    def on_sim_clock_duration_changed(self, sender, app_data):
        """Callback when simulation clock duration is changed"""
        self.simulation_clock_duration = dpg.get_value("sim_clock_duration_slider")
    
    def toggle_simulation_clock(self, *args, **kwargs):
        """Start/stop the simulation clock"""
        if self.simulation_clock_running:
            # Stop clock
            self.stop_simulation_clock = True
            self.simulation_clock_running = False
            if dpg.does_item_exist("sim_clock_btn"):
                dpg.set_value("sim_clock_btn", "Start Clock")
            if dpg.does_item_exist("sim_clock_status"):
                dpg.set_value("sim_clock_status", "Stopped")
                dpg.configure_item("sim_clock_status", color=(150, 150, 150))
        else:
            # Start clock
            self.simulation_clock_position = 0.0
            self.stop_simulation_clock = False
            self.simulation_clock_running = True
            if dpg.does_item_exist("sim_clock_btn"):
                dpg.set_value("sim_clock_btn", "Stop Clock")
            if dpg.does_item_exist("sim_clock_status"):
                dpg.set_value("sim_clock_status", "Running")
                dpg.configure_item("sim_clock_status", color=(0, 255, 0))
            
            # Start clock thread
            if self.simulation_clock_thread is None or not self.simulation_clock_thread.is_alive():
                self.simulation_clock_thread = threading.Thread(target=self.simulation_clock_loop, daemon=True)
                self.simulation_clock_thread.start()
    
    def simulation_clock_loop(self):
        """Background thread for simulation clock"""
        import time
        
        last_time = time.time()
        
        while self.simulation_clock_running and not self.stop_simulation_clock:
            current_time = time.time()
            delta = current_time - last_time
            last_time = current_time
            
            # Update clock position
            self.simulation_clock_position += delta
            
            # Loop back to 0 when reaching duration
            if self.simulation_clock_position >= self.simulation_clock_duration:
                self.simulation_clock_position = 0.0
            
            # Update GUI
            if dpg.does_item_exist("sim_clock_position_text"):
                dpg.set_value("sim_clock_position_text", 
                            f"{self.simulation_clock_position:.1f}s / {self.simulation_clock_duration:.1f}s")
            
            # Send sync messages to all Remote Nowdes in simulation mode
            if self.current_nowde_device and self.output_manager.current_port:
                position_ms = int(self.simulation_clock_position * 1000)
                
                for mac, nowde in self.remote_nowdes.items():
                    # Skip disconnected/missing devices
                    if nowde.get('last_seen_ms', 99999) > 10000:
                        continue
                    
                    sim_mode = self.simulation_settings['mac'].get(mac, 'Disabled')
                    
                    if sim_mode == 'Disabled':
                        continue
                    
                    layer_name = nowde.get('layer', '')
                    if not layer_name:
                        continue
                    
                    # Determine media index and state
                    if sim_mode == 'Stop':
                        media_index = 0
                        state = 'stopped'
                    else:
                        # sim_mode is '1' through '10'
                        try:
                            media_index = int(sim_mode)
                            state = 'playing'
                        except ValueError:
                            continue
                    
                    # Send media sync (simulation takes priority over real OSC for this layer)
                    self.output_manager.send_media_sync(
                        layer_name=layer_name,
                        media_index=media_index,
                        position_ms=position_ms,
                        state=state
                    )
            
            # Sleep for throttle interval
            time.sleep(self.sync_settings['throttle_interval'])
    
    def on_dali_status_changed(self, connected: bool, device_path: str):
        """Callback when DALI connection status changes"""
        self.update_dali_status(connected, device_path)
        if connected:
            self.update_osc_log(f"DALI Master connected: {device_path if device_path else 'Unknown'}")
        else:
            self.update_osc_log("DALI Master disconnected")
    
    def update_dali_status(self, connected: bool, device_path: str = ''):
        """Update the DALI status indicator in GUI"""
        if dpg.does_item_exist("dali_status_indicator"):
            if connected:
                dpg.set_value("dali_status_indicator", "[OK]")
                dpg.configure_item("dali_status_indicator", color=(0, 255, 0))
            else:
                dpg.set_value("dali_status_indicator", "[X]")
                dpg.configure_item("dali_status_indicator", color=(255, 0, 0))
        
        if dpg.does_item_exist("dali_status_text"):
            if connected:
                if device_path:
                    # Show just the device name, not full path
                    device_name = device_path.split('/')[-1] if '/' in device_path else device_path
                    print(f"DALI device name: {device_path} -> {device_name}")
                    # dpg.set_value("dali_status_text", device_name)
                    dpg.set_value("dali_status_text", "Hasseb DALI")
                else:
                    dpg.set_value("dali_status_text", "Connected")
                dpg.configure_item("dali_status_text", color=(0, 255, 0))
            else:
                dpg.set_value("dali_status_text", "Not connected")
                dpg.configure_item("dali_status_text", color=(150, 150, 150))
    
    def dali_all_on(self):
        """Broadcast All On command to all DALI lights"""
        if self.dali_manager and self.dali_manager.is_connected:
            # Update internal values and UI
            with self.lights_lock:
                for channel in list(self.lights.keys()):
                    self.lights[channel] = 255
            
            self.dali_manager.broadcast_on()
            self.update_osc_log("DALI: All On (broadcast)")
            self.update_lights_table()
        else:
            self.update_osc_log("DALI: Device not connected")
    
    def dali_blackout(self):
        """Broadcast Blackout (Off) command to all DALI lights"""
        if self.dali_manager and self.dali_manager.is_connected:
            # Update internal values and UI
            with self.lights_lock:
                for channel in list(self.lights.keys()):
                    self.lights[channel] = 0
            
            self.dali_manager.broadcast_off()
            self.update_osc_log("DALI: Blackout (broadcast)")
            self.update_lights_table()
        else:
            self.update_osc_log("DALI: Device not connected")
    
    def on_quit(self):
        """Callback for Quit button"""
        self.stop_midi_refresh = True
        self.stop_media_sync = True
        self.stop_simulation_clock = True
        self.stop_dali_scan = True
        self.simulation_clock_running = False
        if self.dali_manager:
            self.dali_manager.stop_monitoring_thread()
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
        self.stop_simulation_clock = True
        self.stop_dali_scan = True
        self.simulation_clock_running = False
        if self.dali_manager:
            self.dali_manager.stop_monitoring_thread()
        if self.is_running:
            self.stop_bridge()
        
        dpg.destroy_context()

if __name__ == '__main__':
    app = MilluBridge()
    app.run()