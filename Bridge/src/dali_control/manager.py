# MilluBridge - DALI Manager
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

import threading
import time
from typing import Optional, Callable
import hid

try:
    from dali.driver.hasseb import SyncHassebDALIUSBDriver
    from dali.address import Broadcast, GearShort
    from dali.gear.general import DAPC, Off, RecallMaxLevel, QueryControlGearPresent, QueryActualLevel
    DALI_AVAILABLE = True
except ImportError:
    DALI_AVAILABLE = False
    print("Warning: python-dali not installed. DALI functionality will be disabled.")


class DaliManager:
    """Manages connection to Hasseb DALI Master USB device"""
    
    def __init__(self, status_callback: Optional[Callable] = None):
        """
        Initialize DALI Manager
        
        Args:
            status_callback: Optional callback function(connected: bool, device_path: str) 
                           called when connection status changes
        """
        self.driver: Optional[SyncHassebDALIUSBDriver] = None
        self.device_path: Optional[str] = None
        self.is_connected = False
        self.status_callback = status_callback
        self.stop_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.driver_lock = threading.Lock()  # Protect DALI bus access
        
        if not DALI_AVAILABLE:
            print("DALI support not available - python-dali library not installed")
            return
        
        # Start device monitoring thread
        self.start_monitoring()
    
    def find_hasseb_device(self) -> Optional[str]:
        """
        Find Hasseb DALI Master USB device via HID
        
        Returns:
            Device path if found, None otherwise
        """
        if not DALI_AVAILABLE:
            return None
        
        # Hasseb DALI Master USB identifiers
        HASSEB_VENDOR_ID = 0x04CC  # Philips Semiconductors
        HASSEB_PRODUCT_ID = 0x0802
        
        try:
            devices = hid.enumerate()
            hasseb_devices = [d for d in devices 
                            if d['vendor_id'] == HASSEB_VENDOR_ID 
                            and d['product_id'] == HASSEB_PRODUCT_ID]
            
            if hasseb_devices:
                device = hasseb_devices[0]
                device_path = device['path'].decode('utf-8') if isinstance(device['path'], bytes) else device['path']
                return device_path
            else:
                return None
                
        except Exception as e:
            print(f"[DALI] Error enumerating HID devices: {e}")
            return None
    
    def connect(self, device_path: Optional[str] = None) -> bool:
        """
        Connect to Hasseb DALI Master
        
        Args:
            device_path: Optional specific device path. If None, will auto-detect.
        
        Returns:
            True if connected successfully, False otherwise
        """
        if not DALI_AVAILABLE:
            return False
        
        # Close existing connection
        if self.driver:
            self.disconnect()
        
        # Find device if not specified
        if device_path is None:
            device_path = self.find_hasseb_device()
            if device_path is None:
                return False
        
        try:
            # SyncHassebDALIUSBDriver needs path as bytes
            path = device_path
            if isinstance(path, str):
                path = path.encode()
            
            self.driver = SyncHassebDALIUSBDriver(path=path)
            
            if not self.driver.device_found:
                print("[DALI] Failed to open device - check permissions")
                self.driver = None
                self.device_path = None
                self.is_connected = False
                return False
            
            self.device_path = device_path
            self.is_connected = True
            print(f"[DALI] Connected to Hasseb DALI Master")
            
            if self.status_callback:
                self.status_callback(True, device_path)
            
            return True
            
        except Exception as e:
            print(f"[DALI] Failed to connect: {e}")
            self.driver = None
            self.device_path = None
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Disconnect from DALI device"""
        if self.driver:
            try:
                self.driver.disconnect()
            except Exception as e:
                print(f"Error disconnecting DALI device: {e}")
            finally:
                self.driver = None
                self.device_path = None
                self.is_connected = False
                
                if self.status_callback:
                    self.status_callback(False, None)
    
    def set_level(self, address: int, level: int) -> bool:
        """
        Set DALI light level
        
        Args:
            address: DALI short address (0-63)
            level: Light level (0-255)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected or not self.driver:
            return False
        
        if not (0 <= address <= 63):
            print(f"Invalid DALI address: {address} (must be 0-63)")
            return False
        
        if not (0 <= level <= 254):
            level = min(254, max(0, level))
        
        try:
            with self.driver_lock:
                # Create DALI command: Direct Arc Power Control (DAPC)
                cmd = DAPC(GearShort(address), level)
                self.driver.send(cmd)
            return True
            
        except Exception as e:
            print(f"[DALI] Error setting level: {e}")
            # Connection might be lost
            self.is_connected = False
            if self.status_callback:
                self.status_callback(False, self.device_path)
            return False
    
    def broadcast_on(self) -> bool:
        """Set all DALI lights to full brightness using broadcast"""
        if not self.is_connected or not self.driver:
            print("[DALI] Device not connected")
            return False
        
        try:
            with self.driver_lock:
                # Send broadcast command: RecallMaxLevel (ON)
                cmd = RecallMaxLevel(Broadcast())
                self.driver.send(cmd)
            print("[DALI] Broadcast: All On")
            return True
        except Exception as e:
            print(f"[DALI] Error sending broadcast on: {e}")
            return False
    
    def broadcast_off(self) -> bool:
        """Turn off all DALI lights using broadcast"""
        if not self.is_connected or not self.driver:
            print("[DALI] Device not connected")
            return False
        
        try:
            with self.driver_lock:
                # Send broadcast Off command
                cmd = Off(Broadcast())
                self.driver.send(cmd)
            print("[DALI] Broadcast: Blackout (Off)")
            return True
        except Exception as e:
            print(f"[DALI] Error sending broadcast off: {e}")
            return False
    
    def check_channel_present(self, address: int) -> bool:
        """Check if a DALI device is present at given address
        
        Uses QueryControlGearPresent - the standard DALI commissioning check.
        Returns True only if device explicitly responds YES.
        """
        if not self.is_connected or not self.driver:
            return False
        
        if not (0 <= address <= 63):
            return False
        
        try:
            with self.driver_lock:
                # Small delay before query to let bus settle
                import time
                time.sleep(0.02)
                
                # QueryControlGearPresent is the proper way to detect devices
                cmd = QueryControlGearPresent(GearShort(address))
                response = self.driver.send(cmd)
            
            # Only return True if device explicitly responded YES
            # YesNoResponse.value will be True for YES, False for NO
            # None means no response (timeout)
            if response is not None and hasattr(response, 'value'):
                return response.value is True
            
            return False
        except Exception:
            return False
    
    def start_monitoring(self):
        """Start background thread to monitor device connection"""
        if not DALI_AVAILABLE:
            return
        
        self.stop_monitoring = False
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring_thread(self):
        """Stop the monitoring thread"""
        self.stop_monitoring = True
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
    
    def _monitor_loop(self):
        """Background thread to monitor and auto-reconnect to DALI device"""
        last_connected = False
        
        while not self.stop_monitoring:
            try:
                if not self.is_connected:
                    # Try to connect (only log on first attempt after disconnect)
                    if last_connected:
                        print("[DALI] Attempting to reconnect...")
                    device = self.find_hasseb_device()
                    if device:
                        self.connect(device)
                else:
                    # Check if device is still present by looking for it in HID enumeration
                    device = self.find_hasseb_device()
                    if not device:
                        print("[DALI] Device disconnected")
                        self.is_connected = False
                        if self.driver:
                            try:
                                self.driver.disconnect()
                            except:
                                pass
                        self.driver = None
                        if self.status_callback:
                            self.status_callback(False, self.device_path)
                
                # Notify if connection state changed
                if self.is_connected != last_connected:
                    last_connected = self.is_connected
                
            except Exception as e:
                print(f"[DALI] Error in monitoring: {e}")
            
            # Check every 2 seconds
            time.sleep(2)
    
    def __del__(self):
        """Cleanup on deletion"""
        self.stop_monitoring_thread()
        self.disconnect()
