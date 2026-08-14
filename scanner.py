# scanner.py
import cv2
from pyzbar.pyzbar import decode
from PIL import Image

class QRScanner:
    def __init__(self, on_qr_scanned=None, on_error=None):
        self.cap = None
        self.is_active = False
        self.on_qr_scanned = on_qr_scanned
        self.on_error = on_error

    def start(self):
        """Starts the camera."""
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            if self.on_error:
                self.on_error()
            return False
        self.is_active = True
        return True

    def read_frame(self):
        """Reads a frame from the camera, decodes QR, and returns a PIL Image."""
        if not self.is_active or not self.cap:
            return None

        ret, frame = self.cap.read()
        if not ret:
            return None

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            decoded = decode(gray)
            for obj in decoded:
                data = obj.data.decode('utf-8')
                if data.startswith("SYNCIP:"):
                    ip = data.split(":")[1]
                    self.stop()
                    if self.on_qr_scanned:
                        self.on_qr_scanned(ip)
                    return None
        except Exception:
            pass

        # Convert to RGB for display
        cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(cv2image)
        return img

    def stop(self):
        """Stops the camera."""
        self.is_active = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.cap = None
