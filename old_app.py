import socket
import threading
import struct
import uuid
import os
import io
import time
import zipfile
import json
import hashlib
from datetime import datetime
from tkinter import filedialog
import tkinter as tk

import customtkinter as ctk
import win32clipboard
import win32con
from PIL import ImageGrab, Image, ImageTk, ImageDraw, ImageFont
import qrcode
import cv2
from pyzbar.pyzbar import decode
import arabic_reshaper
from bidi.algorithm import get_display

# Modern dark theme colors
BG_COLOR = "#0F172A"       # Deep slate blue
SIDEBAR_COLOR = "#1E293B"  # Lighter slate
CARD_COLOR = "#334155"     # Even lighter slate
ACCENT_COLOR = "#38BDF8"   # Bright sky blue
TEXT_COLOR = "#F8FAFC"     # Off-white
SUCCESS_COLOR = "#10B981"  # Emerald green
ERROR_COLOR = "#EF4444"    # Red
WARNING_COLOR = "#F59E0B"  # Amber

ctk.set_appearance_mode("Dark")

# Network constants
TCP_PORT = 49152
UDP_PORT = 49153
MAGIC_WORD = b"SYNC_THINGS_V2:"

# Data types
TYPE_TEXT = 1
TYPE_IMAGE = 2
TYPE_FILES = 3
TYPE_PROFILE = 4

CONFIG_FILE = "sync_things_profile.json"
FONT_MAIN = "Vazirmatn"
FONT_NUM = "Segoe UI"

def format_persian(text):
    """Reshapes and applies BiDi algorithm with RTL base direction to fix mixed text."""
    if not text: return ""
    try:
        reshaped_text = arabic_reshaper.reshape(str(text))
        try:
            # Force RTL base direction to keep english substrings (like 'ed26') in correct logical order
            bidi_text = get_display(reshaped_text, base_dir='R')
        except TypeError:
            bidi_text = get_display(reshaped_text)
        return bidi_text
    except Exception:
        return text

