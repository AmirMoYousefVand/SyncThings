import urllib.request
import os

icons = {
    # Name: (White Icon URL)
    "dash": "https://img.icons8.com/ios-filled/100/ffffff/dashboard.png",
    "connect": "https://img.icons8.com/ios-filled/100/ffffff/wifi.png",
    "settings": "https://img.icons8.com/ios-filled/100/ffffff/settings.png",
    "github": "https://img.icons8.com/ios-filled/100/ffffff/github.png",
    "disconnect": "https://img.icons8.com/ios-filled/100/ffffff/power-off-button.png",
    "scan": "https://img.icons8.com/ios-filled/100/ffffff/qr-code.png",
    "refresh": "https://img.icons8.com/ios-filled/100/ffffff/refresh.png",
    "plug": "https://img.icons8.com/ios-filled/100/ffffff/plug.png",
    "rand": "https://img.icons8.com/ios-filled/100/ffffff/dice.png",
    "upload": "https://img.icons8.com/ios-filled/100/ffffff/upload.png",
    "firewall": "https://img.icons8.com/ios-filled/100/ffffff/shield.png",
    "lan": "https://img.icons8.com/ios-filled/100/ffffff/network-cable.png",
    "link": "https://img.icons8.com/ios-filled/100/ffffff/link.png",
    "trash": "https://img.icons8.com/ios-filled/100/ffffff/trash.png"
}

def fetch():
    os.makedirs("Icons", exist_ok=True)
    for name, url in icons.items():
        print(f"Downloading {name}...")
        try:
            # We now only need the white icon (which we save as _light.png to match existing CTkImage setups)
            urllib.request.urlretrieve(url, f"Icons/{name}_light.png")
            # Create a copy as _dark.png just so the code doesn't break if it looks for it
            import shutil
            shutil.copy(f"Icons/{name}_light.png", f"Icons/{name}_dark.png")
        except Exception as e:
            print(f"Failed on {name}: {e}")

if __name__ == "__main__":
    fetch()
