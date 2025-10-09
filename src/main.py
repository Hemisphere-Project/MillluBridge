import dearpygui.dearpygui as dpg
from osc.server import OSCServer
from midi.output_manager import OutputManager
from midi.message_sender import send_midi_message
import time
import threading

class MilluBridge:
    def __init__(self, osc_address="127.0.0.1", osc_port=8000):
        self.osc_address = osc_address
        self.osc_port = osc_port
        self.osc_server = None
        self.output_manager = OutputManager()
        self.selected_port = None
        self.is_running = False
        self.last_osc_time = 0
        self.status_check_thread = None
        
        # Millumin layer tracking
        self.layers = {}  # {layer_name: {state, filename, position, duration}}
        self.layer_rows = {}  # {layer_name: row_tag} - track row tags for updates
        self.show_all_messages = False
        
        # Create DearPyGUI context
        dpg.create_context()
        
        # Setup window
        self.setup_gui()
        
        # Auto-start bridge
        self.start_bridge()

    def setup_gui(self):
        """Setup the DearPyGUI interface"""
        with dpg.window(label="MilluBridge - OSC to MIDI Bridge", tag="primary_window", 
                       width=900, height=700, no_close=True):
            
            # OSC Settings section
            dpg.add_text("OSC Settings", color=(150, 200, 255))
            with dpg.group(horizontal=True):
                dpg.add_text("Address:")
                dpg.add_input_text(tag="osc_address_input", default_value=self.osc_address, 
                                 width=150, on_enter=True, callback=self.on_osc_settings_changed)
                dpg.add_text("Port:")
                dpg.add_input_text(tag="osc_port_input", default_value=str(self.osc_port), 
                                 width=100, on_enter=True, callback=self.on_osc_settings_changed)
            
            # OSC Status indicator
            with dpg.group(horizontal=True):
                dpg.add_text("OSC Status:", tag="status_label")
                dpg.add_text("●", tag="status_indicator", color=(255, 0, 0))  # Red by default
                dpg.add_text("", tag="status_text", color=(150, 150, 150))
            
            dpg.add_separator()
            
            # Millumin Layers section
            dpg.add_text("Millumin Layers", color=(150, 200, 255))
            with dpg.table(header_row=True, tag="layers_table", 
                          borders_innerH=True, borders_outerH=True, 
                          borders_innerV=True, borders_outerV=True,
                          row_background=True, resizable=True):
                dpg.add_table_column(label="Layer", width_fixed=True, init_width_or_weight=150)
                dpg.add_table_column(label="State", width_fixed=True, init_width_or_weight=60)
                dpg.add_table_column(label="Filename", width_stretch=True)
                dpg.add_table_column(label="Position", width_fixed=True, init_width_or_weight=80)
                dpg.add_table_column(label="Duration", width_fixed=True, init_width_or_weight=80)
            
            dpg.add_separator()
            
            # OSC Message log with filter toggle
            dpg.add_text("OSC Logs", color=(150, 200, 255))
            with dpg.group(horizontal=True):
                dpg.add_checkbox(label="Show All Messages", tag="show_all_toggle", 
                               callback=self.on_toggle_filter, default_value=False)
            
            # Use child window for auto-scrolling log
            with dpg.child_window(tag="osc_log_window", width=-1, height=150, border=True):
                dpg.add_text("Waiting for OSC messages...", tag="osc_log_text", wrap=850)
            
            dpg.add_separator()
            
            # MIDI Port selection
            dpg.add_text("MIDI Settings", color=(150, 200, 255))
            ports = self.output_manager.get_ports()
            dpg.add_combo(ports, tag="midi_port_combo", default_value=ports[0] if ports else "No ports",
                         width=-1, callback=self.on_midi_port_changed, label="Output Port")
            
            dpg.add_separator()
            
            # Control buttons
            with dpg.group(horizontal=True):
                dpg.add_button(label="Quit", callback=self.on_quit, width=150)

    def handle_osc_message(self, message):
        self.last_osc_time = time.time()
        self.update_osc_status(True)
        
        # Parse Millumin messages
        is_millumin = self.parse_millumin_message(message)
        
        # Log message (filtered or all)
        if self.show_all_messages or is_millumin:
            self.update_osc_log(message)
        
        if self.selected_port and self.is_running:
            midi_message = self.map_osc_to_midi(message)
            send_midi_message(self.output_manager.midi_out, midi_message)
    
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
                color = (0, 255, 0) if state == "playing" else (150, 150, 150)
                
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

    def update_osc_status(self, active):
        """Update the OSC status indicator"""
        if dpg.does_item_exist("status_indicator"):
            color = (0, 255, 0) if active else (255, 0, 0)  # Green if active, red otherwise
            dpg.configure_item("status_indicator", color=color)
        if dpg.does_item_exist("status_text"):
            if active:
                text = f"Receiving - {self.osc_address}:{self.osc_port}"
                color = (0, 255, 0)
            else:
                if self.is_running:
                    text = f"Listening on {self.osc_address}:{self.osc_port}"
                    color = (150, 150, 150)
                else:
                    text = "Stopped"
                    color = (150, 150, 150)
            dpg.set_value("status_text", text)
            dpg.configure_item("status_text", color=color)

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
    
    def on_midi_port_changed(self, sender, app_data):
        """Callback when MIDI port is changed"""
        port_name = dpg.get_value("midi_port_combo")
        if port_name and port_name != "No ports":
            # Restart bridge with new MIDI port
            self.selected_port = port_name
            self.restart_bridge()
    
    def start_bridge(self):
        """Start the OSC-MIDI bridge"""
        # Initialize OSC server
        if self.osc_server:
            self.osc_server.stop()
        
        self.osc_server = OSCServer(self.handle_osc_message, address=self.osc_address, port=self.osc_port)
        
        # Open MIDI port
        port_name = dpg.get_value("midi_port_combo") if dpg.does_item_exist("midi_port_combo") else None
        if port_name and port_name != "No ports":
            self.selected_port = port_name
            if self.output_manager.open_port(port_name):
                self.is_running = True
                self.osc_server.start()
                self.last_osc_time = time.time()
                self.update_osc_log(f"Bridge started on {self.osc_address}:{self.osc_port} -> {port_name}")
                self.update_osc_status(True)
                
                # Start status check thread
                if self.status_check_thread is None or not self.status_check_thread.is_alive():
                    self.status_check_thread = threading.Thread(target=self.check_osc_status, daemon=True)
                    self.status_check_thread.start()
        else:
            # Start OSC server even without MIDI port
            self.is_running = True
            self.osc_server.start()
            self.last_osc_time = time.time()
            self.update_osc_log(f"OSC server started on {self.osc_address}:{self.osc_port} (no MIDI port selected)")
            self.update_osc_status(True)
            
            if self.status_check_thread is None or not self.status_check_thread.is_alive():
                self.status_check_thread = threading.Thread(target=self.check_osc_status, daemon=True)
                self.status_check_thread.start()
    
    def stop_bridge(self):
        """Stop the OSC-MIDI bridge"""
        self.is_running = False
        if self.osc_server:
            self.osc_server.stop()
        self.output_manager.close_port()
        self.update_osc_status(False)
        self.update_osc_log("Bridge stopped!")
    
    def restart_bridge(self):
        """Restart the bridge with new settings"""
        self.stop_bridge()
        time.sleep(0.1)  # Small delay to ensure clean shutdown
        self.start_bridge()
    
    def on_quit(self):
        """Callback for Quit button"""
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
        return [0x90, 60, 100]
    
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
        if self.is_running:
            self.stop_bridge()
        
        dpg.destroy_context()

if __name__ == '__main__':
    app = MilluBridge()
    app.run()