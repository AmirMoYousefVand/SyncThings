import subprocess
cmd = 'wmic nic where "NetConnectionStatus=2 and PhysicalAdapter=TRUE" get NetConnectionID /value'
startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
print("STDOUT:", repr(result.stdout))
print("STDERR:", repr(result.stderr))
