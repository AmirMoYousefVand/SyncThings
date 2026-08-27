# utils.py
import socket
import os
import sys
import logging
import datetime
import arabic_reshaper
from bidi.algorithm import get_display

def setup_logging():
    """Sets up a robust logging system that outputs to a logs folder next to the executable."""
    # Determine base directory
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.abspath(".")

    logs_dir = os.path.join(base_dir, "logs")

    if not os.path.exists(logs_dir):
        try:
            os.makedirs(logs_dir)
        except Exception:
            pass # Fail silently if we can't create the folder (e.g., permissions)

    log_filename = datetime.datetime.now().strftime("session_%Y%m%d_%H%M%S.log")
    log_filepath = os.path.join(logs_dir, log_filename)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')

    try:
        file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass # Fail silently if file cannot be created

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.info("--- SyncThings Session Started ---")

def log_memory(stage):
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / 1048576
        logging.info(f"[Memory] {stage}: {mem_mb:.2f} MB")
    except Exception as e:
        pass

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
    cmd = 'netsh advfirewall firewall add rule name="SyncThings Local" dir=in action=allow protocol=TCP localport=49152 profile=any & ' \
          'netsh advfirewall firewall add rule name="SyncThings Local UDP" dir=in action=allow protocol=UDP localport=49153 profile=any'

    if is_admin:
        os.system(cmd)
        return True
    else:
        # Request elevation and run the command
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", "/c " + cmd, None, 0)
        return int(ret) > 32 # ShellExecuteW returns > 32 on success

def ensure_firewall_rules():
    """Silently checks if firewall rules exist; only requests admin elevation if they don't."""
    import subprocess
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        # Check if both rules already exist
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all", "dir=in", "protocol=UDP", "localport=49153"],
            capture_output=True, text=True, startupinfo=startupinfo
        )
        if "SyncThings Local UDP" in result.stdout:
            return True  # Rules already exist, no elevation needed
    except Exception:
        pass
    # Rules don't exist yet, request elevation to create them
    return fix_windows_firewall()

def setup_direct_lan_ip():
    """Finds the active Ethernet connection and sets a random static IP for a direct LAN cable connection."""
    import ctypes
    import subprocess
    import random

    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False

    try:
        # Use PowerShell to robustly find Ethernet adapters (including USB-C dongles)
        # We drop -Physical because USB dongles are often not marked as physical.
        # We drop Status -eq 'Up' because direct cables often stay 'Identifying' or 'Disconnected' until an IP is set.
        ps_cmd = "(Get-NetAdapter | Where-Object { $_.InterfaceDescription -match 'Ethernet|GbE|Realtek|Intel|Killer|USB|LAN' -and $_.InterfaceDescription -notmatch 'Wi-Fi|Wireless|Bluetooth|Virtual|VMware|Hyper-V|TAP' } | Select-Object -First 1).Name"

        # Hide console window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, startupinfo=startupinfo)

        adapter_name = result.stdout.strip()

        if not adapter_name:
            return False, "Could not find an Ethernet adapter. Make sure the cable or USB adapter is plugged into the computer."

        ip_octet = random.randint(10, 250)
        ip_addr = f"192.168.137.{ip_octet}"

        # Setup IP, clear any gateway for pure local link, AND add firewall rules.
        # Direct LAN connections default to 'Public' profile which blocks inbound UDP unless explicitly allowed.
        cmd = (f'netsh interface ipv4 set address name="{adapter_name}" static {ip_addr} 255.255.255.0 & '
               f'netsh advfirewall firewall add rule name="SyncThings Local" dir=in action=allow protocol=TCP localport=49152 profile=any & '
               f'netsh advfirewall firewall add rule name="SyncThings Local UDP" dir=in action=allow protocol=UDP localport=49153 profile=any')

        if is_admin:
            os.system(cmd)
            return True, f"IP {ip_addr} assigned to {adapter_name} and firewall configured."
        else:
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", "/c " + cmd, None, 0)
            return int(ret) > 32, "Requested elevation to set IP and configure firewall."

    except Exception as e:
        return False, str(e)

def clear_temp_cache():
    """Clears temporary files generated by SyncThings."""
    import shutil
    import tempfile
    try:
        temp_dir = os.path.join(os.path.expanduser("~"), "Downloads", "SyncThings", "Temp")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

        # Clear temp files in OS temp folder starting with tmp and ending in .zip or .tmp
        sys_temp = tempfile.gettempdir()
        if os.path.exists(sys_temp):
            for file in os.listdir(sys_temp):
                if file.startswith("tmp") and (file.endswith(".zip") or file.endswith(".tmp")):
                    try:
                        os.remove(os.path.join(sys_temp, file))
                    except:
                        pass
        return True
    except Exception as e:
        logging.error(f"Error clearing cache: {e}")
        return False
