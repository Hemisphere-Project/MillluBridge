import rtmidi


class OutputManager:
    def __init__(self):
        self.midi_out = rtmidi.MidiOut()
        self.current_port = None

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