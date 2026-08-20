import subprocess

ps_cmd2 = "Get-NetAdapter -Physical | Where-Object { $_.MediaType -eq '802.3' } | Select-Object -Property Name, Status, MediaType"
startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

result2 = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd2], capture_output=True, text=True, startupinfo=startupinfo)
print("STDOUT2:", result2.stdout)
