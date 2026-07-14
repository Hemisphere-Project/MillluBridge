import dearpygui.dearpygui as dpg
import hid
from dali.driver.hasseb import SyncHassebDALIUSBDriver
from dali.gear.general import (
    DAPC, Off, RecallMaxLevel, QueryControlGearPresent, 
    QueryActualLevel, QueryStatus, QueryDeviceType
)
from dali.address import Broadcast, GearShort

# Constants for Hasseb
HASSEB_USB_VENDOR = 0x04cc
HASSEB_USB_PRODUCT = 0x0802

driver = None
discovered_devices = []  # List of discovered DALI addresses

def log(message):
    # Append to log
    current = dpg.get_value("log_text")
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    new_log = f"[{timestamp}] {message}\n{current}"
    # Limit log size
    if len(new_log) > 10000:
        new_log = new_log[:10000]
    dpg.set_value("log_text", new_log)

def init_driver(sender, app_data):
    global driver
    try:
        devices = hid.enumerate(HASSEB_USB_VENDOR, HASSEB_USB_PRODUCT)
        if not devices:
            log("No Hasseb device found via HID enumeration.")
            return
        
        # Pick first device
        device_info = devices[0]
        path = device_info['path']
        log(f"Found device at path: {path}")
        
        # Path must be bytes for hidapi
        if isinstance(path, str):
            path = path.encode()
        
        driver = SyncHassebDALIUSBDriver(path=path)
        
        if not driver.device_found:
            log("Failed to open device - check permissions")
            dpg.configure_item("status_text", default_value="Status: Error", color=(255, 0, 0))
            return
            
        log(f"Driver initialized. Firmware: {driver.readFirmwareVersion()}")
        dpg.configure_item("status_text", default_value="Status: Connected", color=(0, 255, 0))
    except Exception as e:
        log(f"Failed to initialize driver: {e}")
        dpg.configure_item("status_text", default_value="Status: Error", color=(255, 0, 0))

def send_level(sender, app_data):
    if driver is None:
        log("Driver not connected.")
        return
    
    level = dpg.get_value("level_slider")
    try:
        cmd = DAPC(Broadcast(), int(level))
        driver.send(cmd)
        log(f"Sent DAPC {int(level)} to Broadcast")
    except Exception as e:
        log(f"Error sending command: {e}")

def send_off(sender, app_data):
    if driver is None:
        log("Driver not connected.")
        return
    try:
        cmd = Off(Broadcast())
        driver.send(cmd)
        log("Sent OFF to Broadcast")
    except Exception as e:
        log(f"Error sending command: {e}")

def send_on(sender, app_data):
    if driver is None:
        log("Driver not connected.")
        return
    try:
        cmd = RecallMaxLevel(Broadcast())
        driver.send(cmd)
        log("Sent RecallMaxLevel (ON) to Broadcast")
    except Exception as e:
        log(f"Error sending command: {e}")

def scan_devices(sender, app_data):
    """Scan DALI bus for control gear (addresses 0-63)"""
    global discovered_devices
    if driver is None:
        log("Driver not connected.")
        return
    
    log("Scanning DALI bus for devices (0-63)...")
    discovered_devices = []
    
    for addr in range(64):
        try:
            cmd = QueryControlGearPresent(GearShort(addr))
            response = driver.send(cmd)
            # Debug: show raw response for first few addresses
            if addr < 5:
                log(f"  Addr {addr}: response={response}, type={type(response)}")
            if response is not None:
                # Check various response formats
                if hasattr(response, 'value') and response.value:
                    discovered_devices.append(addr)
                    log(f"  Found device at address {addr}")
                elif hasattr(response, 'raw_value') and response.raw_value is not None:
                    discovered_devices.append(addr)
                    log(f"  Found device at address {addr} (raw)")
        except Exception as e:
            if addr < 5:
                log(f"  Addr {addr}: error={e}")
    
    log(f"Scan complete. Found {len(discovered_devices)} device(s).")
    
    if not discovered_devices:
        log("TIP: Make sure DALI gateway is addressed via 4remote BT app first!")
        log("TIP: Try broadcast ON/OFF to see if devices respond.")
    
    update_device_list()

