from pythonosc import dispatcher
from pythonosc import osc_server
import threading


class OSCServer:
    def __init__(self, callback, address="127.0.0.1", port=8000):
        self.address = address
        self.port = port
        self.server = None
        self.callback = callback
        self.thread = None

    def start(self):
        disp = dispatcher.Dispatcher()
        disp.set_default_handler(self.handle_message)
        
        self.server = osc_server.BlockingOSCUDPServer((self.address, self.port), disp)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"OSC Server started on {self.address}:{self.port}")

    def handle_message(self, address, *args):
        message = f"{address}: {args}"
        if self.callback:
            self.callback(message)

    def stop(self):
        if self.server:
            self.server.shutdown()
            print("OSC Server stopped")