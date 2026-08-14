import win32clipboard
import win32con
from PIL import ImageGrab, Image
import io
import os
import zipfile
import struct
from datetime import datetime
import time
import threading

class ClipboardManager:
    def __init__(self):
        self.last_seq_num = 0
        self.ignore_next = False
        self.running = False
        self._thread = None

    def start_monitoring(self, on_clipboard_change_callback):
        self.running = True
        self.callback = on_clipboard_change_callback
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop_monitoring(self):
        self.running = False

    def _monitor_loop(self):
        try:
            self.last_seq_num = win32clipboard.GetClipboardSequenceNumber()
        except:
            pass

        while self.running:
            time.sleep(1)
            try:
                current_seq = win32clipboard.GetClipboardSequenceNumber()
                if current_seq != self.last_seq_num:
                    self.last_seq_num = current_seq
                    if self.ignore_next:
                        self.ignore_next = False
                        continue
                    self.check_and_send_clipboard()
            except:
                pass

    def check_and_send_clipboard(self):
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                paths = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                win32clipboard.CloseClipboard()
                self.callback('files', paths)
                return
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB) or win32clipboard.IsClipboardFormatAvailable(win32con.CF_BITMAP):
                win32clipboard.CloseClipboard()
                img = ImageGrab.grabclipboard()
                if isinstance(img, Image.Image):
                    self.callback('image', img)
                return
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                self.callback('text', text)
                return
            win32clipboard.CloseClipboard()
        except:
            pass

    def set_clipboard_text(self, text):
        self.ignore_next = True
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            self.last_seq_num = win32clipboard.GetClipboardSequenceNumber()
        except:
            self.ignore_next = False

    def set_clipboard_image(self, image_bytes):
        self.ignore_next = True
        try:
            img = Image.open(io.BytesIO(image_bytes))
            output = io.BytesIO()
            img.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_DIB, data)
            win32clipboard.CloseClipboard()
            self.last_seq_num = win32clipboard.GetClipboardSequenceNumber()
        except:
            self.ignore_next = False

    def extract_and_set_files(self, zip_bytes):
        self.ignore_next = True
        try:
            save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "SyncThings", datetime.now().strftime("%Y%m%d_%H%M%S"))
            os.makedirs(save_dir, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
                zf.extractall(save_dir)
            paths = [os.path.abspath(os.path.join(save_dir, n)) for n in os.listdir(save_dir)]
            stc_dropfiles = struct.pack("5I", struct.calcsize("5I"), 0, 0, 0, 1)
            data = stc_dropfiles + ("\0".join(paths) + "\0\0").encode('utf-16le')
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_HDROP, data)
            win32clipboard.CloseClipboard()
            self.last_seq_num = win32clipboard.GetClipboardSequenceNumber()
        except:
            self.ignore_next = False