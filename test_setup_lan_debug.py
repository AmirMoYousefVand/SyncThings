import subprocess

ps_cmd = "Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' -and $_.MediaType -eq '802.3' } | Select-Object -ExpandProperty Name"
startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, startupinfo=startupinfo)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)

ps_cmd2 = "Get-NetAdapter -Physical | Where-Object { $_.MediaType -eq '802.3' } | Select-Object -ExpandProperty Name"
result2 = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd2], capture_output=True, text=True, startupinfo=startupinfo)
print("STDOUT2:", result2.stdout)
