class MainWindow:
    def __init__(self, window_title="MilluBridge"):
        import PySimpleGUI as sg
        
        self.layout = [
            [sg.Text("OSC Status:"), sg.Text("", key="-OSC_STATUS-", size=(10, 1), text_color='red')],
            [sg.Multiline("", key="-OSC_LOG-", size=(50, 10), disabled=True, autoscroll=True)],
            [sg.Text("Select MIDI Output:"), sg.Combo([], key="-MIDI_OUTPUT-")],
            [sg.Button("Start Bridge"), sg.Button("Stop Bridge"), sg.Button("Quit")]
        ]
        
        self.window = sg.Window(window_title, self.layout, finalize=True)
        self.update_midi_ports()

    def update_midi_ports(self, ports=[]):
        self.window["-MIDI_OUTPUT-"].update(values=ports)

    def update_osc_status(self, status):
        color = 'green' if status else 'red'
        self.window["-OSC_STATUS-"].update(text_color=color)

    def log_osc_message(self, message):
        current_log = self.window["-OSC_LOG-"].get()
        self.window["-OSC_LOG-"].update(current_log + message + "\n")

    def close(self):
        self.window.close()

    def read(self):
        return self.window.read()