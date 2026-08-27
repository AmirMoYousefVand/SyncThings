# config.py
# Constants and configurations for Sync/things

# Modern theme colors - Tuples of (light_hex, dark_hex)
COLORS = {
    "BG": ("#F8FAFC", "#0F172A"),       # Deep slate blue in dark, off-white in light
    "SIDEBAR": ("#F1F5F9", "#1E293B"),  # Lighter slate in dark, light gray in light
    "CARD": ("#FFFFFF", "#334155"),     # Even lighter slate in dark, white in light
    "ACCENT": ("#0EA5E9", "#38BDF8"),   # Bright sky blue
    "TEXT": ("#0F172A", "#F8FAFC"),     # Off-white in dark, slate in light
    "SUCCESS": ("#059669", "#10B981"),  # Emerald green
    "ERROR": ("#DC2626", "#EF4444"),    # Red
    "WARNING": ("#D97706", "#F59E0B"),  # Amber
    "MUTED": ("#64748B", "#94A3B8"),    # Muted text
}

# Network constants
TCP_PORT = 49152
UDP_PORT = 49153
MAGIC_WORD = b"SYNC_THINGS_V2:"

# Data types
TYPE_TEXT = 1
TYPE_IMAGE = 2
TYPE_FILES = 3
TYPE_PROFILE = 4
TYPE_SINGLE_FILE = 5
TYPE_SINGLE_FILE_META = 6
TYPE_DISCONNECT = 9
TYPE_BROWSER_SYNC = 15

# File paths and fonts
CONFIG_FILE = "sync_things_profile.json"
FONT_MAIN = "Vazirmatn"
FONT_EN = "Hubot Sans"
FONT_FA = "Vazirmatn"
FONT_NUM = "Segoe UI"

