# MilluBridge - GUI Main Window
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

class MainWindow:
    def __init__(self, window_title="MilluBridge"):
        
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