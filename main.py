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
        self.lbl = ctk.CTkLabel(self, text=utils.format_persian(text), font=master.get_main_font(15, "bold") if hasattr(master, 'get_main_font') else (config.FONT_EN, 15, "bold"))
        self.lbl.pack(pady=20, padx=20)

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

        # State
        self.app_id = str(uuid.uuid4())
        self.lang = "en"
        self.appearance_mode = "Dark"
        ctk.set_appearance_mode(self.appearance_mode)

        self.default_name = f"User_{self.app_id[:6]}"
        self.profile_name, self.avatar_path, self.avatar_b64 = profile.load_profile(self.default_name)

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
                "on_progress": self._update_progress
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

        self.setup_sidebar()
        self.setup_main_area()

        # QR Scanner
        self.qr_scanner = scanner.QRScanner(on_qr_scanned=self.on_qr_scanned)

        # Start Discovery
        self.network_manager.start_discovery()

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
        self.nav_dash = ctk.CTkButton(self.sidebar_frame, text="Dashboard", font=self.get_main_font(15, "bold"), command=lambda: self.show_frame("dashboard"))
        self.nav_dash.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.nav_connect = ctk.CTkButton(self.sidebar_frame, text="Search & Connect", font=self.get_main_font(15, "bold"), command=lambda: self.show_frame("connect"))
        self.nav_connect.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.nav_settings = ctk.CTkButton(self.sidebar_frame, text="Settings", font=self.get_main_font(15, "bold"), command=lambda: self.show_frame("settings"))
        self.nav_settings.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        # GitHub Button
        self.btn_github = ctk.CTkButton(self.sidebar_frame, text="GitHub", font=self.get_main_font(14, "bold"),
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

        # Show default
        self.show_frame("dashboard")

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

        self.btn_disconnect = ctk.CTkButton(self.status_card, text=utils.format_persian(self.tr("disconnect", default="Disconnect")), font=self.get_main_font(15, "bold"), fg_color=config.COLORS["ERROR"], hover_color="#B91C1C", command=self.disconnect)
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

        self.lbl_progress_pct = ctk.CTkLabel(self.progress_stats_frame, text="0%", font=("JetBrains Mono", 12))
        self.lbl_progress_pct.pack(side="left")

        self.lbl_progress_time = ctk.CTkLabel(self.progress_stats_frame, text="Elapsed: 00:00 | Remaining: --:--", font=("JetBrains Mono", 12), text_color="gray")
        self.lbl_progress_time.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(self.log_card, mode="determinate", fg_color=config.COLORS["BG"][1], progress_color=config.COLORS["ACCENT"][1])
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 20))
        self.progress_bar.pack_forget()

        return frame

    def disconnect(self):
        self.network_manager.disconnect()
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

        self.btn_scan = ctk.CTkButton(qr_scan_card, text=utils.format_persian(self.tr("scan_qr", default="Scan QR Code")), font=self.get_main_font(15, "bold"), command=self.toggle_qr_scanner)
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

        self.btn_refresh = ctk.CTkButton(search_header_frame, text=utils.format_persian(self.tr("search_network", default="Search Network")), width=120, font=self.get_main_font(15, "bold"), fg_color=config.COLORS["ACCENT"], command=self.refresh_discovery)
        self.btn_refresh.pack(side="right")

        self.peer_list_frame = ctk.CTkScrollableFrame(conn_area, fg_color="transparent")
        self.peer_list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        manual_frame = ctk.CTkFrame(conn_area, fg_color="transparent")
        manual_frame.pack(fill="x", padx=20, pady=(0, 20))

        self.ip_entry = ctk.CTkEntry(manual_frame, placeholder_text=utils.format_persian(self.tr("enter_ip", default="Enter IP Address")))
        self.ip_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_manual_conn = ctk.CTkButton(manual_frame, text=utils.format_persian(self.tr("connect", default="Connect")), font=self.get_main_font(15, "bold"), command=self.manual_connect)
        self.btn_manual_conn.pack(side="right")

        return frame

    def create_settings_frame(self):
        frame = ctk.CTkFrame(self.main_container)

        self.lbl_set_title = ctk.CTkLabel(frame, text=utils.format_persian(self.tr("profile_settings", default="Profile Settings")), font=self.get_main_font(28, "bold"))
        self.lbl_set_title.pack(pady=20)

        # Display current avatar
        self.avatar_display_lbl = ctk.CTkLabel(frame, text="")
        self.avatar_display_lbl.pack(pady=(10, 10))
        self.refresh_avatar_display()

        # Avatar buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=(0, 20))

        self.btn_rand_avatar = ctk.CTkButton(btn_frame, text=utils.format_persian(self.tr("random_avatar", default="Generate Random Avatar")), font=self.get_main_font(15, "bold"), command=self.generate_random_avatar_ui)
        self.btn_rand_avatar.pack(side="left", padx=10)

        self.btn_upload_avatar = ctk.CTkButton(btn_frame, text=utils.format_persian(self.tr("upload_avatar", default="Upload Image")), font=self.get_main_font(15, "bold"), command=self.upload_avatar_ui)
        self.btn_upload_avatar.pack(side="left", padx=10)

        self.name_entry = ctk.CTkEntry(frame, placeholder_text=utils.format_persian(self.tr("display_name", default="Display Name")))
        self.name_entry.insert(0, self.profile_name)
        self.name_entry.pack(pady=20, padx=40, fill="x")

        self.btn_save_settings = ctk.CTkButton(frame, text="Save Changes", font=self.get_main_font(15, "bold"), command=self.save_settings)
        self.btn_save_settings.pack(pady=10)

        self.btn_fix_firewall = ctk.CTkButton(frame, text=utils.format_persian(self.tr("fix_firewall", default="Fix Firewall Issues")),
                                              font=self.get_main_font(15, "bold"), fg_color=config.COLORS["WARNING"], hover_color="#D97706", command=self.fix_firewall_ui)
        self.btn_fix_firewall.pack(pady=(30, 10))

        return frame

    def fix_firewall_ui(self):
        import utils
        success = utils.fix_windows_firewall()
        if success:
            self.log("Firewall rules added successfully!")
            RTLMessageDialog(self, "Success", "Firewall rules updated. You might need to restart the app.", _yes=lambda: None, _no=lambda: None)
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
        timestamp = datetime.now().strftime("[%H:%M:%S]")
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

    def toggle_lang(self):
        if self.lang == "en":
            self.lang = "fa"
        else:
            self.lang = "en"
        self.update_sidebar_text()
        self.update_ui_text()

    def update_sidebar_text(self):
        self.nav_dash.configure(text=utils.format_persian(self.tr("dashboard")))
        self.nav_connect.configure(text=utils.format_persian(self.tr("search_and_connect")))
        self.nav_settings.configure(text=utils.format_persian(self.tr("profile_settings")))
        # Update fonts in sidebar
        self.title_lbl.configure(font=self.get_main_font(24, "bold"))
        self.nav_dash.configure(font=self.get_main_font(15, "bold"))
        self.nav_connect.configure(font=self.get_main_font(15, "bold"))
        self.nav_settings.configure(font=self.get_main_font(15, "bold"))
        if hasattr(self, 'btn_github'):
            self.btn_github.configure(font=self.get_main_font(14, "bold"))

    def update_ui_text(self):
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
             self.btn_fix_firewall.configure(text=utils.format_persian(self.tr("fix_firewall", default="Fix Firewall Issues")), font=self.get_main_font(15, "bold"))
        if hasattr(self, 'name_entry'):
             self.name_entry.configure(placeholder_text=utils.format_persian(self.tr("display_name", default="Display Name")))

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
        return ips[0][0] if ips else "127.0.0.1"

    def save_settings(self):
        new_name = self.name_entry.get().strip()
        if new_name:
            self.profile_name = new_name
            profile.save_profile(self.profile_name, self.avatar_path, self.avatar_b64)
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
        if ip not in self.discovered_peers:
            self.discovered_peers[ip] = {"name": name, "avatar": avatar_mini, "id": peer_id}
            # Update UI safely
            self.after(0, self.update_peer_list, ip, name, avatar_mini)
        else:
            # Avatar may have changed
            if self.discovered_peers[ip].get("avatar") != avatar_mini or self.discovered_peers[ip].get("name") != name:
                self.discovered_peers[ip]["avatar"] = avatar_mini
                self.discovered_peers[ip]["name"] = name
                self.after(0, self.update_peer_list, ip, name, avatar_mini)

    def update_peer_list(self, ip, name, avatar_mini=""):
        # Check if row already exists, if so destroy it
        for widget in self.peer_list_frame.winfo_children():
            if hasattr(widget, '_peer_ip') and widget._peer_ip == ip:
                widget.destroy()

        row = ctk.CTkFrame(self.peer_list_frame, fg_color="transparent")
        row._peer_ip = ip
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

    def _handle_network_error(self, err_msg):
        self.log(f"Error: {err_msg}")
        self.lbl_status.configure(text=utils.format_persian(self.tr("disconnected")), text_color=config.COLORS["ERROR"][1])
        self.clipboard_manager.stop_monitoring()

    def _update_progress(self, current, total):
        if total > 0:
            percentage = current / total
            self.after(0, self._set_progress, percentage)

    def _set_progress(self, percentage):
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
            self.log(config.TRANSLATIONS["en"]["sending_text"])
            self.network_manager.send_data_packet(config.TYPE_TEXT, data.encode("utf-8"), progress_callback=self._update_progress)
        elif dtype == "image":
            self.log(config.TRANSLATIONS["en"]["sending_image"])
            import io
            out = io.BytesIO()
            data.convert("RGB").save(out, format="JPEG")
            self.network_manager.send_data_packet(config.TYPE_IMAGE, out.getvalue(), progress_callback=self._update_progress)
        elif dtype == "files":
            self.log(config.TRANSLATIONS["en"]["sending_file"])
            import zipfile
            import io
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                for path in data:
                    if os.path.isfile(path):
                        zf.write(path, os.path.basename(path))
                    elif os.path.isdir(path):
                        for root, _, files in os.walk(path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, os.path.dirname(path))
                                zf.write(file_path, arcname)
            self.network_manager.send_data_packet(config.TYPE_FILES, out.getvalue(), progress_callback=self._update_progress)
            self.log(config.TRANSLATIONS["en"]["file_sent_success"])

    def _update_progress(self, current, total):
        self.after(0, self._set_progress, current, total)

    def _set_progress(self, current, total):
        if total == 0:
            return
        pct = current / total

        import time
        if not hasattr(self, '_transfer_start_time') or current == 0:
            self._transfer_start_time = time.time()

        if not self.progress_bar.winfo_viewable() and pct < 1.0:
            self.progress_stats_frame.pack(fill="x", padx=20, pady=(0, 5))
            self.progress_bar.pack(fill="x", padx=20, pady=(0, 20))
            self.progress_bar.set(0)

        self.progress_bar.set(pct)
        self.lbl_progress_pct.configure(text=f"{int(pct * 100)}%")

        elapsed = time.time() - self._transfer_start_time
        if pct > 0:
            total_est = elapsed / pct
            remaining = max(0, total_est - elapsed)

            # format MM:SS
            el_m, el_s = divmod(int(elapsed), 60)
            rem_m, rem_s = divmod(int(remaining), 60)
            self.lbl_progress_time.configure(text=f"Elapsed: {el_m:02d}:{el_s:02d} | Remaining: {rem_m:02d}:{rem_s:02d}")

        self.update_idletasks()

        if current >= total:
            # Hide after a small delay
            self.after(1000, self.progress_bar.pack_forget)
            self.after(1000, self.progress_stats_frame.pack_forget)
            if hasattr(self, '_transfer_start_time'):
                del self._transfer_start_time

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
            self.clipboard_manager.extract_and_set_files(data)
            self.log(config.TRANSLATIONS["en"]["file_received"])
        elif data_type == config.TYPE_PROFILE:
            try:
                info = json.loads(data.decode("utf-8"))
                peer_name = info.get("name", self.tr("unknown"))
                self.lbl_status.configure(text=utils.format_persian(self.tr("ready_to_transfer").format(peer_name)))
            except:
                pass

if __name__ == "__main__":
    app = SyncThingsApp()
    app.mainloop()
