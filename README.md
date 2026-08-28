# SyncThings v2.0.0

SyncThings is a simple, lightweight, and modern cross-platform application to seamlessly share clipboard text, images, and files over your local network between devices. 

## Features

- **Private Sync (Screen Sync)**: Global hotkey to silently capture the entire screen and automatically copy it to the receiver's clipboard without any traces.
- **Private Paste**: Global hotkey to stealthily "type" clipboard text to bypass web copy/paste listeners and anti-cheat systems.
- **File Restrictions**: Set limits on maximum file size and allowed/blocked extensions before sending.
- **Transfer Controls**: Pause, Resume, and Cancel transfers in real-time, perfectly synced across both devices without dropping connections.
- **LAN Discovery Auto-Fixes**: Automatically applies Windows Firewall rules and forces UDP broadcasts out the correct physical port for seamless offline LAN connection.
- **RTL & UI Polish**: Full Right-to-Left support for Persian dialogs, automatic light/dark icon switching, and scrollable settings.
- **Clipboard Sync**: Instantly share text and images copied to your clipboard.
- **File Transfer**: Easily send single or multiple files by copying them.
- **QR Code Pairing**: Connect effortlessly using a QR code.
- **Auto Discovery**: Automatically discover other devices running SyncThings on your network.
- **Dark/Light Mode & Localization**: Fully supports Dark and Light themes with English and Persian languages.
- **Secure**: Transfers happen entirely locally over your WiFi/Ethernet without going through external servers.

## Download & Installation

You can download the latest version from the [Releases page](../../releases). 
Pre-built binaries are available for Windows. 

1. Download the `SyncThings-Windows.exe` file.
2. Extract the archive to any folder.
3. Run `SyncThings.exe`.

*Note: On your first run, Windows Firewall might prompt you to allow the app through the network. Please allow it to ensure devices can discover and connect to each other.*

## How to Use

### 1. Connecting Devices

There are a few ways to connect your devices:
- **Auto Discovery**: Go to the **Search & Connect** tab and click **Search Network**. Discovered devices will appear in the list. Click **Connect**.
- **QR Code**: On one device, go to **Search & Connect**. You will see your QR Code. On the second device, click **Scan QR Code** to read it.
- **Manual IP**: Enter the IP address shown on the other device's Dashboard and hit **Connect**.

*Note: When a connection request is initiated, the target device will show a prompt to accept or reject the connection.*

### 2. Transferring Data

Once connected, simply copy text, an image, or files to your clipboard on one device (e.g., using `Ctrl+C`). It will automatically be transferred to the connected device's clipboard!

## Architecture & Engineering

SyncThings is built using Python with a modern UI approach using CustomTkinter. 

- **UI Framework**: CustomTkinter
- **Networking**: Raw TCP/UDP Sockets with extreme performance optimizations.
  - UDP (Port 49153) is used for network discovery and broadcasting.
  - TCP (Port 49152) is used for reliable data transfer (text, images, files).
  - Uses `memoryview` and zero-copy abstractions for gigabit network saturation. Internal application benchmarks achieve up to **1.8 GB/s (1800 MB/s)** locally, ensuring physical networks are the only bottleneck.
  - Optimized disk I/O with 4MB accumulated buffers prevents fragmented SSD writes.
  - Skips intermediate `.zip` processing for single large files, directly piping bytes to maximize IOPS.
- **Clipboard Management**: Uses `pyperclip` for text and `PIL.ImageGrab` / internal Windows API calls for images and files.
- **Packaging**: Packaged into a standalone executable using PyInstaller.

## Important Note on Transfer Speeds
To experience the maximum file transfer speeds (100+ MB/s):
1. **Use a physical Ethernet cable (LAN)** or a high-end 5GHz/Wi-Fi 6 router. 
2. **Avoid mobile hotspots:** A standard 2.4GHz mobile hotspot operates in half-duplex mode. Because data must travel from *Laptop A -> Phone -> Laptop B*, the bandwidth is halved, physically capping your maximum transfer speed at around **3 to 4 MB/s**, regardless of SSD capabilities.
3. **Disable Proxies/VPNs:** Applications that hook into Windows networking (like Proxifier or V2rayNG) will intercept local LAN traffic, causing massive CPU overhead and breaking direct zero-copy pathways. Ensure local IP subnets are set to "Direct" or "Bypass".

## Building from Source

Ensure you have Python 3.9+ installed.

1. Clone the repository:
   ```bash
   git clone https://github.com/AmirMoYousefVand/SyncThings.git
   cd SyncThings
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

4. (Optional) Build the executable:
   ```bash
   pyinstaller --noconfirm --windowed --icon=app.ico --add-data "Fonts;Fonts" --add-data "app.ico;." main.py
   ```
