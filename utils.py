# utils.py
import socket
import os
import sys
import arabic_reshaper
from bidi.algorithm import get_display

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def format_persian(text):
    """Reshapes and applies BiDi algorithm with RTL base direction to fix mixed text."""
    if not text: return ""
    try:
        reshaped_text = arabic_reshaper.reshape(str(text))
        try:
            # Force RTL base direction to keep english substrings (like 'ed26') in correct logical order
            bidi_text = get_display(reshaped_text, base_dir='R')
        except TypeError:
            bidi_text = get_display(reshaped_text)
        return bidi_text
    except Exception:
        return text

def get_local_ips():
    """Returns a list of tuples: (ip_address, broadcast_address) for active network adapters using netifaces."""
    import netifaces

    ips = []
    try:
        # Get all interfaces
        interfaces = netifaces.interfaces()
        for iface in interfaces:
            addrs = netifaces.ifaddresses(iface)
            # Check if there are IPv4 addresses
            if netifaces.AF_INET in addrs:
                for link in addrs[netifaces.AF_INET]:
                    ip = link.get('addr')
                    broadcast = link.get('broadcast')

                    if ip and not ip.startswith("127."):
                        # If broadcast address is missing, we try to guess it
                        # but normally netifaces provides it
                        if not broadcast:
                            parts = ip.split('.')
                            if len(parts) == 4:
                                parts[3] = '255'
                                broadcast = '.'.join(parts)

                        ips.append((ip, broadcast))

    except Exception as e:
        print(f"Error getting IPs with netifaces: {e}")
        pass

    return ips

def fix_windows_firewall():
    """Requests Admin privileges and unblocks the app's TCP/UDP ports in Windows Firewall."""
    import ctypes
    import sys
    try:
        # Check if already admin
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False

    # The command to run
    # We add an inbound/outbound rule for our custom ports
    cmd = 'netsh advfirewall firewall add rule name="SyncThings Local" dir=in action=allow protocol=TCP localport=49152 & ' \
          'netsh advfirewall firewall add rule name="SyncThings Local UDP" dir=in action=allow protocol=UDP localport=49153'

    if is_admin:
        os.system(cmd)
        return True
    else:
        # Request elevation and run the command
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", "/c " + cmd, None, 0)
        return int(ret) > 32 # ShellExecuteW returns > 32 on success
