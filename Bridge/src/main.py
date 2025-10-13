import dearpygui.dearpygui as dpg
from osc.server import OSCServer
from midi.output_manager import OutputManager
from midi.input_manager import InputManager
from midi.message_sender import send_midi_message
import time
import threading

class MilluBridge:
    def __init__(self, osc_address="127.0.0.1", osc_port=8000):
        self.osc_address = osc_address
        self.osc_port = osc_port
        self.osc_server = None
        self.output_manager = OutputManager()
        self.input_manager = InputManager(
            callback=self.handle_midi_input,
            sysex_callback=self.handle_sysex_message
        )
        self.selected_port = None
        self.is_running = False
        self.last_osc_time = 0
        self.status_check_thread = None
        self.midi_refresh_thread = None
        self.stop_midi_refresh = False
        self.current_nowde_device = None
        
        # Millumin layer tracking
        self.layers = {}  # {layer_name: {state, filename, position, duration}}
        self.layer_rows = {}  # {layer_name: row_tag} - track row tags for updates
        self.show_all_messages = False
        
        # Remote Nowdes tracking
        self.remote_nowdes = {}  # {mac: {name, version, layer}}
        
        # Layer editing modal state
        self.editing_layer_mac = None  # Track which device is being edited
        
        # Create DearPyGUI context
        dpg.create_context()
        
        # Setup window
        self.setup_gui()
        
        # Start MIDI device refresh thread
        self.start_midi_refresh_thread()
        
        # Auto-start bridge
        self.start_bridge()

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
                dpg.add_table_column(label="UUID", width_fixed=True, init_width_or_weight=100)
                dpg.add_table_column(label="Version", width_fixed=True, init_width_or_weight=80)
                dpg.add_table_column(label="State", width_fixed=True, init_width_or_weight=80)
                dpg.add_table_column(label="Layer", width_stretch=True)

    def handle_midi_input(self, message, deltatime):
        """Handle incoming MIDI messages from the device (for logging/debug only)"""
        # Log the incoming MIDI message
        self.log_midi_message(message, is_input=True)
    
    def handle_sysex_message(self, msg_type, data):
        """Handle parsed SysEx messages from Nowde"""
        if msg_type == 'receiver_table':
            # Update remote Nowdes table
            for nowde in data:
                self.remote_nowdes[nowde['mac']] = nowde
            
            # Update GUI
            self.update_remote_nowdes_table()
            
            # Log to OSC log
            self.update_osc_log(f"Remote Nowdes updated: {len(data)} device(s)")
        
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
        
        # Clear existing rows (except header)
        children = dpg.get_item_children("remote_nowdes_table", slot=1)
        if children:
            for child in children:
                dpg.delete_item(child)
        
        # Add rows for each remote Nowde, sorted by UUID
        for mac, nowde in sorted(self.remote_nowdes.items(), key=lambda x: x[1].get('uuid', '')):
            # Determine colors based on connection status
            connected = nowde.get('connected', True)
            
            if connected:
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
            
            with dpg.table_row(parent="remote_nowdes_table"):
                dpg.add_text(nowde['uuid'], color=uuid_color)
                dpg.add_text(nowde['version'], color=version_color)
                dpg.add_text(state_text, color=state_color)
                
                # Clickable button to edit layer
                layer_btn_tag = f"layer_btn_{mac}"
                dpg.add_button(
                    tag=layer_btn_tag,
                    label=nowde['layer'],
                    width=150,  # Limit width to ~16 chars
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
        
        # OSC to MIDI: Send MIDI output based on OSC message
        if self.selected_port and self.is_running:
            midi_message = self.map_osc_to_midi(message)
            if midi_message:
                send_midi_message(self.output_manager.midi_out, midi_message)
                # Log the outgoing MIDI message
                self.log_midi_message(midi_message, is_input=False)
    
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
                layer["filename"] = str(args[1]) if len(args) > 1 else ""
                layer["duration"] = float(args[2]) if len(args) > 2 else 0.0
                layer["state"] = "stopped"
            
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
    
    def on_subscribe_layer(self):
        """Handle Subscribe to Layer button click"""
        if not self.current_nowde_device:
            self.update_osc_log("Error: No Nowde connected")
            return
        
        layer_name = dpg.get_value("subscribe_layer_input")
        if not layer_name or not layer_name.strip():
            self.update_osc_log("Error: Please enter a layer name")
            return
        
        # Send Subscribe to Layer SysEx
        result = self.output_manager.send_subscribe_layer(layer_name.strip())
        if result and result[0]:
            success, formatted_msg = result
            self.update_osc_log(f"Sent Subscribe to Layer: {layer_name.strip()}")
            self.log_nowde_message(f"TX: {formatted_msg}")
        else:
            self.update_osc_log("Error: Failed to send Subscribe command")
    
    def log_midi_message(self, midi_message, is_input=False):
        """Log MIDI message in a human-readable format"""
        if dpg.does_item_exist("midi_log_text"):
            current_log = dpg.get_value("midi_log_text")
            
            # Clear initial message on first real message
            if current_log.strip() == "Waiting for MIDI messages...":
                current_log = ""
            
            # Format MIDI message in human-readable form
            direction = "IN " if is_input else "OUT"
            formatted_msg = self.format_midi_message(midi_message)
            timestamp = time.strftime("%H:%M:%S")
            new_log = current_log + f"[{timestamp}] {direction}: {formatted_msg}\n"
            
            # Keep only last 1000 lines
            lines = new_log.split('\n')
            if len(lines) > 1000:
                new_log = '\n'.join(lines[-1000:])
            
            dpg.set_value("midi_log_text", new_log)
            
            # Auto-scroll to bottom
            if dpg.does_item_exist("midi_log_window"):
                dpg.set_y_scroll("midi_log_window", dpg.get_y_scroll_max("midi_log_window"))
    
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
    
    def format_midi_message(self, midi_message):
        """Format MIDI message bytes into human-readable string"""
        if not midi_message or len(midi_message) == 0:
            return "Empty message"
        
        status_byte = midi_message[0]
        channel = (status_byte & 0x0F) + 1  # MIDI channels are 1-16
        msg_type = status_byte & 0xF0
        
        # Note On (0x90)
        if msg_type == 0x90 and len(midi_message) >= 3:
            note = midi_message[1]
            velocity = midi_message[2]
            note_name = self.midi_note_to_name(note)
            if velocity == 0:
                return f"Note Off: {note_name} (Ch {channel}) - Raw: {list(midi_message)}"
            return f"Note On: {note_name}, Vel={velocity} (Ch {channel}) - Raw: {list(midi_message)}"
        
        # Note Off (0x80)
        elif msg_type == 0x80 and len(midi_message) >= 3:
            note = midi_message[1]
            velocity = midi_message[2]
            note_name = self.midi_note_to_name(note)
            return f"Note Off: {note_name}, Vel={velocity} (Ch {channel}) - Raw: {list(midi_message)}"
        
        # Control Change (0xB0)
        elif msg_type == 0xB0 and len(midi_message) >= 3:
            cc_num = midi_message[1]
            value = midi_message[2]
            return f"CC: {cc_num}, Value={value} (Ch {channel}) - Raw: {list(midi_message)}"
        
        # Program Change (0xC0)
        elif msg_type == 0xC0 and len(midi_message) >= 2:
            program = midi_message[1]
            return f"Program Change: {program} (Ch {channel}) - Raw: {list(midi_message)}"
        
        # Pitch Bend (0xE0)
        elif msg_type == 0xE0 and len(midi_message) >= 3:
            lsb = midi_message[1]
            msb = midi_message[2]
            value = (msb << 7) | lsb
            return f"Pitch Bend: {value} (Ch {channel}) - Raw: {list(midi_message)}"
        
        # Unknown or other message types
        else:
            return f"Raw MIDI: {list(midi_message)}"
    
    def midi_note_to_name(self, note_number):
        """Convert MIDI note number to note name (e.g., 60 -> C4)"""
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (note_number // 12) - 1
        note = note_names[note_number % 12]
        return f"{note}{octave} ({note_number})"
    
    def refresh_midi_devices(self):
        """Find and connect to first Nowde device"""
        # Get all available ports (union of input and output)
        out_ports = set(self.output_manager.get_ports())
        in_ports = set(self.input_manager.get_ports())
        all_ports = sorted(list(out_ports | in_ports))
        
        # Find first device starting with "Nowde"
        nowde_device = None
        for port in all_ports:
            if port.startswith("Nowde"):
                nowde_device = port
                break
        
        # If we found a Nowde device and it's different from current, connect to it
        if nowde_device and nowde_device != self.current_nowde_device:
            self.connect_nowde_device(nowde_device)
        elif not nowde_device and self.current_nowde_device:
            # Nowde was disconnected
            self.disconnect_nowde_device()
    
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
            
            # Send Bridge Connected SysEx to activate sender mode
            if out_success:
                result = self.output_manager.send_bridge_connected()
                if result and result[0]:
                    success, formatted_msg = result
                    self.log_nowde_message(f"TX: {formatted_msg}")
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
    
    def auto_refresh_midi_devices(self):
        """Background thread to periodically check for Nowde devices"""
        last_ports = set()
        
        while not self.stop_midi_refresh:
            time.sleep(2)  # Check every 2 seconds
            
            # Get all available ports (union of input and output)
            out_ports = set(self.output_manager.get_ports())
            in_ports = set(self.input_manager.get_ports())
            current_ports = out_ports | in_ports
            
            # Only update if ports changed
            if current_ports != last_ports:
                self.refresh_midi_devices()
                last_ports = current_ports

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
        if self.is_running:
            self.stop_bridge()
        dpg.stop_dearpygui()

    def map_osc_to_midi(self, message):
        """
        Placeholder for OSC-to-MIDI mapping logic
        Parse OSC message and convert to MIDI format
        Example: converts OSC message to MIDI Note On message
        """
        # Default MIDI message: Note On, Middle C, Velocity 100
        # return [0x90, 60, 100]
        return None  # No mapping by default
    
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
        if self.is_running:
            self.stop_bridge()
        
        dpg.destroy_context()

if __name__ == '__main__':
    app = MilluBridge()
    app.run()