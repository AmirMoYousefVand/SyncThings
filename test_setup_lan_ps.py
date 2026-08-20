import subprocess
import ctypes
import random
import os
import sys

def setup_direct_lan_ip():
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False

    try:
        # Instead of WMIC which gives formatting issues or doesn't find physical nicely, use powershell Get-NetAdapter
        ps_cmd = "Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' -and $_.MediaType -eq '802.3' } | Select-Object -ExpandProperty Name"
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # Run PowerShell command
        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, startupinfo=startupinfo)
        
        adapter_names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        
        if not adapter_names:
            return False, "Could not find an active physical Ethernet cable connection."

        adapter_name = adapter_names[0]
        
        ip_octet = random.randint(10, 250)
        ip_addr = f"192.168.137.{ip_octet}"
        
        cmd = f'netsh interface ipv4 set address name="{adapter_name}" static {ip_addr} 255.255.255.0'

        print(f"Would run: {cmd}")
        return True, f"IP {ip_addr} assigned to {adapter_name}"
    except Exception as e:
        return False, str(e)

print(setup_direct_lan_ip())