class RTLMessageDialog(ctk.CTkToplevel):
    """Custom popup dialog to ensure perfect RTL rendering."""
    def __init__(self, title, message, yes_no=False):
        super().__init__()
        self.title(title)
        self.geometry("420x220")
        self.configure(fg_color=SIDEBAR_COLOR)
        self.attributes("-topmost", True)
        self.resizable(False, False)

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (420 // 2)
        y = (self.winfo_screenheight() // 2) - (220 // 2)
        self.geometry(f"+{x}+{y}")

        self.result = False

        # Add RLM (‏) for Persian to ensure trailing punctuation is rendered correctly
        display_text = format_persian(message + "‏")
        lbl = ctk.CTkLabel(
            self,
            text=display_text,
            font=ctk.CTkFont(family=FONT_MAIN, size=15),
            wraplength=380,
            justify="right"
        )
        lbl.pack(expand=True, pady=(30, 10), padx=20, fill="both")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 25), padx=30)
        
        if yes_no:
            btn_yes = ctk.CTkButton(btn_frame, text=format_persian("بله"), command=self.on_yes, fg_color=SUCCESS_COLOR, hover_color="#059669", font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold"))
            btn_yes.pack(side="right", padx=10, expand=True, fill="x")
            
            btn_no = ctk.CTkButton(btn_frame, text=format_persian("خیر"), command=self.on_no, fg_color=ERROR_COLOR, hover_color="#DC2626", font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold"))
            btn_no.pack(side="left", padx=10, expand=True, fill="x")
        else:
            btn_ok = ctk.CTkButton(btn_frame, text=format_persian("تایید"), command=self.on_yes, fg_color=ACCENT_COLOR, text_color=BG_COLOR, hover_color="#0284C7", font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold"))
            btn_ok.pack(expand=True, fill="x", padx=60)
            
        self.grab_set()
        self.wait_window()
        
    def on_yes(self):
        self.result = True
        self.destroy()
        
    def on_no(self):
        self.result = False
        self.destroy()

class SyncThingsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Sync/things")
        self.geometry("1000x700")
        self.minsize(900, 600)
        self.configure(fg_color=BG_COLOR)

        # State and network variables
        self.app_id = str(uuid.uuid4())
        self.peer_socket = None
        self.connected = False
        self.ignore_next_clipboard = False
        self.last_seq_num = 0
        self.active_nav = 'dashboard'
        
        # Profile variables
        self.profile_name = "کاربر_" + self.app_id[:4]
        self.avatar_path = None
        self.peer_profile_name = "ناشناس"
        
        # Camera and discovered peers
        self.camera_active = False
        self.cap = None
        self.discovered_peers = {}

        self.load_profile()
        self.setup_ui()
        self.setup_network()
        
        # Clipboard monitor
        self.monitor_thread = threading.Thread(target=self.monitor_clipboard_loop, daemon=True)
        self.monitor_thread.start()

    def load_profile(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.profile_name = config.get("name", self.profile_name)
                    self.avatar_path = config.get("avatar", None)
            except: pass

    def save_profile(self):
        config = {"name": self.profile_name, "avatar": self.avatar_path}
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False)

    def generate_default_avatar(self, name, size=100):
        hash_val = int(hashlib.md5(name.encode('utf-8')).hexdigest(), 16)
        colors = ["#F43F5E", "#F97316", "#EAB308", "#22C55E", "#14B8A6", "#0EA5E9", "#8B5CF6", "#D946EF"]
        bg_color = colors[hash_val % len(colors)]
        
        img = Image.new('RGB', (size, size), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        first_letter = name[0] if name else "?"
        try:
            font = ImageFont.truetype("arial.ttf", int(size*0.4))
        except:
            font = ImageFont.load_default()
            
        try:
            bbox = draw.textbbox((0, 0), first_letter, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            w, h = draw.textsize(first_letter, font=font)
            
        draw.text(((size-w)/2, (size-h)/2 - (size*0.05)), first_letter, fill="#FFFFFF", font=font)
        
        mask = Image.new('L', (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        
        output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        output.paste(img, (0, 0), mask=mask)
        return output

    def get_avatar_image(self, path, name, size=100):
        if path and os.path.exists(path):
            try:
                img = Image.open(path).convert("RGBA").resize((size, size))
                mask = Image.new('L', (size, size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, size, size), fill=255)
                output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
                output.paste(img, (0, 0), mask=mask)
                return output
            except: pass
        return self.generate_default_avatar(name, size)

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=240, fg_color=SIDEBAR_COLOR, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        # Logo Area (Icon and Text completely separated)
        logo_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=(30, 40), sticky="ew")
        
        logo_icon = ctk.CTkLabel(logo_frame, text="⚡", font=ctk.CTkFont(size=28), text_color=ACCENT_COLOR)
        logo_icon.pack(side="left")
        logo_text = ctk.CTkLabel(logo_frame, text="Sync/things", font=ctk.CTkFont(family=FONT_NUM, size=22, weight="bold"), text_color=TEXT_COLOR)
        logo_text.pack(side="left", padx=(5, 0))

        # Navigation Buttons (Fully isolated logic)
        self.nav_btns = {}
        self.nav_btns['dashboard'] = self.create_nav_button("داشبورد", "🏠", 1, 'dashboard')
        self.nav_btns['connect'] = self.create_nav_button("جستجو و اتصال", "🔗", 2, 'connect')
        self.nav_btns['settings'] = self.create_nav_button("تنظیمات پروفایل", "⚙️", 3, 'settings')

        # User Profile (Bottom of sidebar)
        self.sidebar_profile = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.sidebar_profile.grid(row=5, column=0, padx=20, pady=20, sticky="ew")
        
        self.sidebar_avatar_lbl = ctk.CTkLabel(self.sidebar_profile, text="")
        self.sidebar_avatar_lbl.pack(side="left")
        self.sidebar_name_lbl = ctk.CTkLabel(self.sidebar_profile, text="", font=ctk.CTkFont(family=FONT_MAIN, size=14, weight="bold"))
        self.sidebar_name_lbl.pack(side="left", padx=10)
        self.update_sidebar_profile()

        # --- Main Content Area ---
        self.main_container = ctk.CTkFrame(self, fg_color=BG_COLOR, corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        self.setup_dashboard_frame()
        self.setup_connect_frame()
        self.setup_settings_frame()

        self.show_dashboard()

    def create_nav_button(self, text_val, icon_val, row, nav_id):
        """Creates a customized navigation button with strictly separated text and icon widgets."""
        btn_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent", corner_radius=8, cursor="hand2", height=45)
        btn_frame.grid(row=row, column=0, sticky="ew", padx=15, pady=5)
        btn_frame.pack_propagate(False)
        
        lbl_icon = ctk.CTkLabel(btn_frame, text=icon_val, font=ctk.CTkFont(size=20), text_color=TEXT_COLOR)
        lbl_icon.pack(side="right", padx=(10, 15))
        
        lbl_text = ctk.CTkLabel(btn_frame, text=format_persian(text_val), font=ctk.CTkFont(family=FONT_MAIN, size=15), text_color=TEXT_COLOR)
        lbl_text.pack(side="right", fill="x", expand=True, anchor="e")
        
        def on_enter(e):
            if self.active_nav != nav_id:
                btn_frame.configure(fg_color=CARD_COLOR)
        def on_leave(e):
            if self.active_nav != nav_id:
                btn_frame.configure(fg_color="transparent")
        def on_click(e):
            if nav_id == 'dashboard': self.show_dashboard()
            elif nav_id == 'connect': self.show_connect()
            elif nav_id == 'settings': self.show_settings()
            
        for w in [btn_frame, lbl_icon, lbl_text]:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)
            
        return {"frame": btn_frame, "icon": lbl_icon, "text": lbl_text}

    def update_sidebar_profile(self):
        img = self.get_avatar_image(self.avatar_path, self.profile_name, 36)
        photo = ctk.CTkImage(light_image=img, dark_image=img, size=(36, 36))
        self.sidebar_avatar_lbl.configure(image=photo)
        self.sidebar_name_lbl.configure(text=format_persian(self.profile_name))

    def setup_dashboard_frame(self):
        frm = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.frames['dashboard'] = frm
        
        # Header (Greeting) - Segmented to completely avoid BiDi engine collapse
        header_frame = ctk.CTkFrame(frm, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 30))
        
        lbl_salam = ctk.CTkLabel(header_frame, text=format_persian("سلام"), font=ctk.CTkFont(family=FONT_MAIN, size=26, weight="bold"))
        lbl_salam.pack(side="right")
        
        self.lbl_greeting_name = ctk.CTkLabel(header_frame, text=format_persian(self.profile_name), font=ctk.CTkFont(family=FONT_MAIN, size=26, weight="bold"), text_color=ACCENT_COLOR)
        self.lbl_greeting_name.pack(side="right", padx=(8, 0))
        
        lbl_comma = ctk.CTkLabel(header_frame, text="،", font=ctk.CTkFont(family=FONT_MAIN, size=26, weight="bold"))
        lbl_comma.pack(side="right")
        
        lbl_be = ctk.CTkLabel(header_frame, text=format_persian("به"), font=ctk.CTkFont(family=FONT_MAIN, size=26, weight="bold"))
        lbl_be.pack(side="right", padx=(8, 8))
        
        app_name_label = ctk.CTkLabel(header_frame, text="Sync/things", font=ctk.CTkFont(family=FONT_NUM, size=26, weight="bold"), text_color=ACCENT_COLOR)
        app_name_label.pack(side="right")
        
        greeting_part2 = ctk.CTkLabel(header_frame, text=format_persian("خوش آمدید"), font=ctk.CTkFont(family=FONT_MAIN, size=26, weight="bold"))
        greeting_part2.pack(side="right", padx=(8, 0))

        # Status Cards Grid
        cards_frame = ctk.CTkFrame(frm, fg_color="transparent")
        cards_frame.pack(fill="x", pady=10)
        cards_frame.grid_columnconfigure((0,1,2), weight=1)

        # 1. Connection Status Card
        self.status_card = ctk.CTkFrame(cards_frame, fg_color=CARD_COLOR, corner_radius=12, height=160)
        self.status_card.grid(row=0, column=2, padx=10, sticky="ew")
        self.status_card.grid_propagate(False)
        
        self.status_inner = ctk.CTkFrame(self.status_card, fg_color="transparent")
        self.status_inner.place(relx=0.5, rely=0.5, anchor="center")
        
        status_title = ctk.CTkLabel(self.status_inner, text=format_persian("وضعیت سیستم"), font=ctk.CTkFont(family=FONT_MAIN, size=14), text_color="#94A3B8")
        status_title.pack(pady=(0, 10))
        
        self.status_indicator_frame = ctk.CTkFrame(self.status_inner, fg_color="transparent")
        self.status_indicator_frame.pack()
        
        # Disconnect button (Initialized but NOT packed initially)
        self.btn_disconnect = ctk.CTkButton(self.status_inner, text=format_persian("قطع اتصال"), font=ctk.CTkFont(family=FONT_MAIN, size=13, weight="bold"),
                                            fg_color=ERROR_COLOR, hover_color="#DC2626", text_color="#FFFFFF",
                                            height=30, width=100, command=self.disconnect_peer)

        # Isolated dot icon
        self.dash_status_icon = ctk.CTkLabel(self.status_indicator_frame, text="●", font=ctk.CTkFont(size=20), text_color=ERROR_COLOR)
        self.dash_status_icon.pack(side="right", padx=(0, 5))
        self.dash_status_lbl = ctk.CTkLabel(self.status_indicator_frame, text=format_persian("عدم اتصال"), font=ctk.CTkFont(family=FONT_MAIN, size=18, weight="bold"))
        self.dash_status_lbl.pack(side="right")

        # 2. IP Card
        ip_card = ctk.CTkFrame(cards_frame, fg_color=CARD_COLOR, corner_radius=12, height=160)
        ip_card.grid(row=0, column=1, padx=10, sticky="ew")
        ip_card.grid_propagate(False)
        
        ip_inner = ctk.CTkFrame(ip_card, fg_color="transparent")
        ip_inner.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(ip_inner, text=format_persian("آدرس IP شما"), font=ctk.CTkFont(family=FONT_MAIN, size=14), text_color="#94A3B8").pack(pady=(0, 10))
        local_ips = self.get_local_ips()
        display_ip = " / ".join(local_ips) if local_ips else "127.0.0.1"
        ip_lbl = ctk.CTkLabel(ip_inner, text=display_ip, font=ctk.CTkFont(family=FONT_NUM, size=16, weight="bold"), text_color=TEXT_COLOR)
        ip_lbl.configure(wraplength=200)
        ip_lbl.pack()

        # 3. Connected Peer Card
        self.peer_card = ctk.CTkFrame(cards_frame, fg_color=CARD_COLOR, corner_radius=12, height=160)
        self.peer_card.grid(row=0, column=0, padx=10, sticky="ew")
        self.peer_card.grid_propagate(False)
        
        peer_inner = ctk.CTkFrame(self.peer_card, fg_color="transparent")
        peer_inner.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(peer_inner, text=format_persian("دستگاه متصل"), font=ctk.CTkFont(family=FONT_MAIN, size=14), text_color="#94A3B8").pack(pady=(0, 10))
        self.dash_peer_lbl = ctk.CTkLabel(peer_inner, text="---", font=ctk.CTkFont(family=FONT_MAIN, size=18, weight="bold"))
        self.dash_peer_lbl.pack()

        # Logs Section
        log_frame = ctk.CTkFrame(frm, fg_color=CARD_COLOR, corner_radius=12)
        log_frame.pack(fill="both", expand=True, pady=30, padx=10)
        
        ctk.CTkLabel(log_frame, text=format_persian("تاریخچه رویدادها"), font=ctk.CTkFont(family=FONT_MAIN, size=15, weight="bold")).pack(anchor="e", padx=20, pady=15)
        
        self.log_box = ctk.CTkTextbox(log_frame, font=ctk.CTkFont(family=FONT_MAIN, size=13), fg_color="#1E293B", text_color=TEXT_COLOR, corner_radius=8)
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.log_box.configure(state="disabled")

    def create_custom_icon_btn(self, parent, text_val, icon_val, command, fg_color, hover_color, width):
        """Creates a robust custom button with separated text and emoji labels."""
        frame = ctk.CTkFrame(parent, fg_color=fg_color, corner_radius=6, cursor="hand2", height=40, width=width)
        frame.pack_propagate(False)
        
        icon_lbl = ctk.CTkLabel(frame, text=icon_val, font=ctk.CTkFont(size=18), text_color=TEXT_COLOR)
        icon_lbl.pack(side="right", padx=(10, 5))
        
        text_lbl = ctk.CTkLabel(frame, text=format_persian(text_val), font=ctk.CTkFont(family=FONT_MAIN, size=14), text_color=TEXT_COLOR)
        text_lbl.pack(side="right", padx=(0, 10))
        
        def on_enter(e): frame.configure(fg_color=hover_color)
        def on_leave(e): frame.configure(fg_color=fg_color)
        def on_click(e): command()
        
        for w in [frame, icon_lbl, text_lbl]:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)
        return frame

    def setup_connect_frame(self):
        frm = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.frames['connect'] = frm

        header_frame = ctk.CTkFrame(frm, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))
        title = ctk.CTkLabel(header_frame, text=format_persian("اتصال به دستگاه‌ها"), font=ctk.CTkFont(family=FONT_MAIN, size=24, weight="bold"))
        title.pack(side="right")

        controls_frame = ctk.CTkFrame(frm, fg_color="transparent")
        controls_frame.pack(fill="x", pady=(0,20))
        
        # Pure Text Button
        self.btn_discover = ctk.CTkButton(controls_frame, text=format_persian("جستجوی خودکار"), font=ctk.CTkFont(family=FONT_MAIN, size=14),
                                          command=self.start_discovery, fg_color=ACCENT_COLOR, text_color=BG_COLOR, hover_color="#7DD3FC", height=40)
        self.btn_discover.pack(side="right", padx=5)

        # Custom Separated Icon Button
        self.btn_scan_qr = self.create_custom_icon_btn(controls_frame, "اسکن بارکد", "📷", self.toggle_camera, CARD_COLOR, "#475569", width=130)
        self.btn_scan_qr.pack(side="right", padx=5)

        # Manual Connection Frame
        manual_frame = ctk.CTkFrame(controls_frame, fg_color=CARD_COLOR, corner_radius=8, height=40)
        manual_frame.pack(side="left", padx=5)
        manual_frame.pack_propagate(False)
        
        self.ip_entry = ctk.CTkEntry(manual_frame, placeholder_text="192.168.x.x", font=ctk.CTkFont(family=FONT_NUM, size=14), width=130, border_width=0, fg_color="transparent")
        self.ip_entry.pack(side="left", padx=10, fill="y")
        
        self.btn_manual = ctk.CTkButton(manual_frame, text=format_persian("اتصال"), font=ctk.CTkFont(family=FONT_MAIN, size=13), width=60, height=30, fg_color=ACCENT_COLOR, text_color=BG_COLOR, command=self.manual_connect)
        self.btn_manual.pack(side="left", padx=(0, 5))

        # QR Code Panel
        qr_panel = ctk.CTkFrame(frm, fg_color=CARD_COLOR, corner_radius=12)
        qr_panel.pack(fill="x", pady=10)
        
        local_ips = self.get_local_ips()
        display_ip = local_ips[0] if local_ips else "127.0.0.1"
        
        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr.add_data(f"SYNCIP:{display_ip}")
        qr.make(fit=True)
        pil_img = qr.make_image(fill_color="black", back_color="white").get_image()
        self.qr_photo = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(100, 100))
        
        ctk.CTkLabel(qr_panel, image=self.qr_photo, text="").pack(side="left", padx=25, pady=25)
        
        qr_info = ctk.CTkFrame(qr_panel, fg_color="transparent")
        qr_info.pack(side="right", fill="both", expand=True, padx=20)
        
        ctk.CTkLabel(qr_info, text=format_persian("برای اتصال سریع، این بارکد را در سیستم مقابل اسکن کنید"), font=ctk.CTkFont(family=FONT_MAIN, size=14), justify="right", text_color="#94A3B8").pack(anchor="e", pady=(30, 10))
        
        ip_row = ctk.CTkFrame(qr_info, fg_color="transparent")
        ip_row.pack(anchor="e")
        all_ips = " / ".join(local_ips) if local_ips else "127.0.0.1"
        ctk.CTkLabel(ip_row, text=all_ips, font=ctk.CTkFont(family=FONT_NUM, size=14, weight="bold"), text_color=ACCENT_COLOR).pack(side="left")
        ctk.CTkLabel(ip_row, text=" IPs: ", font=ctk.CTkFont(family=FONT_NUM, size=16), text_color="#94A3B8").pack(side="left")

        # Camera Panel
        self.camera_panel = ctk.CTkFrame(frm, fg_color=CARD_COLOR, corner_radius=12)
        self.camera_label = ctk.CTkLabel(self.camera_panel, text=format_persian("در حال باز کردن دوربین..."), font=ctk.CTkFont(family=FONT_MAIN, size=15))
        self.camera_label.pack(pady=10, padx=10, expand=True)
        btn_close_cam = ctk.CTkButton(self.camera_panel, text=format_persian("بستن دوربین"), font=ctk.CTkFont(family=FONT_MAIN, size=13), fg_color=ERROR_COLOR, hover_color="#F87171", command=self.stop_camera)
        btn_close_cam.pack(pady=15)

        ctk.CTkLabel(frm, text=format_persian("دستگاه‌های پیدا شده در شبکه:"), font=ctk.CTkFont(family=FONT_MAIN, size=15, weight="bold")).pack(anchor="e", pady=(20, 10))
        self.devices_scroll = ctk.CTkScrollableFrame(frm, fg_color=CARD_COLOR, corner_radius=12)
        self.devices_scroll.pack(fill="both", expand=True)

    def setup_settings_frame(self):
        frm = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.frames['settings'] = frm

        title = ctk.CTkLabel(frm, text=format_persian("تنظیمات پروفایل"), font=ctk.CTkFont(family=FONT_MAIN, size=24, weight="bold"))
        title.pack(anchor="e", pady=(0, 20))

        content_card = ctk.CTkFrame(frm, fg_color=CARD_COLOR, corner_radius=12)
        content_card.pack(fill="both", expand=True, pady=10)

        self.settings_avatar_lbl = ctk.CTkLabel(content_card, text="")
        self.settings_avatar_lbl.pack(pady=(40, 15))
        self.update_settings_avatar()

        btn_avatar = ctk.CTkButton(content_card, text=format_persian("تغییر آواتار..."), font=ctk.CTkFont(family=FONT_MAIN, size=13), width=130, fg_color=SIDEBAR_COLOR, hover_color="#475569", command=self.choose_avatar)
        btn_avatar.pack(pady=10)

        ctk.CTkLabel(content_card, text=format_persian("نام نمایشی شما:"), font=ctk.CTkFont(family=FONT_MAIN, size=14), text_color="#94A3B8").pack(pady=(30, 5))
        
        self.name_entry = ctk.CTkEntry(content_card, font=ctk.CTkFont(family=FONT_MAIN, size=16), justify="center", width=250, height=45, corner_radius=8, border_width=1, border_color="#475569", fg_color="#1E293B")
        self.name_entry.insert(0, self.profile_name)
        self.name_entry.pack(pady=10)

        btn_save = ctk.CTkButton(content_card, text=format_persian("ذخیره تغییرات"), font=ctk.CTkFont(family=FONT_MAIN, size=15), height=45, fg_color=ACCENT_COLOR, text_color=BG_COLOR, hover_color="#7DD3FC", command=self.save_profile_ui)
        btn_save.pack(pady=40)

    def update_settings_avatar(self):
        img = self.get_avatar_image(self.avatar_path, self.profile_name, 120)
        photo = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 120))
        self.settings_avatar_lbl.configure(image=photo)

    def choose_avatar(self):
        file_path = filedialog.askopenfilename(title="Select Avatar", filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if file_path:
            self.avatar_path = file_path
            self.update_settings_avatar()

    def save_profile_ui(self):
        new_name = self.name_entry.get().strip()
        if new_name:
            self.profile_name = new_name
            self.save_profile()
            self.update_sidebar_profile()
            self.update_settings_avatar()
            
            if hasattr(self, 'lbl_greeting_name'):
                self.lbl_greeting_name.configure(text=format_persian(self.profile_name))
                    
            RTLMessageDialog("موفقیت", "تنظیمات با موفقیت ذخیره شد.", yes_no=False)

    def set_active_nav(self, nav_id):
        self.active_nav = nav_id
        for key, btn_dict in self.nav_btns.items():
            if key == nav_id:
                btn_dict['frame'].configure(fg_color=CARD_COLOR)
                btn_dict['text'].configure(text_color=ACCENT_COLOR)
                btn_dict['icon'].configure(text_color=ACCENT_COLOR)
            else:
                btn_dict['frame'].configure(fg_color="transparent")
                btn_dict['text'].configure(text_color=TEXT_COLOR)
                btn_dict['icon'].configure(text_color=TEXT_COLOR)
                
    def show_frame(self, frame_name):
        for frm in self.frames.values(): frm.pack_forget()
        self.frames[frame_name].pack(fill="both", expand=True)

    def show_dashboard(self):
        self.set_active_nav('dashboard')
        self.show_frame('dashboard')

    def show_connect(self):
        self.set_active_nav('connect')
        self.show_frame('connect')

    def show_settings(self):
        self.set_active_nav('settings')
        self.show_frame('settings')

    def toggle_camera(self):
        if self.camera_active: self.stop_camera()
        else: self.start_camera()

    def start_camera(self):
        self.devices_scroll.pack_forget() 
        self.camera_panel.pack(fill="both", expand=True, pady=10)
        self.camera_active = True
        self.cap = cv2.VideoCapture(0)
        
        if not self.cap.isOpened():
            self.camera_label.configure(text=format_persian("خطا: دوربین یافت نشد!"), text_color=ERROR_COLOR)
            return
        self.update_camera_frame()

    def update_camera_frame(self):
        if not self.camera_active or not self.cap: return
        ret, frame = self.cap.read()
        if ret:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                decoded = decode(gray)
                for obj in decoded:
                    data = obj.data.decode('utf-8')
                    if data.startswith("SYNCIP:"):
                        ip = data.split(":")[1]
                        self.stop_camera()
                        self.log(f"بارکد اسکن شد! در حال اتصال به: {ip}")
                        threading.Thread(target=self.initiate_connection, args=(ip,), daemon=True).start()
                        return
            except Exception: pass 
            
            cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(cv2image)
            img.thumbnail((400, 300))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.camera_label.configure(image=ctk_img, text="")
            
        if self.camera_active:
            self.after(30, self.update_camera_frame)

    def stop_camera(self):
        self.camera_active = False
        if self.cap and self.cap.isOpened(): self.cap.release()
        self.camera_panel.pack_forget()
        self.devices_scroll.pack(fill="both", expand=True)

    def get_local_ips(self):
        ips = []
        try:
            for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
                if not ip.startswith("127."): ips.append(ip)
        except: pass
        return ips

    def log(self, message):
        self.log_box.configure(state="normal")
        time_str = datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("0.0", format_persian(f"[{time_str}] {message}\n")) 
        self.log_box.configure(state="disabled")

    def setup_network(self):
        self.tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server.bind(("0.0.0.0", TCP_PORT))
        self.tcp_server.listen(5)
        threading.Thread(target=self.tcp_listen_thread, daemon=True).start()

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.udp_socket.bind(("0.0.0.0", UDP_PORT))
        threading.Thread(target=self.udp_listen_thread, daemon=True).start()

    def start_discovery(self):
        if self.connected: return
        self.log("در حال جستجو در شبکه محلی...")
        
        for widget in self.devices_scroll.winfo_children(): widget.destroy()
        self.discovered_peers.clear()

        def broadcast_worker():
            try:
                payload = json.dumps({"id": self.app_id, "name": self.profile_name}).encode('utf-8')
                msg = MAGIC_WORD + payload
                
                self.udp_socket.sendto(msg, ("<broadcast>", UDP_PORT))
                self.udp_socket.sendto(msg, ("255.255.255.255", UDP_PORT))
                
                for ip in self.get_local_ips():
                    parts = ip.split('.')
                    if len(parts) == 4:
                        parts[3] = '255'
                        try: self.udp_socket.sendto(msg, ('.'.join(parts), UDP_PORT))
                        except: pass
            except: pass
        threading.Thread(target=broadcast_worker, daemon=True).start()

    def udp_listen_thread(self):
        while True:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                if data.startswith(MAGIC_WORD):
                    payload = data[len(MAGIC_WORD):].decode('utf-8')
                    try:
                        info = json.loads(payload)
                        peer_id = info.get("id")
                        peer_name = info.get("name", "ناشناس")
                    except: continue
                    
                    if peer_id != self.app_id and addr[0] not in self.discovered_peers:
                        self.discovered_peers[addr[0]] = {"name": peer_name, "id": peer_id}
                        self.after(0, self.add_device_to_list, addr[0], peer_name)
            except: pass

    def add_device_to_list(self, ip, name):
        card = ctk.CTkFrame(self.devices_scroll, fg_color=SIDEBAR_COLOR, corner_radius=8)
        card.pack(fill="x", pady=5, padx=5)
        
        img = self.generate_default_avatar(name, 44)
        photo = ctk.CTkImage(light_image=img, dark_image=img, size=(44, 44))
        ctk.CTkLabel(card, image=photo, text="").pack(side="right", padx=15, pady=10)
        
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="right", fill="y", pady=10)
        ctk.CTkLabel(info_frame, text=format_persian(name), font=ctk.CTkFont(family=FONT_MAIN, size=15, weight="bold")).pack(anchor="e")
        ctk.CTkLabel(info_frame, text=ip, font=ctk.CTkFont(family=FONT_NUM, size=12), text_color="#94A3B8").pack(anchor="e")
        
        btn_conn = ctk.CTkButton(card, text=format_persian("اتصال"), font=ctk.CTkFont(family=FONT_MAIN, size=13), width=70, height=32,
                                 fg_color=ACCENT_COLOR, text_color=BG_COLOR, hover_color="#7DD3FC",
                                 command=lambda target_ip=ip: threading.Thread(target=self.initiate_connection, args=(target_ip,), daemon=True).start())
        btn_conn.pack(side="left", padx=20)

    def manual_connect(self):
        if self.connected: return
        target_ip = self.ip_entry.get().strip()
        if not target_ip: return
        self.log(f"تلاش برای اتصال دستی به {target_ip}...")
        threading.Thread(target=self.initiate_connection, args=(target_ip,), daemon=True).start()

    def tcp_listen_thread(self):
        while True:
            try:
                conn, addr = self.tcp_server.accept()
                if not self.connected:
                    msg = conn.recv(1024)
                    if msg == b'PAIR_REQ':
                        threading.Thread(target=self.handle_pairing, args=(conn, addr[0]), daemon=True).start()
                    else: conn.close()
                else: conn.close()
            except: pass

    def initiate_connection(self, ip):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, TCP_PORT))
            sock.settimeout(None)
            sock.sendall(b'PAIR_REQ')
            self.handle_pairing(sock, ip)
        except Exception as e:
            self.after(0, self.log, f"خطا در اتصال به {ip}")

    def handle_pairing(self, sock, ip):
        user_response = [None]
        peer_name_in_dict = self.discovered_peers.get(ip, {}).get("name", ip)
        
        def ask_user():
            # Use custom dialog for correct rendering
            dialog = RTLMessageDialog("درخواست اتصال", f"آیا مایل هستید به «{peer_name_in_dict}» متصل شوید؟", yes_no=True)
            user_response[0] = b'YES' if dialog.result else b'NO'
            
        self.after(0, ask_user)
        
        while user_response[0] is None: time.sleep(0.2)
        
        try:
            sock.sendall(user_response[0])
            peer_response = sock.recv(1024)
            if user_response[0] == b'YES' and peer_response == b'YES':
                self.connect_success(sock, ip)
            else:
                self.after(0, self.log, "اتصال لغو شد.")
                sock.close()
        except: 
            sock.close()

    def connect_success(self, sock, ip):
        if self.connected: return
        self.peer_socket = sock
        self.connected = True
        
        self.after(0, self.dash_status_icon.configure, {"text_color": SUCCESS_COLOR})
        self.after(0, self.dash_status_lbl.configure, {"text": format_persian("متصل شد")})
        
        # Show disconnect button
        self.after(0, lambda: self.btn_disconnect.pack(pady=(15, 0)))
        
        self.after(0, self.btn_discover.configure, {"state": "disabled"})
        self.after(0, self.btn_manual.configure, {"state": "disabled"})
        self.after(0, self.log, "✅ اتصال برقرار شد! تبادل پروفایل...")
        self.after(0, self.show_dashboard) 
        
        threading.Thread(target=self.send_full_profile, daemon=True).start()
        threading.Thread(target=self.receive_data_thread, args=(sock,), daemon=True).start()

    def disconnect_peer(self):
        if self.connected:
            self.handle_disconnect()
            self.log("اتصال توسط شما قطع شد.")

    def handle_disconnect(self):
        if self.connected:
            self.connected = False
            if self.peer_socket:
                try: self.peer_socket.close()
                except: pass
            self.peer_socket = None
            
            self.after(0, self.dash_status_icon.configure, {"text_color": ERROR_COLOR})
            self.after(0, self.dash_status_lbl.configure, {"text": format_persian("عدم اتصال")})
            
            # Hide disconnect button
            self.after(0, self.btn_disconnect.pack_forget)
            
            self.after(0, self.dash_peer_lbl.configure, {"text": "---"})
            self.after(0, self.btn_discover.configure, {"state": "normal"})
            self.after(0, self.btn_manual.configure, {"state": "normal"})
            self.after(0, self.log, "ارتباط قطع شد.")

    def send_full_profile(self):
        try:
            profile_data = {"name": self.profile_name}
            if self.avatar_path and os.path.exists(self.avatar_path):
                import base64
                with open(self.avatar_path, "rb") as f:
                    profile_data["avatar_b64"] = base64.b64encode(f.read()).decode('utf-8')
            json_str = json.dumps(profile_data)
            self._send_data_packet(TYPE_PROFILE, json_str.encode('utf-8'))
        except: pass

    def process_profile_data(self, data):
        try:
            profile_data = json.loads(data.decode('utf-8'))
            self.peer_profile_name = profile_data.get("name", "ناشناس")
            self.after(0, self.dash_peer_lbl.configure, {"text": format_persian(self.peer_profile_name)})
            self.after(0, self.log, f"آماده تبادل فایل با {self.peer_profile_name}")
        except: pass

    def receive_data_thread(self, conn):
        while self.connected:
            try:
                header = self.recvall(conn, 9)
                if not header: break
                data_type, size = struct.unpack('>BQ', header)
                if size > 0:
                    data = self.recvall(conn, size)
                    if data:
                        if data_type == TYPE_PROFILE: self.process_profile_data(data)
                        else: self.process_received_data(data_type, data)
            except: break
        self.handle_disconnect()

    def recvall(self, sock, n):
        data = bytearray()
        while len(data) < n:
            packet = sock.recv(min(n - len(data), 65536))
            if not packet: return None
            data.extend(packet)
        return data

    def process_received_data(self, data_type, data):
        self.ignore_next_clipboard = True 
        try:
            if data_type == TYPE_TEXT:
                self.set_clipboard_text(data.decode('utf-8'))
                self.after(0, self.log, "📄 متن دریافت و در کلیپ‌بورد کپی شد.")
            elif data_type == TYPE_IMAGE:
                self.set_clipboard_image(data)
                self.after(0, self.log, "🖼️ تصویر دریافت و در کلیپ‌بورد کپی شد.")
            elif data_type == TYPE_FILES:
                self.extract_and_set_files(data)
                self.after(0, self.log, "📁 فایل دریافت شد. آماده Paste در پوشه دلخواه.")
            self.last_seq_num = win32clipboard.GetClipboardSequenceNumber()
        except: pass
        finally: self.ignore_next_clipboard = False

    def monitor_clipboard_loop(self):
        try: self.last_seq_num = win32clipboard.GetClipboardSequenceNumber()
        except: pass
        while True:
            time.sleep(1)
            if not self.connected: continue
            try:
                current_seq = win32clipboard.GetClipboardSequenceNumber()
                if current_seq != self.last_seq_num:
                    self.last_seq_num = current_seq
                    if self.ignore_next_clipboard:
                        self.ignore_next_clipboard = False
                        continue
                    self.check_and_send_clipboard()
            except: pass

    def check_and_send_clipboard(self):
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                paths = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                win32clipboard.CloseClipboard()
                self.send_files(paths)
                return
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB) or win32clipboard.IsClipboardFormatAvailable(win32con.CF_BITMAP):
                win32clipboard.CloseClipboard() 
                img = ImageGrab.grabclipboard()
                if isinstance(img, Image.Image): self.send_image(img)
                return
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                self.send_text(text)
                return
            win32clipboard.CloseClipboard()
        except: pass

    def _send_data_packet(self, data_type, data):
        try:
            header = struct.pack('>BQ', data_type, len(data))
            self.peer_socket.sendall(header + data)
        except: self.handle_disconnect()

    def send_text(self, text):
        self.after(0, self.log, "ارسال متن...")
        self._send_data_packet(TYPE_TEXT, text.encode('utf-8'))

    def send_image(self, img):
        self.after(0, self.log, "ارسال تصویر...")
        img_byte_arr = io.BytesIO()
        img.convert("RGB").save(img_byte_arr, format='PNG')
        self._send_data_packet(TYPE_IMAGE, img_byte_arr.getvalue())

    def send_files(self, paths):
        self.after(0, self.log, "در حال فشرده‌سازی و ارسال فایل...")
        def _task():
            memory_file = io.BytesIO()
            with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                for path in paths:
                    if os.path.isfile(path): zf.write(path, os.path.basename(path))
                    elif os.path.isdir(path):
                        for root, dirs, files in os.walk(path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                zf.write(file_path, os.path.relpath(file_path, os.path.dirname(path)))
            self._send_data_packet(TYPE_FILES, memory_file.getvalue())
            self.after(0, self.log, "ارسال فایل با موفقیت انجام شد.")
        threading.Thread(target=_task, daemon=True).start()

    def set_clipboard_text(self, text):
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()

    def set_clipboard_image(self, image_data):
        img = Image.open(io.BytesIO(image_data))
        output = io.BytesIO()
        img.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:] 
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, data)
        win32clipboard.CloseClipboard()

    def extract_and_set_files(self, zip_data):
        save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "SyncThings", datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(save_dir, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zf:
            zf.extractall(save_dir)
        paths = [os.path.abspath(os.path.join(save_dir, n)) for n in os.listdir(save_dir)]
        stc_dropfiles = struct.pack("5I", struct.calcsize("5I"), 0, 0, 0, 1) 
        data = stc_dropfiles + ("\0".join(paths) + "\0\0").encode('utf-16le')
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_HDROP, data)
        win32clipboard.CloseClipboard()

if __name__ == "__main__":
    app = SyncThingsApp()
    app.mainloop()