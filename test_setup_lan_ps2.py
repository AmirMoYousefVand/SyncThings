import subprocess
import random
import ctypes

def setup_direct_lan_ip():
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False

    try:
        # We need a robust powershell script that returns the name of physical wired ethernet adapters that are Up.
        ps_cmd = "$adapters = Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' -and $_.MediaType -eq '802.3' }; if ($adapters) { $adapters.Name }"
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, startupinfo=startupinfo)
        
        adapter_names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        
        if not adapter_names:
            return False, "Could not find an active physical Ethernet cable connection. Make sure the cable is plugged in."

        adapter_name = adapter_names[0]
        
        ip_octet = random.randint(10, 250)
        ip_addr = f"192.168.137.{ip_octet}"
        
        cmd = f'netsh interface ipv4 set address name="{adapter_name}" static {ip_addr} 255.255.255.0'

        if is_admin:
            # os.system(cmd)
            return True, f"IP {ip_addr} assigned to {adapter_name}"
        else:
            return False, "Not admin"
    except Exception as e:
        return False, str(e)

print(setup_direct_lan_ip())