# Translations for EN/FA support
TRANSLATIONS = {
    "en": {
        "hello": "Hello",
        "to": "to",
        "welcome": "Welcome",
        "system_status": "System Status",
        "disconnected": "Disconnected",
        "connected": "Connected",
        "disconnect": "Disconnect",
        "your_ip": "Your IP Address",
        "connected_device": "Connected Device",
        "event_history": "Event History",
        "connect_to_devices": "Connect to Devices",
        "auto_search": "Auto Search",
        "scan_qr": "Scan QR Code",
        "connect": "Connect",
        "qr_helper_text": "Scan this QR code on the other device to connect quickly",
        "opening_camera": "Opening camera...",
        "close_camera": "Close Camera",
        "devices_found": "Devices found on network:",
        "profile_settings": "Profile Settings",
        "change_avatar": "Change Avatar...",
        "display_name": "Your Display Name:",
        "save_changes": "Save Changes",
        "dashboard": "Dashboard",
        "search_network": "Search Network",
        "my_qr": "My QR Code",
        "search_and_connect": "Search & Connect",
        "random_avatar": "Generate Random Avatar",
        "upload_avatar": "Upload Image",
        "enter_ip": "Enter IP Address",
        "select_image": "Select Profile Image",
        "fix_firewall": "Grant Firewall permission",
        "setup_lan_ip": "Setup Direct LAN IP",
        "lan_ip_success": "Static IP assigned successfully. You can now connect.",
        "lan_ip_fail": "Failed to set IP. Make sure the LAN cable is connected and try again.",
        "clear_cache": "Clear Cache",
        "cache_cleared": "Temporary files cleared successfully.",
        "file_restrictions": "File Restrictions",
        "enable_file_restrictions": "Enable File Restrictions",
        "max_file_size_mb": "Max File Size (MB):",
        "allowed_extensions": "Allowed Extensions (comma-separated):",
        "file_size_exceeded": "File '{}' exceeds maximum allowed size of {} MB.",
        "file_type_blocked": "File type of '{}' is not allowed.",
        "yes": "Yes",
        "no": "No",
        "ok": "OK",
        "unknown": "Unknown",
        "connection_request": "Connection Request",
        "do_you_want_to_connect": "Do you want to connect to «{}»?",
        "success": "Success",
        "settings_saved": "Settings saved successfully.",
        "camera_error": "Error: Camera not found!",
        "qr_scanned": "QR code scanned! Connecting to: {}",
        "searching_network": "Searching local network...",
        "manual_connect_attempt": "Attempting manual connection to {}...",
        "connection_error": "Error connecting to {}",
        "connection_cancelled": "Connection cancelled.",
        "connected_ready": "✅ Connected! Exchanging profiles...",
        "ready_to_transfer": "Ready to transfer files with {}",
        "text_received": "📄 Text received and copied to clipboard.",
        "image_received": "🖼️ Image received and copied to clipboard.",
        "file_received": "📁 File received. Ready to paste in any folder.",
        "disconnected_by_you": "Disconnected by you.",
        "connection_lost": "Connection lost.",
        "sending_text": "Sending text...",
        "sending_image": "Sending image...",
        "sending_file": "Compressing and sending file...",
        "file_sent_success": "File sent successfully.",
        "user_prefix": "User_",
        "browser_sync": "Browser Sync",
        "capture_browser": "Capture Current Browser Now",
        "set_hotkey": "Set Hotkey (e.g., Ctrl+Shift+B)",
        "browser_sync_instructions": "This feature captures the currently open webpage in your browser and sends it to the connected device.",
        "browser_captured": "Browser captured and sent."
    },
    "fa": {
        "hello": "سلام",
        "to": "به",
        "welcome": "خوش آمدید",
        "system_status": "وضعیت سیستم",
        "disconnected": "عدم اتصال",
        "connected": "متصل شد",
        "disconnect": "قطع اتصال",
        "your_ip": "آدرس IP شما",
        "connected_device": "دستگاه متصل",
        "event_history": "تاریخچه رویدادها",
        "connect_to_devices": "اتصال به دستگاه‌ها",
        "auto_search": "جستجوی خودکار",
        "scan_qr": "اسکن بارکد",
        "connect": "اتصال",
        "qr_helper_text": "برای اتصال سریع، این بارکد را در سیستم مقابل اسکن کنید",
        "opening_camera": "در حال باز کردن دوربین...",
        "close_camera": "بستن دوربین",
        "devices_found": "دستگاه‌های پیدا شده در شبکه:",
        "profile_settings": "تنظیمات پروفایل",
        "change_avatar": "تغییر آواتار...",
        "display_name": "نام نمایشی شما:",
        "save_changes": "ذخیره تغییرات",
        "dashboard": "داشبورد",
        "search_network": "جستجوی شبکه",
        "my_qr": "QR کد من",
        "search_and_connect": "جستجو و اتصال",
        "random_avatar": "ساخت آواتار تصادفی",
        "upload_avatar": "آپلود عکس",
        "enter_ip": "آدرس IP را وارد کنید",
        "select_image": "انتخاب تصویر پروفایل",
        "fix_firewall": "اعطای دسترسی فایروال",
        "setup_lan_ip": "تنظیم خودکار IP کابل شبکه",
        "lan_ip_success": "آی‌پی استاتیک با موفقیت تنظیم شد. حالا می‌توانید متصل شوید.",
        "lan_ip_fail": "خطا در تنظیم آی‌پی. مطمئن شوید کابل LAN متصل است.",
        "clear_cache": "پاکسازی حافظه پنهان",
        "cache_cleared": "فایل‌های موقت با موفقیت پاک شدند.",
        "file_restrictions": "محدودیت حجم و نوع فایل",
        "enable_file_restrictions": "فعال سازی محدودیت فایل",
        "max_file_size_mb": "حداکثر حجم فایل (مگابایت):",
        "allowed_extensions": "پسوندهای مجاز (جدا شده با کاما):",
        "file_size_exceeded": "فایل '{}' از حجم مجاز {} مگابایت بیشتر است.",
        "file_type_blocked": "نوع فایل '{}' مجاز نیست.",
        "app_name": "سینک / تینگز",
        "yes": "بله",
        "no": "خیر",
        "ok": "تایید",
        "unknown": "ناشناس",
        "connection_request": "درخواست اتصال",
        "do_you_want_to_connect": "آیا مایل هستید به «{}» متصل شوید؟",
        "success": "موفقیت",
        "settings_saved": "تنظیمات با موفقیت ذخیره شد.",
        "camera_error": "خطا: دوربین یافت نشد!",
        "qr_scanned": "بارکد اسکن شد! در حال اتصال به: {}",
        "searching_network": "در حال جستجو در شبکه محلی...",
        "manual_connect_attempt": "تلاش برای اتصال دستی به {}...",
        "connection_error": "خطا در اتصال به {}",
        "connection_cancelled": "اتصال لغو شد.",
        "connected_ready": "✅ اتصال برقرار شد! تبادل پروفایل...",
        "ready_to_transfer": "آماده تبادل فایل با {}",
        "text_received": "📄 متن دریافت و در کلیپ‌بورد کپی شد.",
        "image_received": "🖼️ تصویر دریافت و در کلیپ‌بورد کپی شد.",
        "file_received": "📁 فایل دریافت شد. آماده Paste در پوشه دلخواه.",
        "disconnected_by_you": "اتصال توسط شما قطع شد.",
        "connection_lost": "ارتباط قطع شد.",
        "sending_text": "ارسال متن...",
        "sending_image": "ارسال تصویر...",
        "sending_file": "در حال فشرده‌سازی و ارسال فایل...",
        "file_sent_success": "ارسال فایل با موفقیت انجام شد.",
        "user_prefix": "کاربر_",
        "browser_sync": "هم رسانی مرورگر",
        "capture_browser": "ضبط صفحه مرورگر فعلی",
        "set_hotkey": "تنظیم کلید میانبر (مثلاً Ctrl+Shift+B)",
        "browser_sync_instructions": "این قابلیت صفحه وب باز فعلی در مرورگر شما را ضبط کرده و به دستگاه متصل ارسال می‌کند.",
        "browser_captured": "مرورگر ضبط و ارسال شد."
    }
}
