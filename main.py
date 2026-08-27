import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import config
import utils
import profile
import scanner
import clipboard
import network
import uuid
import json
import os
import webbrowser
import logging
from PIL import Image
from datetime import datetime

# Load the custom fonts portably before any UI elements are created
font_path_fa = utils.resource_path(os.path.join("Fonts", "Vazirmatn-Regular.ttf"))
if os.path.exists(font_path_fa):
    ctk.FontManager.load_font(font_path_fa)

font_path_en = utils.resource_path(os.path.join("Fonts", "Hubot-Sans-Regular.ttf"))
if os.path.exists(font_path_en):
    ctk.FontManager.load_font(font_path_en)

font_path_mono = utils.resource_path(os.path.join("Fonts", "JetBrainsMono-Regular.ttf"))
if os.path.exists(font_path_mono):
    ctk.FontManager.load_font(font_path_mono)

class RTLMessageDialog(ctk.CTkToplevel):
    def __init__(self, master, title, text, on_yes, on_no):
        super().__init__(master)
        self.title(title)
        self.geometry("350x150")
        self.resizable(False, False)

        # Set App Icon
        icon_path = utils.resource_path("app.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
                import ctypes
                self.after(200, lambda: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f'mycompany.syncthings.v2.{master.app_id}'))
            except Exception as e:
                print(f"Failed to set dialog icon: {e}")

        # Make modal
        self.transient(master)
        self.grab_set()

        # Center on screen
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() // 2) - (350 // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (150 // 2)
        self.geometry(f"+{x}+{y}")

        self.on_yes = on_yes
        self.on_no = on_no

        # Dark/Light aware background
        bg_color = master.cget("fg_color")
        self.configure(fg_color=bg_color)

        # Label
        is_fa = getattr(master, 'lang', 'en') == 'fa'
        # Add RLM (‏) for Persian to ensure trailing punctuation is rendered correctly
        display_text = "‫" + utils.format_persian(text) + "‬" if is_fa else text

        self.lbl = ctk.CTkLabel(
            self,
            text=display_text,
            font=master.get_main_font(15, "bold") if hasattr(master, 'get_main_font') else (config.FONT_EN, 15, "bold"),
            wraplength=310,
            justify="right" if is_fa else "left"
        )
        self.lbl.pack(pady=20, padx=20, fill="both", expand=True)

        # Buttons frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)

        yes_btn = ctk.CTkButton(btn_frame, text=utils.format_persian(master.tr("yes", default="Yes")), font=master.get_main_font(15, "bold") if hasattr(master, 'get_main_font') else (config.FONT_EN, 15, "bold"), width=100,
                               fg_color=config.COLORS["SUCCESS"][master._get_appearance_mode() == "Light" and 0 or 1],
                               command=self._yes)
        yes_btn.pack(side="left", padx=20)

        no_btn = ctk.CTkButton(btn_frame, text=utils.format_persian(master.tr("no", default="No")), font=master.get_main_font(15, "bold") if hasattr(master, 'get_main_font') else (config.FONT_EN, 15, "bold"), width=100,
                               fg_color=config.COLORS["ERROR"][master._get_appearance_mode() == "Light" and 0 or 1],
                               command=self._no)
        no_btn.pack(side="right", padx=20)

        self.protocol("WM_DELETE_WINDOW", self._no)

    def _yes(self):
        self.destroy()
        if self.on_yes:
            self.on_yes()

    def _no(self):
        self.destroy()
        if self.on_no:
            self.on_no()

class SyncThingsApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Basic Setup
        self.title("Syncthings")
        self.geometry("1000x700")
        self.minsize(900, 600)
        self.state("zoomed")  # Force maximized mode
        self.after(200, lambda: self.state("zoomed")) # Ensure it applies

        # State
        self.app_id = str(uuid.uuid4())
        self.default_name = f"User_{self.app_id[:6]}"
        self.profile_name, self.avatar_path, self.avatar_b64, self.appearance_mode, self.lang, self.window_state, self.enable_size_limit, self.max_file_size_mb, self.enable_ext_limit, self.ext_mode, self.target_extensions = profile.load_profile(self.default_name)

        # Set App Icon
        icon_path = utils.resource_path("app.ico")
        if os.path.exists(icon_path):
            try:
                # Set icon for the window title bar
                self.iconbitmap(icon_path)

                # Force Windows to show this icon in the taskbar when running from Python directly
                import ctypes
                myappid = f'mycompany.syncthings.v2.{self.app_id}' # arbitrary string
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception as e:
                print(f"Failed to set icon: {e}")
        ctk.set_appearance_mode(self.appearance_mode)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Managers
        self.clipboard_manager = clipboard.ClipboardManager()
        self.network_manager = network.NetworkManager(
            self.app_id,
            callbacks={
                "on_peer_discovered": self.on_peer_discovered,
                "on_connection_request": self.on_connection_request,
                "on_connection_success": self.on_connection_success,
                "on_data_received": self.on_data_received,
                "on_error": self.on_network_error,
                "on_progress": lambda c, t: self._update_progress(c, t, "Receiving"),
                "on_peer_disconnected": self.on_peer_disconnected,
                "on_control_event": self.on_control_event
            }
        )
        self.network_manager.update_profile_name(self.profile_name, self.avatar_b64)

        # Handle Double Launch Error by catching OSError on network start
        try:
            self.network_manager.start_network()
        except OSError:
            import sys
            from tkinter import messagebox
            # Hide the main window since we are aborting
            self.withdraw()
            messagebox.showerror("Error", "Another instance of Sync/things is already running or ports are blocked.\n\nPlease close the other instance and try again.")
            sys.exit(1)

        self.discovered_peers = {} # ip -> {"name": name, "avatar": b64, "id": id}

        # UI Structure
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Load Icons
        self._load_icons()

        self.setup_sidebar()
        self.setup_main_area()

        # QR Scanner
        self.qr_scanner = scanner.QRScanner(on_qr_scanned=self.on_qr_scanned)

        # Initial Hotkey for browser sync
        try:
            import keyboard
            self._current_browser_hotkey = "ctrl+shift+b"
            keyboard.add_hotkey(self._current_browser_hotkey, self.trigger_browser_sync, suppress=True)
        except Exception:
            self._current_browser_hotkey = None
            
        # Start Discovery
        self.network_manager.start_discovery()

    def _load_icons(self):
        try:
            from PIL import Image
            import os
            def get_icon(name):
                # Dark icons for light theme, light icons for dark theme
                return ctk.CTkImage(
                    light_image=Image.open(utils.resource_path(os.path.join("Icons", f"{name}_dark.png"))),
                    dark_image=Image.open(utils.resource_path(os.path.join("Icons", f"{name}_light.png"))),
                    size=(24, 24)
                )

            self.icon_dash = get_icon("dash")
            self.icon_connect = get_icon("connect")
            self.icon_settings = get_icon("settings")
            self.icon_github = get_icon("github")
            self.icon_scan = get_icon("scan")
            self.icon_plug = get_icon("plug")
            self.icon_rand = get_icon("rand")
            self.icon_upload = get_icon("upload")

            self.icon_disconnect = get_icon("disconnect")
            self.icon_refresh = get_icon("refresh")
            self.icon_firewall = get_icon("firewall")
            self.icon_lan = get_icon("lan")
            self.icon_link = get_icon("link")
            self.icon_trash = get_icon("trash")
            self.icon_play = get_icon("play")
            self.icon_pause = get_icon("pause")
            self.icon_cancel = get_icon("cancel")

            self._icons_loaded = True
        except Exception as e:
            import logging
            logging.error(f"Failed to load icons: {e}")
            self._icons_loaded = False

    def get_main_font(self, size, weight="normal"):
        return (config.FONT_EN if self.lang == "en" else config.FONT_FA, size, weight)

    def tr(self, key, default=None):
        return config.TRANSLATIONS[self.lang].get(key, default or key)

    def setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, corner_radius=0, width=250)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        # App Title
        self.title_lbl = ctk.CTkLabel(self.sidebar_frame, text="SyncThings", font=self.get_main_font(24, "bold"))
        self.title_lbl.grid(row=0, column=0, padx=20, pady=(30, 20))

        # Navigation
        self.nav_dash = ctk.CTkButton(self.sidebar_frame, text="Dashboard", font=self.get_main_font(15, "bold"),
                                      image=self.icon_dash if self._icons_loaded else None, compound="left", anchor="w",
                                      command=lambda: self.show_frame("dashboard"))
        self.nav_dash.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.nav_connect = ctk.CTkButton(self.sidebar_frame, text="Search & Connect", font=self.get_main_font(15, "bold"),
                                         image=self.icon_connect if self._icons_loaded else None, compound="left", anchor="w",
                                         command=lambda: self.show_frame("connect"))
        self.nav_connect.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.nav_settings = ctk.CTkButton(self.sidebar_frame, text="Settings", font=self.get_main_font(15, "bold"),
                                          image=self.icon_settings if self._icons_loaded else None, compound="left", anchor="w",
                                          command=lambda: self.show_frame("settings"))
        self.nav_settings.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        self.nav_browser = ctk.CTkButton(self.sidebar_frame, text="Browser Sync", font=self.get_main_font(15, "bold"),
                                         compound="left", anchor="w",
                                         command=lambda: self.show_frame("browser_sync"))
        self.nav_browser.grid(row=4, column=0, padx=20, pady=10, sticky="ew")

        # GitHub Button
        self.btn_github = ctk.CTkButton(self.sidebar_frame, text="GitHub", font=self.get_main_font(14, "bold"),
                                        image=self.icon_github if self._icons_loaded else None, compound="left",
                                        fg_color=config.COLORS["MUTED"], hover_color=config.COLORS["CARD"][1],
                                        command=lambda: __import__('webbrowser').open("https://github.com/AmirMoYousefVand/SyncThings.git"))
        self.btn_github.grid(row=4, column=0, padx=20, pady=(10, 0), sticky="s")

        # Bottom controls (Lang / Theme)
        self.bottom_controls = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.bottom_controls.grid(row=5, column=0, padx=20, pady=20, sticky="ew")

        self.lang_btn = ctk.CTkSwitch(self.bottom_controls, text="EN/FA", width=60, command=self.toggle_lang)
        self.lang_btn.pack(side="left", padx=5)

        self.theme_btn = ctk.CTkSwitch(self.bottom_controls, text="Light/Dark", width=60, command=self.toggle_theme)
        self.theme_btn.pack(side="right", padx=5)

        self.update_sidebar_text()

    def setup_main_area(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # Frames
        self.frames = {}

        # 1. Dashboard Frame
        self.frames["dashboard"] = self.create_dashboard_frame()

        # 2. Connect Frame
        self.frames["connect"] = self.create_connect_frame()

        # 3. Settings Frame
        self.frames["settings"] = self.create_settings_frame()

        # 4. Browser Sync Frame
        self.frames["browser_sync"] = self.create_browser_sync_frame()

        # Show default
        self.show_frame("dashboard")

    def update_browser_ui_text(self):
        self.lbl_browser_title.configure(text=utils.format_persian(self.tr("browser_sync", default="Browser Sync")), font=self.get_main_font(28, "bold"))
        self.btn_capture.configure(text=utils.format_persian(self.tr("capture_browser", default="Capture Current Browser Now")), font=self.get_main_font(16, "bold"))
        if hasattr(self, 'lbl_hotkey'):
            self.lbl_hotkey.configure(text=utils.format_persian(self.tr("set_hotkey", default="Set Hotkey (e.g., Ctrl+Shift+B):")))

    def update_browser_hotkey(self):
        hotkey = self.hotkey_entry.get()
        if not hotkey:
            return
        
        try:
            import keyboard
            # Remove previous if exists
            if hasattr(self, '_current_browser_hotkey') and self._current_browser_hotkey:
                keyboard.remove_hotkey(self._current_browser_hotkey)
            
            keyboard.add_hotkey(hotkey, self.trigger_browser_sync, suppress=True)
            self._current_browser_hotkey = hotkey
            self.log(f"Browser sync hotkey set to: {hotkey}")
        except Exception as e:
            self.log(f"Failed to set hotkey: {e}")

    def trigger_browser_sync(self):
        if not self.network_manager.connected_peer_ip:
            self.log("Cannot capture browser: Not connected to any device.")
            return

        self.log("Triggering browser capture in background...")
        import threading
        threading.Thread(target=self._capture_browser_thread, daemon=True).start()

    def _capture_browser_thread(self):
        try:
            import uiautomation as auto
            import requests
            import os

            self.log("Searching for active browser window...")
            url = None

            browser = auto.WindowControl(ClassName='Chrome_WidgetWin_1') # Works for Chrome/Edge
            if not browser.Exists(0, 0):
                browser = auto.WindowControl(ClassName='MozillaWindowClass') # Firefox

            if not browser.Exists(0, 0):
                self.log("Browser not found.")
                return

            # Simple heuristic: try to find an EditControl that might be the address bar
            # Or Name="Address and search bar"
            try:
                addr_bar = browser.EditControl(Name="Address and search bar")
                if not addr_bar.Exists(0, 0):
                    addr_bar = browser.EditControl(Name="Search or enter web address")
                if not addr_bar.Exists(0, 0):
                    addr_bar = browser.EditControl() # Just any edit control as fallback
                if addr_bar.Exists(0, 0):
                    url = addr_bar.GetValuePattern().Value
            except:
                pass

            if not url:
                self.log("Could not find a valid URL in active browser.")
                return

            if not url.startswith("http"):
                url = "https://" + url

            self.log(f"Capturing URL: {url}")

            try:
                resp = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})

                # Check if it's a login page or not accessible
                if resp.status_code == 200 and "login" not in url.lower():
                    html_content = resp.text
                else:
                    raise Exception(f"Status code {resp.status_code} or login page")
            except Exception as e:
                self.log(f"Failed to download HTML via requests: {e}. Trying fallback method...")
                try:
                    # Fallback: Extract text from browser tree
                    doc = browser.DocumentControl()
                    if doc.Exists(0, 0):
                        text = doc.Name
                    else:
                        text = "Failed to extract text from document."

                    html_content = f"<html><body style='font-family: sans-serif; padding: 40px; font-size: 16px;'><h1>Captured from {url}</h1><pre>{text}</pre></body></html>"
                except Exception as ex:
                    self.log(f"Fallback method failed: {ex}")
                    html_content = f"<html><body style='font-family: sans-serif; padding: 20px;'><a href='{url}'>{url}</a><br><br>Failed to capture page content.</body></html>"

            temp_file = os.path.join(os.environ.get("TEMP", "."), "browser_sync_capture.html")
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(html_content)

            self.network_manager.send_file_packet(config.TYPE_BROWSER_SYNC, temp_file)
            self.log(self.tr("browser_captured", default="Browser captured and sent."))

        except Exception as e:
            self.log(f"Browser capture error: {e}")


    def create_dashboard_frame(self):
        frame = ctk.CTkFrame(self.main_container)
        frame.grid_columnconfigure(0, weight=1)

        self.lbl_dash_title = ctk.CTkLabel(frame, text=utils.format_persian(self.tr("dashboard", default="Dashboard")), font=self.get_main_font(28, "bold"))
        self.lbl_dash_title.pack(pady=20)

        # Status Card
        self.status_card = ctk.CTkFrame(frame, corner_radius=15, fg_color=config.COLORS["CARD"])
        self.status_card.pack(fill="x", padx=40, pady=10)

        self.lbl_status = ctk.CTkLabel(self.status_card, text=utils.format_persian(self.tr("disconnected", default="Disconnected")), font=self.get_main_font(18, "bold"), text_color=config.COLORS["ERROR"][1])
        self.lbl_status.pack(pady=(15, 5))

        self.lbl_ip = ctk.CTkLabel(self.status_card, text=f"{utils.format_persian(self.tr('your_ip', default='Your IP:'))} {self.get_primary_ip()}", font=self.get_main_font(14, "bold"))
        self.lbl_ip.pack(pady=(0, 10))

        self.btn_disconnect = ctk.CTkButton(self.status_card, text=utils.format_persian(self.tr("disconnect", default="Disconnect")), font=self.get_main_font(15, "bold"),
                                            image=self.icon_disconnect if getattr(self, '_icons_loaded', False) else None, compound="left",
                                            fg_color=config.COLORS["ERROR"], hover_color="#B91C1C", command=self.disconnect)
        self.btn_disconnect.pack(pady=(0, 15))
        self.btn_disconnect.pack_forget() # Hide initially

        # Activity Log Card
        self.log_card = ctk.CTkFrame(frame, corner_radius=15, fg_color=config.COLORS["CARD"])
        self.log_card.pack(fill="both", expand=True, padx=40, pady=10)

        self.lbl_log_title = ctk.CTkLabel(self.log_card, text=utils.format_persian(self.tr("event_history", default="Event History")), font=self.get_main_font(18, "bold"))
        self.lbl_log_title.pack(anchor="w", padx=20, pady=(20, 5))

        self.log_box = ctk.CTkTextbox(self.log_card, height=300, fg_color="transparent", font=("JetBrains Mono", 13))
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 5))
        self.log_box.configure(state="disabled")

        # Progress Stats
        self.progress_stats_frame = ctk.CTkFrame(self.log_card, fg_color="transparent")
        self.progress_stats_frame.pack(fill="x", padx=20, pady=(0, 5))
        self.progress_stats_frame.pack_forget()

        self.lbl_progress_pct = ctk.CTkLabel(self.progress_stats_frame, text="0% - Transferring...", font=("JetBrains Mono", 12))
        self.lbl_progress_pct.pack(side="left")

        # Controls for Pause/Cancel
        self.transfer_controls_frame = ctk.CTkFrame(self.progress_stats_frame, fg_color="transparent")
        self.transfer_controls_frame.pack(side="left", padx=15)

        self.btn_pause_resume = ctk.CTkButton(self.transfer_controls_frame, text="", width=24, height=24, border_width=0, image=self.icon_pause if getattr(self, '_icons_loaded', False) else None, fg_color="transparent", hover_color="gray25", command=self.toggle_pause_transfer)
        self.btn_pause_resume.pack(side="left", padx=2)

        self.btn_cancel = ctk.CTkButton(self.transfer_controls_frame, text="", width=24, height=24, border_width=0, image=self.icon_cancel if getattr(self, '_icons_loaded', False) else None, fg_color="transparent", hover_color="gray25", command=self.cancel_transfer)
        self.btn_cancel.pack(side="left", padx=2)

        self.lbl_progress_time = ctk.CTkLabel(self.progress_stats_frame, text="Elapsed: 00:00 | Remaining: --:--", font=("JetBrains Mono", 12), text_color="gray")
        self.lbl_progress_time.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(self.log_card, mode="determinate", fg_color=config.COLORS["BG"][1], progress_color=config.COLORS["ACCENT"][1])
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 20))
        self.progress_bar.pack_forget()

        return frame

    def disconnect(self):
        self.network_manager.disconnect(send_signal=True)
        self.lbl_status.configure(text=utils.format_persian(self.tr("disconnected")), text_color=config.COLORS["ERROR"][1])
        self.btn_disconnect.pack_forget()
        self.log(config.TRANSLATIONS["en"]["disconnected_by_you"])
        # Resume discovery immediately
        self.refresh_discovery()

    def create_connect_frame(self):
        frame = ctk.CTkFrame(self.main_container)

        self.lbl_conn_title = ctk.CTkLabel(frame, text=utils.format_persian(self.tr("connect_to_devices", default="Connect to Devices")), font=self.get_main_font(28, "bold"))
        self.lbl_conn_title.pack(pady=20)

        # Top area: QR Code generation & scanning
        qr_main_frame = ctk.CTkFrame(frame, fg_color="transparent")
        qr_main_frame.pack(fill="x", padx=40, pady=10)
        qr_main_frame.grid_columnconfigure(0, weight=1)
        qr_main_frame.grid_columnconfigure(1, weight=1)

        # 1. My QR Code display
        self.my_qr_card = ctk.CTkFrame(qr_main_frame, corner_radius=15, fg_color=config.COLORS["CARD"])
        self.my_qr_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.lbl_my_qr = ctk.CTkLabel(self.my_qr_card, text=utils.format_persian(self.tr("my_qr", default="My QR Code")), font=self.get_main_font(16, "bold"))
        self.lbl_my_qr.pack(pady=(10, 5))

        self.lbl_my_qr_image = ctk.CTkLabel(self.my_qr_card, text="")
        self.lbl_my_qr_image.pack(pady=(5, 10))
        self.generate_and_display_qr()

        # 2. QR Code scanning
        qr_scan_card = ctk.CTkFrame(qr_main_frame, corner_radius=15, fg_color=config.COLORS["CARD"])
        qr_scan_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self.btn_scan = ctk.CTkButton(qr_scan_card, text=utils.format_persian(self.tr("scan_qr", default="Scan QR Code")), font=self.get_main_font(15, "bold"),
                                      image=self.icon_scan if getattr(self, '_icons_loaded', False) else None, compound="left",
                                      command=self.toggle_qr_scanner)
        self.btn_scan.pack(pady=10)

        self.cam_lbl = ctk.CTkLabel(qr_scan_card, text="")
        self.cam_lbl.pack(pady=10)
        self.cam_lbl.pack_forget() # Hide initially

        # Manual / Auto Connect area
        conn_area = ctk.CTkFrame(frame, corner_radius=15, fg_color=config.COLORS["CARD"])
        conn_area.pack(fill="both", expand=True, padx=40, pady=10)

        # Header with Search button side by side
        search_header_frame = ctk.CTkFrame(conn_area, fg_color="transparent")
        search_header_frame.pack(fill="x", padx=20, pady=10)

        self.lbl_found = ctk.CTkLabel(search_header_frame, text=utils.format_persian(self.tr("devices_found", default="Devices found on network:")), font=self.get_main_font(16, "bold"))
        self.lbl_found.pack(side="left")

        self.btn_refresh = ctk.CTkButton(search_header_frame, text=utils.format_persian(self.tr("search_network", default="Search Network")), width=120, font=self.get_main_font(15, "bold"),
                                         image=self.icon_refresh if getattr(self, '_icons_loaded', False) else None, compound="left",
                                         fg_color=config.COLORS["ACCENT"], command=self.refresh_discovery)
        self.btn_refresh.pack(side="right")

        self.peer_list_frame = ctk.CTkScrollableFrame(conn_area, fg_color="transparent")
        self.peer_list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        manual_frame = ctk.CTkFrame(conn_area, fg_color="transparent")
        manual_frame.pack(fill="x", padx=20, pady=(0, 20))

        self.ip_entry = ctk.CTkEntry(manual_frame, placeholder_text=utils.format_persian(self.tr("enter_ip", default="Enter IP Address")))
        self.ip_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_manual_conn = ctk.CTkButton(manual_frame, text=utils.format_persian(self.tr("connect", default="Connect")), font=self.get_main_font(15, "bold"),
                                             image=self.icon_link if getattr(self, '_icons_loaded', False) else None, compound="left",
                                             command=self.manual_connect)
        self.btn_manual_conn.pack(side="right")

        return frame

    def create_browser_sync_frame(self):
        frame = ctk.CTkFrame(self.main_container)
        frame.grid_columnconfigure(0, weight=1)

        self.lbl_browser_title = ctk.CTkLabel(frame, text=utils.format_persian(self.tr("browser_sync", default="Browser Sync")), font=self.get_main_font(28, "bold"))
        self.lbl_browser_title.pack(pady=20)

        instructions = ctk.CTkLabel(frame, text=utils.format_persian(self.tr("browser_sync_instructions", default="This feature captures the currently open webpage in your browser and sends it to the connected device.")), font=self.get_main_font(14), wraplength=400)
        instructions.pack(pady=10)

        hotkey_frame = ctk.CTkFrame(frame, fg_color="transparent")
        hotkey_frame.pack(pady=20)
        
        lbl_hotkey = ctk.CTkLabel(hotkey_frame, text=utils.format_persian(self.tr("set_hotkey", default="Set Hotkey (e.g., Ctrl+Shift+B):")), font=self.get_main_font(14))
        lbl_hotkey.pack(side="left", padx=10)
        
        self.hotkey_entry = ctk.CTkEntry(hotkey_frame, width=150, font=self.get_main_font(14))
        self.hotkey_entry.insert(0, "Ctrl+Shift+B")
        self.hotkey_entry.pack(side="left")
        
        self.btn_set_hotkey = ctk.CTkButton(hotkey_frame, text=utils.format_persian(self.tr("ok", default="OK")), width=60, font=self.get_main_font(14), command=self.update_browser_hotkey)
        self.btn_set_hotkey.pack(side="left", padx=10)

        self.btn_capture = ctk.CTkButton(frame, text=utils.format_persian(self.tr("capture_browser", default="Capture Current Browser Now")), font=self.get_main_font(16, "bold"),
                                         command=self.trigger_browser_sync)
        self.btn_capture.pack(pady=30)
        
        return frame

    def create_settings_frame(self):
        frame = ctk.CTkScrollableFrame(self.main_container)

        self.lbl_set_title = ctk.CTkLabel(frame, text=utils.format_persian(self.tr("profile_settings", default="Profile Settings")), font=self.get_main_font(28, "bold"))
        self.lbl_set_title.pack(pady=20)

        # Inner frame to hold all settings content and ensure correct sizing in ScrollableFrame
        content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True)

        # Display current avatar
        self.avatar_display_lbl = ctk.CTkLabel(content_frame, text="")
        self.avatar_display_lbl.pack(pady=(10, 10))
        self.refresh_avatar_display()

        # Avatar buttons
        btn_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        btn_frame.pack(pady=(0, 20))

        self.btn_rand_avatar = ctk.CTkButton(btn_frame, text=utils.format_persian(self.tr("random_avatar", default="Generate Random Avatar")), font=self.get_main_font(15, "bold"),
                                             image=self.icon_rand if getattr(self, '_icons_loaded', False) else None, compound="left",
                                             command=self.generate_random_avatar_ui)
        self.btn_rand_avatar.pack(side="left", padx=10)

        self.btn_upload_avatar = ctk.CTkButton(btn_frame, text=utils.format_persian(self.tr("upload_avatar", default="Upload Image")), font=self.get_main_font(15, "bold"),
                                               image=self.icon_upload if getattr(self, '_icons_loaded', False) else None, compound="left",
                                               command=self.upload_avatar_ui)
        self.btn_upload_avatar.pack(side="left", padx=10)

        self.name_entry = ctk.CTkEntry(content_frame, placeholder_text=utils.format_persian(self.tr("display_name", default="Display Name")))
        self.name_entry.insert(0, self.profile_name)
        self.name_entry.pack(pady=20, padx=40, fill="x")

        # File Restrictions Frame
        restrictions_frame = ctk.CTkFrame(content_frame, fg_color=config.COLORS["CARD"], corner_radius=15)
        restrictions_frame.pack(pady=10, padx=40, fill="x")

        self.lbl_restrictions_title = ctk.CTkLabel(restrictions_frame, text=utils.format_persian(self.tr("file_restrictions", default="File Restrictions")), font=self.get_main_font(16, "bold"))
        self.lbl_restrictions_title.pack(anchor="w", padx=15, pady=(15, 5))

        # Size Limit Frame
        size_frame = ctk.CTkFrame(restrictions_frame, fg_color="transparent")
        size_frame.pack(fill="x", padx=15, pady=5)

        self.switch_size = ctk.CTkSwitch(size_frame, text=utils.format_persian(self.tr("enable_size_limit", default="Enable Size Limit")), font=self.get_main_font(14), command=self.toggle_restrictions)
        self.switch_size.grid(row=0, column=0, sticky="w", pady=5)
        if getattr(self, "enable_size_limit", False):
            self.switch_size.select()

        self.lbl_size = ctk.CTkLabel(size_frame, text=utils.format_persian(self.tr("max_file_size_mb", default="Max File Size (MB):")), font=self.get_main_font(14))
        self.lbl_size.grid(row=0, column=1, sticky="w", padx=10, pady=5)

        self.size_entry = ctk.CTkEntry(size_frame, width=100)
        self.size_entry.grid(row=0, column=2, sticky="w", padx=10, pady=5)
        self.size_entry.insert(0, str(getattr(self, "max_file_size_mb", 100)))
        self.size_entry.bind("<KeyRelease>", lambda event: self.save_settings())

        # Extension Limit Frame
        ext_frame = ctk.CTkFrame(restrictions_frame, fg_color="transparent")
        ext_frame.pack(fill="x", padx=15, pady=(5, 15))

        self.switch_ext = ctk.CTkSwitch(ext_frame, text=utils.format_persian(self.tr("enable_ext_limit", default="Enable Extension Limit")), font=self.get_main_font(14), command=self.toggle_restrictions)
        self.switch_ext.grid(row=0, column=0, sticky="w", pady=5)
        if getattr(self, "enable_ext_limit", False):
            self.switch_ext.select()

        mode_options = [
            "Include (فقط اینها)" if self.lang == 'fa' else "Include",
            "Exclude (به‌جز اینها)" if self.lang == 'fa' else "Exclude"
        ]
        self.ext_mode_combo = ctk.CTkComboBox(ext_frame, values=mode_options, width=160, command=lambda _: self.save_settings())
        self.ext_mode_combo.grid(row=0, column=1, sticky="w", padx=10, pady=5)

        current_mode = getattr(self, 'ext_mode', 'exclude')
        if current_mode == 'include':
            self.ext_mode_combo.set(mode_options[0])
        else:
            self.ext_mode_combo.set(mode_options[1])

        self.ext_entry = ctk.CTkEntry(ext_frame, width=250, placeholder_text="e.g. mp4, mkv, exe")
        self.ext_entry.grid(row=0, column=2, sticky="w", padx=10, pady=5)
        self.ext_entry.insert(0, getattr(self, "target_extensions", ""))
        self.ext_entry.bind("<KeyRelease>", lambda event: self.save_settings())

        self.toggle_restrictions()

        self.btn_save_settings = ctk.CTkButton(content_frame, text="Save Changes", font=self.get_main_font(15, "bold"), command=self.save_settings)
        self.btn_save_settings.pack(pady=20)

        self.btn_fix_firewall = ctk.CTkButton(content_frame, text=utils.format_persian(self.tr("fix_firewall", default="Grant Firewall permission")),
                                              font=self.get_main_font(15, "bold"), fg_color=config.COLORS["WARNING"], hover_color="#D97706",
                                              image=self.icon_firewall if getattr(self, '_icons_loaded', False) else None, compound="left",
                                              command=self.fix_firewall_ui)
        self.btn_fix_firewall.pack(pady=(30, 10))

        self.btn_setup_lan = ctk.CTkButton(content_frame, text=utils.format_persian(self.tr("setup_lan_ip", default="Setup Direct LAN IP")),
                                           font=self.get_main_font(15, "bold"), fg_color=config.COLORS["ACCENT"], hover_color="#0284C7",
                                           image=self.icon_lan if getattr(self, '_icons_loaded', False) else None, compound="left",
                                           command=self.setup_lan_ui)
        self.btn_setup_lan.pack(pady=(10, 10))

        self.btn_clear_cache = ctk.CTkButton(content_frame, text=utils.format_persian(self.tr("clear_cache", default="Clear Cache")),
                                             font=self.get_main_font(15, "bold"), fg_color=config.COLORS["MUTED"], hover_color=config.COLORS["CARD"][1],
                                             image=self.icon_trash if getattr(self, '_icons_loaded', False) else None, compound="left",
                                             command=self.clear_cache_ui)
        self.btn_clear_cache.pack(pady=(10, 30))

        return frame

    def toggle_restrictions(self):
        if hasattr(self, "switch_size"):
            if self.switch_size.get() == 1:
                self.size_entry.configure(state="normal")
            else:
                self.size_entry.configure(state="disabled")
        if hasattr(self, "switch_ext"):
            if self.switch_ext.get() == 1:
                self.ext_mode_combo.configure(state="normal")
                self.ext_entry.configure(state="normal")
            else:
                self.ext_mode_combo.configure(state="disabled")
                self.ext_entry.configure(state="disabled")
        self.save_settings()

    def clear_cache_ui(self):
        import utils
        success = utils.clear_temp_cache()
        if success:
            self.log("Cache cleared successfully.")
            RTLMessageDialog(self, self.tr("success", default="Success"), self.tr("cache_cleared"), on_yes=lambda: None, on_no=lambda: None)
        else:
            self.log("Failed to clear some cache files.")

    def setup_lan_ui(self):
        import utils
        success, message = utils.setup_direct_lan_ip()
        if success:
            self.log(f"LAN IP Setup: {message}")
            RTLMessageDialog(self, self.tr("success", default="Success"), self.tr("lan_ip_success"), on_yes=lambda: None, on_no=lambda: None)
            self.after(2000, lambda: self.lbl_ip.configure(text=f"{utils.format_persian(self.tr('your_ip'))} {self.get_primary_ip()}"))
        else:
            self.log(f"Failed to setup LAN IP: {message}")
            RTLMessageDialog(self, "Error", self.tr("lan_ip_fail"), on_yes=lambda: None, on_no=lambda: None)

    def fix_firewall_ui(self):
        import utils
        success = utils.fix_windows_firewall()
        if success:
            self.log("Firewall rules added successfully!")
            RTLMessageDialog(self, "Success", "Firewall rules updated. You might need to restart the app.", on_yes=lambda: None, on_no=lambda: None)
        else:
            self.log("Failed to add firewall rules. Admin privileges required.")

    def refresh_avatar_display(self):
        img = profile.get_avatar_image(self.avatar_path, self.avatar_b64, self.profile_name, size=120)
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 120))
        self.avatar_display_lbl.configure(image=ctk_img)
        self.avatar_display_lbl.image = ctk_img

    def generate_random_avatar_ui(self):
        import profile
        self.avatar_b64, mini_b64 = profile.generate_random_avatar()
        self.avatar_path = None
        self.refresh_avatar_display()
        self.save_settings()

    def upload_avatar_ui(self):
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title=self.tr("select_image", default="Select Profile Image"),
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")]
        )
        if file_path:
            import profile
            try:
                # Open, center crop, and encode
                img = Image.open(file_path).convert("RGBA")
                width, height = img.size
                min_dim = min(width, height)

                # Center crop calculation
                left = (width - min_dim) / 2
                top = (height - min_dim) / 2
                right = (width + min_dim) / 2
                bottom = (height + min_dim) / 2

                img_cropped = img.crop((left, top, right, bottom))

                # Main avatar
                main_img = img_cropped.resize((200, 200), Image.Resampling.LANCZOS)
                import io, base64
                main_out = io.BytesIO()
                main_img.save(main_out, format="PNG")
                self.avatar_b64 = base64.b64encode(main_out.getvalue()).decode('utf-8')

                # Mini avatar
                mini_img = img_cropped.resize((50, 50), Image.Resampling.LANCZOS)
                mini_out = io.BytesIO()
                mini_img.save(mini_out, format="PNG")
                mini_b64 = base64.b64encode(mini_out.getvalue()).decode('utf-8')

                self.avatar_path = None

                # Save manually here so mini gets updated correctly
                profile.save_profile(self.profile_name, None, self.avatar_b64, mini_b64)
                self.refresh_avatar_display()
                self.network_manager.update_profile_name(self.profile_name, self.avatar_b64)
            except Exception as e:
                self.log(f"Error uploading image: {e}")

    def show_frame(self, name):
        for f in self.frames.values():
            f.grid_forget()
        self.frames[name].grid(row=0, column=0, sticky="nsew")

    def log(self, msg):
        logging.info(msg)
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.after(0, lambda: self._update_log_ui(timestamp, msg))

    def _update_log_ui(self, timestamp, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{timestamp} {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def toggle_theme(self):
        if self.appearance_mode == "Dark":
            self.appearance_mode = "Light"
        else:
            self.appearance_mode = "Dark"
        ctk.set_appearance_mode(self.appearance_mode)
        import profile
        try:
            current_state = "zoomed" if self.state() == "zoomed" else "normal"
            profile.save_profile(self.profile_name, self.avatar_path, self.avatar_b64, None, self.appearance_mode, self.lang, current_state, self.enable_size_limit, self.max_file_size_mb, self.enable_ext_limit, self.ext_mode, self.target_extensions)
        except:
            pass

    def toggle_lang(self):
        if self.lang == "en":
            self.lang = "fa"
        else:
            self.lang = "en"
        self.update_sidebar_text()
        self.update_ui_text()
        import profile
        try:
            current_state = "zoomed" if self.state() == "zoomed" else "normal"
            profile.save_profile(self.profile_name, self.avatar_path, self.avatar_b64, None, self.appearance_mode, self.lang, current_state, self.enable_size_limit, self.max_file_size_mb, self.enable_ext_limit, self.ext_mode, self.target_extensions)
        except:
            pass

    def update_sidebar_text(self):
        self.nav_dash.configure(text=utils.format_persian(self.tr("dashboard")))
        self.nav_connect.configure(text=utils.format_persian(self.tr("search_and_connect")))
        self.nav_settings.configure(text=utils.format_persian(self.tr("profile_settings")))
        self.nav_browser.configure(text=utils.format_persian(self.tr("browser_sync", default="Browser Sync")))
        # Update fonts in sidebar
        self.title_lbl.configure(font=self.get_main_font(24, "bold"))
        self.nav_dash.configure(font=self.get_main_font(15, "bold"))
        self.nav_connect.configure(font=self.get_main_font(15, "bold"))
        self.nav_settings.configure(font=self.get_main_font(15, "bold"))
        self.nav_browser.configure(font=self.get_main_font(15, "bold"))
        if hasattr(self, 'btn_github'):
            self.btn_github.configure(font=self.get_main_font(14, "bold"))

    def update_ui_text(self):
        self.lbl_browser_title.configure(text=utils.format_persian(self.tr("browser_sync", default="Browser Sync")), font=self.get_main_font(28, "bold"))
        self.btn_capture.configure(text=utils.format_persian(self.tr("capture_browser", default="Capture Current Browser Now")), font=self.get_main_font(16, "bold"))
        self.lbl_dash_title.configure(text=utils.format_persian(self.tr("dashboard")), font=self.get_main_font(28, "bold"))
        self.lbl_log_title.configure(text=utils.format_persian(self.tr("event_history")), font=self.get_main_font(18, "bold"))

        self.lbl_conn_title.configure(text=utils.format_persian(self.tr("search_and_connect")), font=self.get_main_font(28, "bold"))
        self.btn_scan.configure(text=utils.format_persian(self.tr("scan_qr")), font=self.get_main_font(15, "bold"))
        self.lbl_my_qr.configure(text=utils.format_persian(self.tr("my_qr")), font=self.get_main_font(16, "bold"))
        self.lbl_found.configure(text=utils.format_persian(self.tr("devices_found")), font=self.get_main_font(16, "bold"))
        self.btn_refresh.configure(text=utils.format_persian(self.tr("search_network")), font=self.get_main_font(15, "bold"))
        self.btn_manual_conn.configure(text=utils.format_persian(self.tr("connect")), font=self.get_main_font(15, "bold"))
        if hasattr(self, 'ip_entry'):
            self.ip_entry.configure(placeholder_text=utils.format_persian(self.tr("enter_ip", default="Enter IP Address")))

        self.lbl_set_title.configure(text=utils.format_persian(self.tr("profile_settings")), font=self.get_main_font(28, "bold"))
        self.btn_save_settings.configure(text=utils.format_persian(self.tr("save_changes")), font=self.get_main_font(15, "bold"))
        if hasattr(self, 'btn_rand_avatar'):
             self.btn_rand_avatar.configure(text=utils.format_persian(self.tr("random_avatar", default="Generate Random Avatar")), font=self.get_main_font(15, "bold"))
        if hasattr(self, 'btn_upload_avatar'):
             self.btn_upload_avatar.configure(text=utils.format_persian(self.tr("upload_avatar", default="Upload Image")), font=self.get_main_font(15, "bold"))
        if hasattr(self, 'btn_fix_firewall'):
             self.btn_fix_firewall.configure(text=utils.format_persian(self.tr("fix_firewall", default="Grant Firewall permission")), font=self.get_main_font(15, "bold"))
        if hasattr(self, 'btn_setup_lan'):
             self.btn_setup_lan.configure(text=utils.format_persian(self.tr("setup_lan_ip", default="Setup Direct LAN IP")), font=self.get_main_font(15, "bold"))
        if hasattr(self, 'btn_clear_cache'):
             self.btn_clear_cache.configure(text=utils.format_persian(self.tr("clear_cache", default="Clear Cache")), font=self.get_main_font(15, "bold"))
        if hasattr(self, 'name_entry'):
             self.name_entry.configure(placeholder_text=utils.format_persian(self.tr("display_name", default="Display Name")))
        if hasattr(self, 'lbl_restrictions_title'):
             self.lbl_restrictions_title.configure(text=utils.format_persian(self.tr("file_restrictions", default="File Restrictions")), font=self.get_main_font(16, "bold"))
        if hasattr(self, 'switch_size'):
             self.switch_size.configure(text=utils.format_persian(self.tr("enable_size_limit", default="Enable Size Limit")), font=self.get_main_font(14))
        if hasattr(self, 'switch_ext'):
             self.switch_ext.configure(text=utils.format_persian(self.tr("enable_ext_limit", default="Enable Extension Limit")), font=self.get_main_font(14))
        if hasattr(self, 'lbl_size'):
             self.lbl_size.configure(text=utils.format_persian(self.tr("max_file_size_mb", default="Max File Size (MB):")), font=self.get_main_font(14))
        if hasattr(self, 'lbl_ext'):
             self.lbl_ext.configure(text=utils.format_persian(self.tr("allowed_extensions", default="Allowed Extensions (comma-separated):")), font=self.get_main_font(14))

        if self.network_manager.connected:
            self.lbl_status.configure(text=utils.format_persian(self.tr("connected")), font=self.get_main_font(18, "bold"))
        else:
            self.lbl_status.configure(text=utils.format_persian(self.tr("disconnected")), font=self.get_main_font(18, "bold"))

        self.lbl_ip.configure(text=f"{utils.format_persian(self.tr('your_ip', default='Your IP:'))} {self.get_primary_ip()}", font=self.get_main_font(14, "bold"))
        self.btn_disconnect.configure(text=utils.format_persian(self.tr("disconnect", default="Disconnect")), font=self.get_main_font(15, "bold"))

    def generate_and_display_qr(self):
        ip = self.get_primary_ip()
        if ip:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=5, border=2)
            qr.add_data(f"SYNCIP:{ip}")
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img = img.get_image() # Convert from qrcode PilImage to actual PIL.Image.Image

            # Convert to CTkImage
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(150, 150))
            self.lbl_my_qr_image.configure(image=ctk_img)
            self.lbl_my_qr_image.image = ctk_img

    def get_primary_ip(self):
        ips = utils.get_local_ips()
        if not ips:
            return "127.0.0.1"

        # Prioritize the Direct LAN IP if it exists
        for ip, _ in ips:
            if ip.startswith("192.168.137."):
                return ip

        # Fallback to the first available IP
        return ips[0][0]

    def save_settings(self):
        new_name = self.name_entry.get().strip()
        if new_name:
            self.profile_name = new_name
            if hasattr(self, "switch_size"):
                self.enable_size_limit = self.switch_size.get() == 1
            if hasattr(self, "switch_ext"):
                self.enable_ext_limit = self.switch_ext.get() == 1
                self.ext_mode = 'include' if getattr(self, "ext_mode_combo", None) and self.ext_mode_combo.get().startswith('Include') else 'exclude'
            try:
                if hasattr(self, "size_entry"):
                    self.max_file_size_mb = int(self.size_entry.get().strip())
            except ValueError:
                self.max_file_size_mb = 100
            
            if hasattr(self, "ext_entry"):
                self.target_extensions = self.ext_entry.get().strip()

            profile.save_profile(self.profile_name, self.avatar_path, self.avatar_b64, None, self.appearance_mode, self.lang, self.window_state, getattr(self, "enable_size_limit", False), getattr(self, "max_file_size_mb", 100), getattr(self, "enable_ext_limit", False), getattr(self, "ext_mode", "exclude"), getattr(self, "target_extensions", ""))
            self.network_manager.update_profile_name(self.profile_name, self.avatar_b64)
            self.log(config.TRANSLATIONS["en"]["settings_saved"])

    def manual_connect(self):
        ip = self.ip_entry.get().strip()
        if ip:
            self.log(config.TRANSLATIONS["en"]["manual_connect_attempt"].format(ip))
            import threading
            threading.Thread(target=self.network_manager.initiate_connection, args=(ip,), daemon=True).start()

    def refresh_discovery(self):
        # Clear existing peers
        self.discovered_peers.clear()
        for widget in self.peer_list_frame.winfo_children():
            widget.destroy()

        self.network_manager.stop_discovery()
        import time
        time.sleep(0.1)
        self.network_manager.start_discovery()
        self.log(config.TRANSLATIONS["en"]["searching_network"])

    # QR Scanner
    def toggle_qr_scanner(self):
        if not self.qr_scanner.is_active:
            if self.qr_scanner.start():
                self.btn_scan.configure(text=utils.format_persian(self.tr("close_camera")))
                self.cam_lbl.pack(pady=10)
                self.update_camera()
            else:
                self.log(config.TRANSLATIONS["en"]["camera_error"])
        else:
            self.qr_scanner.stop()
            self.btn_scan.configure(text=utils.format_persian(self.tr("scan_qr")))
            self.cam_lbl.pack_forget()

    def update_camera(self):
        if self.qr_scanner.is_active:
            img = self.qr_scanner.read_frame()
            if img:
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(320, 240))
                self.cam_lbl.configure(image=ctk_img)
                self.cam_lbl.image = ctk_img
            self.after(30, self.update_camera)
        else:
            self.cam_lbl.pack_forget()

    def on_qr_scanned(self, ip):
        self.btn_scan.configure(text=utils.format_persian(self.tr("scan_qr")))
        self.cam_lbl.pack_forget()
        self.log(config.TRANSLATIONS["en"]["qr_scanned"].format(ip))
        self.ip_entry.delete(0, "end")
        self.ip_entry.insert(0, ip)
        self.manual_connect()

    # Network Callbacks
    def on_peer_discovered(self, ip, name, peer_id, avatar_mini=""):
        # Key by peer_id instead of IP to avoid duplicates when connected to both Wi-Fi and LAN
        if peer_id not in self.discovered_peers:
            self.discovered_peers[peer_id] = {"name": name, "avatar": avatar_mini, "ip": ip}
            self.after(0, self.update_peer_list, peer_id)
        else:
            # Update info
            peer = self.discovered_peers[peer_id]
            needs_update = False

            # Prioritize LAN IP (192.168.137.x) if a new packet comes in with it
            if ip.startswith("192.168.137.") and not peer["ip"].startswith("192.168.137."):
                peer["ip"] = ip
                needs_update = True

            if peer.get("avatar") != avatar_mini or peer.get("name") != name:
                peer["avatar"] = avatar_mini
                peer["name"] = name
                needs_update = True

            if needs_update:
                self.after(0, self.update_peer_list, peer_id)

    def update_peer_list(self, peer_id):
        if peer_id not in self.discovered_peers:
            return

        peer = self.discovered_peers[peer_id]
        ip = peer["ip"]
        name = peer["name"]
        avatar_mini = peer["avatar"]

        # Check if row already exists, if so destroy it
        for widget in self.peer_list_frame.winfo_children():
            if hasattr(widget, '_peer_id') and widget._peer_id == peer_id:
                widget.destroy()

        row = ctk.CTkFrame(self.peer_list_frame, fg_color="transparent")
        row._peer_id = peer_id
        row.pack(fill="x", pady=5)

        if avatar_mini:
            try:
                import io
                import base64
                image_data = base64.b64decode(avatar_mini)
                img = Image.open(io.BytesIO(image_data))
                img = img.resize((36, 36), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(36, 36))
                avatar_lbl = ctk.CTkLabel(row, image=ctk_img, text="")
                avatar_lbl.image = ctk_img
                avatar_lbl.pack(side="left", padx=(0, 10))
            except Exception as e:
                pass

        # Text Frame for Name and IP
        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)

        lbl_name = ctk.CTkLabel(text_frame, text=utils.format_persian(name), font=self.get_main_font(15, "bold"))
        lbl_name.pack(anchor="w")

        lbl_ip = ctk.CTkLabel(text_frame, text=ip, font=self.get_main_font(12), text_color="gray")
        lbl_ip.pack(anchor="w")

        btn = ctk.CTkButton(row, text=utils.format_persian(self.tr("connect")), font=self.get_main_font(15, "bold"), width=80, fg_color=config.COLORS["SUCCESS"], hover_color="#059669",
                           command=lambda i=ip, n=name: self._trigger_connect(i, n))
        btn.pack(side="right", padx=10)

    def _trigger_connect(self, ip, name):
        import threading
        threading.Thread(target=self.network_manager.initiate_connection, args=(ip, name), daemon=True).start()

    def on_connection_request(self, ip, peer_name="Unknown"):
        # We now get the actual peer name from the TCP pairing packet!
        if peer_name == "Unknown" or not peer_name:
            peer_info = self.discovered_peers.get(ip, {})
            peer_name = peer_info.get("name", self.tr("unknown", default="Unknown")) if isinstance(peer_info, dict) else peer_info
        if not isinstance(peer_name, str):
             peer_name = self.tr("unknown", default="Unknown")

        result = [False]
        dialog_done = [False]

        def _yes():
            result[0] = True
            dialog_done[0] = True

        def _no():
            result[0] = False
            dialog_done[0] = True

        def _show_dialog():
            RTLMessageDialog(
                self,
                self.tr("connection_request", default="Connection Request"),
                self.tr("do_you_want_to_connect", default="Do you want to connect to «{}»?").format(peer_name),
                _yes,
                _no
            )

        self.after(0, _show_dialog)

        # Block until dialog is done
        while not dialog_done[0]:
            self.update()

        return result[0]

    def on_connection_success(self, ip, peer_name="Unknown"):
        self.after(0, self._handle_connection_success, ip, peer_name)

    def _handle_connection_success(self, ip, peer_name="Unknown"):
        if peer_name == "Unknown" or not peer_name:
            peer_info = self.discovered_peers.get(ip, {})
            peer_name = peer_info.get("name", self.tr("unknown", default="Unknown")) if isinstance(peer_info, dict) else peer_info
        if not isinstance(peer_name, str):
             peer_name = self.tr("unknown", default="Unknown")

        self.lbl_status.configure(text=utils.format_persian(self.tr("connected") + f": {peer_name}"), text_color=config.COLORS["SUCCESS"][1])
        self.btn_disconnect.pack(pady=(0, 15)) # Show the disconnect button
        self.log(config.TRANSLATIONS["en"]["connected_ready"])

        # Start clipboard monitor
        self.clipboard_manager.start_monitoring(self.on_clipboard_change)

        # Exchange profile info
        profile_data = {
            "name": self.profile_name,
            "avatar_b64": self.avatar_b64
        }
        self.network_manager.send_data_packet(config.TYPE_PROFILE, json.dumps(profile_data).encode("utf-8"))

    def on_network_error(self, err_msg):
        self.after(0, self._handle_network_error, err_msg)

    def on_peer_disconnected(self):
        self.after(0, self._handle_peer_disconnected)

    def _handle_peer_disconnected(self):
        self.log(config.TRANSLATIONS["en"]["connection_lost"])
        self.lbl_status.configure(text=utils.format_persian(self.tr("disconnected")), text_color=config.COLORS["ERROR"][1])
        self.btn_disconnect.pack_forget()
        self.clipboard_manager.stop_monitoring()
        self.refresh_discovery()

    def _handle_network_error(self, err_msg):
        self.log(f"Error: {err_msg}")
        self.lbl_status.configure(text=utils.format_persian(self.tr("disconnected")), text_color=config.COLORS["ERROR"][1])
        self.clipboard_manager.stop_monitoring()

    def _update_progress_simple(self, current, total):
        if total > 0:
            percentage = current / total
            self.after(0, self._set_progress_simple, percentage)

    def _set_progress_simple(self, percentage):
        if percentage < 1.0:
            if not self.progress_bar.winfo_viewable():
                self.progress_bar.pack(pady=10)
            self.progress_bar.set(percentage)
        else:
            self.progress_bar.set(1.0)
            # hide after short delay
            self.after(500, self.progress_bar.pack_forget)

    # Clipboard Monitor Callback
    def on_clipboard_change(self, dtype, data):
        if not self.network_manager.connected:
            return

        if dtype == "text":
            logging.info("Clipboard change detected: Text")
            self.log(config.TRANSLATIONS["en"]["sending_text"])
            self.network_manager.send_data_packet(config.TYPE_TEXT, data.encode("utf-8"), progress_callback=lambda c, t: self._update_progress(c, t, "Sending"))
        elif dtype == "image":
            logging.info("Clipboard change detected: Image")
            self.log(config.TRANSLATIONS["en"]["sending_image"])
            import io
            out = io.BytesIO()
            data.convert("RGB").save(out, format="JPEG")
            self.network_manager.send_data_packet(config.TYPE_IMAGE, out.getvalue(), progress_callback=lambda c, t: self._update_progress(c, t, "Sending"))
        elif dtype == "files":
            logging.info(f"Clipboard change detected: Files. Starting background thread for processing...")
            import threading
            threading.Thread(target=self._process_and_send_files, args=(data,), daemon=True).start()

    def _process_and_send_files(self, data):
        try:
            import zipfile
            import io
            import tempfile
            import config
            import utils
            import os
            from pathlib import Path

            # Apply restrictions if enabled
            check_size = getattr(self, 'enable_size_limit', False)
            max_size_bytes = (getattr(self, "max_file_size_mb", 100) or 100) * 1024 * 1024
            check_ext = getattr(self, 'enable_ext_limit', False)
            ext_mode = getattr(self, 'ext_mode', 'exclude')
            target_exts = [ext.strip().lower() for ext in (getattr(self, 'target_extensions', '') or "").split(',') if ext.strip()]
            target_exts = [ext.lstrip('.') for ext in target_exts]

            def is_file_allowed(filepath):
                if check_size and os.path.getsize(filepath) > max_size_bytes:
                    self.log(f"Skipped {os.path.basename(filepath)}: exceeds size limit.")
                    return False
                ext = Path(filepath).suffix.lower().strip('.')
                if check_ext and target_exts:
                    if ext_mode == "include" and ext not in target_exts:
                        self.log(f"Skipped {os.path.basename(filepath)}: extension not allowed.")
                        return False
                    if ext_mode == "exclude" and ext in target_exts:
                        self.log(f"Skipped {os.path.basename(filepath)}: extension is blocked.")
                        return False
                return True

            # Pre-calculate total size
            total_bytes = 0
            files_to_zip = []
            skipped_files = 0

            for path in data:
                if os.path.isfile(path):
                    if is_file_allowed(path):
                        size = os.path.getsize(path)
                        total_bytes += size
                        files_to_zip.append((path, os.path.basename(path), size))
                    else:
                        skipped_files += 1
                elif os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            if is_file_allowed(file_path):
                                size = os.path.getsize(file_path)
                                total_bytes += size
                                arcname = os.path.relpath(file_path, os.path.dirname(path))
                                files_to_zip.append((file_path, arcname, size))
                            else:
                                skipped_files += 1

            if len(files_to_zip) == 0:
                self.log("Transfer aborted: No valid files to send.")
                self.after(0, lambda: RTLMessageDialog(
                    self,
                    self.tr("error", default="Error"),
                    self.tr("no_valid_files", default="No valid files to send. They may have been blocked by your size or extension limits."),
                    on_yes=lambda: None,
                    on_no=lambda: None
                ))
                return

            if skipped_files > 0:
                self.log(f"{skipped_files} files were skipped due to restrictions.")

            # Direct transfer optimization for a single file
            if len(files_to_zip) == 1 and os.path.isfile(files_to_zip[0][0]):
                single_file_path = files_to_zip[0][0]
                self.log(f"{config.TRANSLATIONS['en']['sending_file']} (Direct single file, {total_bytes / 1048576:.2f} MB)")
                logging.info(f"Bypassing zip for single file: {single_file_path}")

                self.after(0, lambda: self.progress_bar.configure(progress_color=config.COLORS["ACCENT"][self._get_appearance_mode() == "Light" and 0 or 1]))

                # Send a metadata packet first so receiver knows the filename
                metadata = json.dumps({"filename": files_to_zip[0][1]}).encode('utf-8')
                self.network_manager.send_data_packet(config.TYPE_SINGLE_FILE_META, metadata)

                # Send the actual file data directly
                success = self.network_manager.send_file_packet(config.TYPE_SINGLE_FILE, single_file_path, progress_callback=lambda c, t: self._update_progress(c, t, "Sending"))

                if success:
                    self.log(config.TRANSLATIONS["en"]["file_sent_success"])
                    logging.info("Network transfer completed successfully (Single File).")
                else:
                    self.log("File transfer failed.")
                    logging.error("Network transfer failed.")
                return

            self.log(f"{config.TRANSLATIONS['en']['sending_file']} ({len(files_to_zip)} files, {total_bytes / 1048576:.2f} MB)")
            logging.info(f"Starting zip process for {len(files_to_zip)} files ({total_bytes / 1048576:.2f} MB)")

            processed_bytes = 0

            # Set to green for compression
            self.after(0, lambda: self.progress_bar.configure(progress_color=config.COLORS["SUCCESS"][self._get_appearance_mode() == "Light" and 0 or 1]))

            # Write ZIP directly to a temp file on disk instead of BytesIO
            temp_dir = os.path.join(os.path.expanduser("~"), "Downloads", "SyncThings", "Temp")
            os.makedirs(temp_dir, exist_ok=True)
            temp_zip_path = tempfile.mktemp(dir=temp_dir, suffix=".zip")
            logging.info(f"Using temporary zip path: {temp_zip_path}")

            with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
                for file_path, arcname, size in files_to_zip:
                    # Use native write which is heavily optimized rather than slow Python chunk loops
                    zf.write(file_path, arcname)
                    processed_bytes += size
                    if total_bytes > 0:
                        self._update_progress(processed_bytes, total_bytes, "Compressing")

            logging.info(f"Zipping complete. Temp file size: {os.path.getsize(temp_zip_path) / 1048576:.2f} MB. Starting network transfer...")

            # Revert to blue for network transfer
            self.after(0, lambda: self.progress_bar.configure(progress_color=config.COLORS["ACCENT"][self._get_appearance_mode() == "Light" and 0 or 1]))
            success = self.network_manager.send_file_packet(config.TYPE_FILES, temp_zip_path, progress_callback=lambda c, t: self._update_progress(c, t, "Sending"))

            try:
                os.remove(temp_zip_path) # cleanup
                logging.info(f"Cleaned up temp zip file: {temp_zip_path}")
            except Exception as e:
                logging.error(f"Failed to clean up temp zip file: {e}")

            if success:
                self.log(config.TRANSLATIONS["en"]["file_sent_success"])
                logging.info("Network transfer completed successfully.")
            else:
                self.log("File transfer failed.")
                logging.error("Network transfer failed.")
        except Exception as e:
            self.log(f"Error processing files: {e}")
            logging.error(f"Exception in _process_and_send_files: {e}", exc_info=True)

    def toggle_pause_transfer(self):
        if not hasattr(self, '_transfer_paused'):
            self._transfer_paused = False

        self._transfer_paused = not self._transfer_paused
        if self._transfer_paused:
            self.btn_pause_resume.configure(image=self.icon_play if getattr(self, '_icons_loaded', False) else None)
            self.network_manager.pause_transfer()
            self.log("Transfer paused.")
        else:
            self.btn_pause_resume.configure(image=self.icon_pause if getattr(self, '_icons_loaded', False) else None)
            self.network_manager.resume_transfer()
            self.log("Transfer resumed.")

    def on_control_event(self, action):
        # Always execute UI changes in the main thread
        self.after(0, lambda: self._handle_control_event(action))

    def _handle_control_event(self, action):
        if action == "CTRL:PAUSE":
            self._transfer_paused = True
            self.btn_pause_resume.configure(image=self.icon_play if getattr(self, '_icons_loaded', False) else None)
            self.network_manager.pause_event.clear()
            self.log("Transfer paused by peer.")
        elif action == "CTRL:RESUME":
            self._transfer_paused = False
            self.btn_pause_resume.configure(image=self.icon_pause if getattr(self, '_icons_loaded', False) else None)
            self.network_manager.pause_event.set()
            self.log("Transfer resumed by peer.")
        elif action == "CTRL:CANCEL":
            self.network_manager.cancel_event.set()
            self.network_manager.resume_transfer()
            self.log("Transfer cancelled by peer.")
            self._ui_polling_active = False
            self.progress_bar.pack_forget()
            self.progress_stats_frame.pack_forget()
            self._transfer_paused = False
            self.btn_pause_resume.configure(image=self.icon_pause if getattr(self, '_icons_loaded', False) else None)

    def cancel_transfer(self):
        self.network_manager.cancel_transfer()
        self.log("Transfer cancelled by user.")
        self._ui_polling_active = False
        self.progress_bar.pack_forget()
        self.progress_stats_frame.pack_forget()
        # Reset button state
        self._transfer_paused = False
        self.btn_pause_resume.configure(image=self.icon_pause if getattr(self, '_icons_loaded', False) else None)

    def _update_progress(self, current, total, action="Transferring"):
        # This is called from the background network thread.
        # It must NOT call any UI methods or wait for the UI thread.
        self._current_progress_sent = current
        self._current_progress_total = total
        self._current_progress_action = action

        if not hasattr(self, '_ui_polling_active') or not self._ui_polling_active:
            self._ui_polling_active = True
            import time
            self._transfer_start_time = time.time()

            # Reset icon states on new transfer
            if not hasattr(self, '_transfer_paused'):
                self._transfer_paused = False
            self.btn_pause_resume.configure(image=self.icon_pause if getattr(self, '_icons_loaded', False) else None)

            # Start the polling loop safely on the main thread
            self.after(0, self._poll_ui_progress)

    def _poll_ui_progress(self):
        if not hasattr(self, '_ui_polling_active') or not self._ui_polling_active:
            return

        current = getattr(self, '_current_progress_sent', 0)
        total = getattr(self, '_current_progress_total', 1)
        action = getattr(self, '_current_progress_action', "Transferring")

        if total == 0:
            total = 1

        pct = current / total

        if not self.progress_bar.winfo_viewable() and pct < 1.0:
            self.progress_stats_frame.pack(fill="x", padx=20, pady=(0, 5))
            self.progress_bar.pack(fill="x", padx=20, pady=(0, 20))
            self.progress_bar.set(0)

            # Ensure proper icon is shown when a transfer starts
            self.btn_pause_resume.configure(image=self.icon_play if getattr(self, '_transfer_paused', False) else self.icon_pause if getattr(self, '_icons_loaded', False) else None)

        self.progress_bar.set(pct)
        self.lbl_progress_pct.configure(text=f"{int(pct * 100)}% - {action}...")

        import time
        elapsed = time.time() - getattr(self, '_transfer_start_time', time.time())
        if pct > 0:
            total_est = elapsed / pct
            remaining = max(0, total_est - elapsed)

            el_m, el_s = divmod(int(elapsed), 60)
            rem_m, rem_s = divmod(int(remaining), 60)

            speed_mb = (current / 1048576) / elapsed if elapsed > 0 else 0
            self.lbl_progress_time.configure(text=f"Elapsed: {el_m:02d}:{el_s:02d} | Remaining: {rem_m:02d}:{rem_s:02d} | Speed: {speed_mb:.1f} MB/s")

        if current >= total:
            self._ui_polling_active = False
            self.after(1000, self.progress_bar.pack_forget)
            self.after(1000, self.progress_stats_frame.pack_forget)
        else:
            # Poll again in 50ms (20 FPS)
            self.after(50, self._poll_ui_progress)

    # Network Receive Callback
    def on_data_received(self, data_type, data):
        self.after(0, self._handle_data_received, data_type, data)

    def _handle_data_received(self, data_type, data):
        if data_type == config.TYPE_TEXT:
            text = data.decode("utf-8")
            self.clipboard_manager.set_clipboard_text(text)
            self.log(config.TRANSLATIONS["en"]["text_received"])
        elif data_type == config.TYPE_IMAGE:
            self.clipboard_manager.set_clipboard_image(data)
            self.log(config.TRANSLATIONS["en"]["image_received"])
        elif data_type == config.TYPE_FILES:
            # Here 'data' is now the filepath string for the temp zip on disk
            import os
            file_size = os.path.getsize(data)
            self.after(0, lambda: self.progress_bar.configure(progress_color=config.COLORS["SUCCESS"][self._get_appearance_mode() == "Light" and 0 or 1]))
            self.clipboard_manager.extract_and_set_files(data, progress_callback=lambda c, t: self._update_progress(c, t, "Decompressing"))

            try:
                os.remove(data) # clean up the temp streamed zip
            except:
                pass
            
            self.after(500, self._hide_progress)
            self.log(config.TRANSLATIONS["en"]["file_received"])
            
        elif data_type == config.TYPE_BROWSER_SYNC:
            import os
            import webbrowser
            # data is the temp filepath
            self.log("Browser sync content received. Opening in default browser...")
            # We don't want to delete it immediately because the browser needs to read it
            # We will just open it
            try:
                os.startfile(data)
            except AttributeError:
                # Fallback for non-Windows (though this is Windows specific usually)
                webbrowser.open('file://' + os.path.realpath(data))
            except Exception as e:
                self.log(f"Failed to open browser sync file: {e}")
                
            self.after(500, self._hide_progress)

            self.log(f"{config.TRANSLATIONS['en']['file_received']} ({file_size / 1048576:.2f} MB)")
        elif data_type == config.TYPE_BROWSER_SYNC:
            import os
            try:
                os.startfile(data)
                self.log("Browser sync received and opened in default browser.")
            except Exception as e:
                self.log(f"Failed to open browser sync file: {e}")
        elif data_type == config.TYPE_SINGLE_FILE_META:
            # Metadata packet for single file
            try:
                import json
                meta = json.loads(data.decode('utf-8'))
                self._last_single_filename = meta.get('filename', 'received_file')
            except Exception as e:
                import logging
                logging.error(f"Failed to parse single file metadata: {e}")
                self._last_single_filename = 'received_file'
        elif data_type == config.TYPE_SINGLE_FILE:
            # Single file bypasses zip
            import os
            import tempfile
            import shutil

            file_size = os.path.getsize(data)
            filename = getattr(self, '_last_single_filename', 'received_file')

            # Move it to a named temp file that clipboard can reference
            temp_dir = os.path.join(os.path.expanduser("~"), "Downloads", "SyncThings", "Temp")
            os.makedirs(temp_dir, exist_ok=True)
            final_path = os.path.join(temp_dir, filename)

            try:
                # Clean up old file if it exists
                if os.path.exists(final_path):
                    try:
                        os.remove(final_path)
                    except:
                        pass

                # Use shutil.move instead of os.rename to allow cross-device moves
                shutil.move(data, final_path)

                # Put exactly this file on the clipboard
                self.clipboard_manager.set_clipboard_files([final_path])
                self.log(f"{config.TRANSLATIONS['en']['file_received']} ({file_size / 1048576:.2f} MB)")
            except Exception as e:
                logging.error(f"Failed to process single file receive: {e}")
        elif data_type == config.TYPE_PROFILE:
            try:
                import json
                info = json.loads(data.decode("utf-8"))
                peer_name = info.get("name", self.tr("unknown"))
                self.lbl_status.configure(text=utils.format_persian(self.tr("ready_to_transfer").format(peer_name)))
            except Exception as e:
                logging.error(f"Error parsing profile data: {e}")

    def on_closing(self):
        try:
            self.network_manager.stop_discovery()
            self.network_manager.disconnect()
        except:
            pass
        self.destroy()

if __name__ == '__main__':
    utils.setup_logging()
    app = SyncThingsApp()
    app.mainloop()

