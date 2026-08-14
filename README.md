# SyncThings

SyncThings is a simple, lightweight, and modern cross-platform application to seamlessly share clipboard text, images, and files over your local network between devices. 

## Features

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
- **Networking**: Raw TCP/UDP Sockets
  - UDP (Port 49153) is used for network discovery and broadcasting.
  - TCP (Port 49152) is used for reliable data transfer (text, images, files).
- **Clipboard Management**: Uses `pyperclip` for text and `PIL.ImageGrab` / internal Windows API calls for images and files.
- **Packaging**: Packaged into a standalone executable using PyInstaller.

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