def update_device_list():
    """Update the device list in the GUI"""
    # Clear existing items
    if dpg.does_item_exist("device_list"):
        dpg.delete_item("device_list", children_only=True)
    
    if not discovered_devices:
        dpg.add_text("No devices found. Click 'Scan'.", parent="device_list")
        return
    
    for addr in discovered_devices:
        with dpg.group(horizontal=True, parent="device_list"):
            dpg.add_text(f"Addr {addr:02d}")
            dpg.add_button(label="ON", width=50, user_data=addr, callback=lambda s, a, u: device_on(u))
            dpg.add_button(label="OFF", width=50, user_data=addr, callback=lambda s, a, u: device_off(u))
            dpg.add_slider_int(
                label="", default_value=128, max_value=254, width=150,
                tag=f"slider_{addr}",
                user_data=addr,
                callback=lambda s, a, u: device_level(u, a)
            )
            dpg.add_button(label="Query", width=50, user_data=addr, callback=lambda s, a, u: query_device(u))

def device_on(addr):
    """Turn on a specific device"""
    if driver is None:
        return
    try:
        cmd = RecallMaxLevel(GearShort(addr))
        driver.send(cmd)
        log(f"Addr {addr}: ON")
    except Exception as e:
        log(f"Addr {addr}: Error - {e}")

def device_off(addr):
    """Turn off a specific device"""
    if driver is None:
        return
    try:
        cmd = Off(GearShort(addr))
        driver.send(cmd)
        log(f"Addr {addr}: OFF")
    except Exception as e:
        log(f"Addr {addr}: Error - {e}")

def device_level(addr, level):
    """Set level for a specific device"""
    if driver is None:
        return
    try:
        cmd = DAPC(GearShort(addr), int(level))
        driver.send(cmd)
        log(f"Addr {addr}: Level {level}")
    except Exception as e:
        log(f"Addr {addr}: Error - {e}")

def query_device(addr):
    """Query device status and level"""
    if driver is None:
        return
    try:
        # Query actual level
        cmd = QueryActualLevel(GearShort(addr))
        response = driver.send(cmd)
        level = response.value if response and hasattr(response, 'value') else "N/A"
        
        # Query status
        cmd2 = QueryStatus(GearShort(addr))
        response2 = driver.send(cmd2)
        status = response2.raw_value if response2 and hasattr(response2, 'raw_value') else "N/A"
        
        log(f"Addr {addr}: Level={level}, Status=0x{status:02X}" if isinstance(status, int) else f"Addr {addr}: Level={level}, Status={status}")
        
        # Update slider if we got a valid level
        if isinstance(level, int) and dpg.does_item_exist(f"slider_{addr}"):
            dpg.set_value(f"slider_{addr}", level)
    except Exception as e:
        log(f"Addr {addr}: Query error - {e}")

def create_gui():
    dpg.create_context()
    dpg.create_viewport(title='Hasseb DALI Controller', width=700, height=700)

    with dpg.window(label="Main Window", width=700, height=700, no_close=True):
        dpg.add_text("Hasseb DALI Master Control", color=(0, 200, 255))
        dpg.add_text("Status: Disconnected", tag="status_text", color=(255, 100, 0))
        
        dpg.add_button(label="Initialize Driver", callback=init_driver, width=200, height=30)
        
        dpg.add_separator()
        dpg.add_text("Broadcast Control")
        
        with dpg.group(horizontal=True):
            dpg.add_button(label="OFF", callback=send_off, width=80)
            dpg.add_button(label="ON", callback=send_on, width=80)
        
        dpg.add_slider_int(label="Level (0-254)", tag="level_slider", default_value=128, max_value=254, width=400)
        dpg.add_button(label="Set Level", callback=send_level, width=200)
        
        dpg.add_separator()
        dpg.add_text("Device Discovery & Control", color=(0, 200, 255))
        dpg.add_button(label="Scan DALI Bus", callback=scan_devices, width=200, height=30)
        
        with dpg.child_window(tag="device_list", height=200, border=True):
            dpg.add_text("Click 'Scan DALI Bus' to discover devices.")
        
        dpg.add_separator()
        dpg.add_text("Log")
        dpg.add_input_text(tag="log_text", multiline=True, readonly=True, height=150, width=680)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == "__main__":
    create_gui()
