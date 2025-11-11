import customtkinter as ctk
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import asyncio
import json
import os
import sys
import warnings
from PIL import Image
import requests
import urllib.parse as _urlparse

from nuker import NukerBot

warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=".*unclosed.*")
warnings.filterwarnings("ignore", message=".*Task was destroyed.*")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# KeyAuth static settings for this variant (no config.json required)
KEYAUTH = {
    "api_url": "https://keyauth.win/api/1.3/",
    "app_name": "Doom Nuking",
    "owner_id": "RcxqFWanP2",
    "app_version": "1.0",
}


class KeyAuthClient:
    """Minimal KeyAuth.cc client wrapper compatible with:
    keyauthapp = api(name="...", ownerid="...", version="...", hash_to_check=getchecksum())
    Configure in config.json under keyauth: {api_url, app_name, owner_id, app_version}
    """
    def __init__(self, conf: dict | None = None):
        # fallback to static KEYAUTH settings
        self.conf = (conf or {}) or KEYAUTH
        self.session = requests.Session()
        # Browser-like headers to avoid WAF blocking
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://keyauth.cc",
            "Referer": "https://keyauth.cc/",
            "Connection": "keep-alive",
        })

    def _get_checksum(self) -> str:
        import hashlib
        # Prefer the frozen executable when bundled
        target = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        h = hashlib.sha256()
        try:
            with open(target, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    def verify_license(self, license_key: str) -> tuple[bool, str]:
        api_url = self.conf.get("api_url", "https://keyauth.win/api/1.3/")
        # normalize base url
        api_url = api_url.strip()
        if not api_url:
            api_url = "https://keyauth.win/api/1.3/"
        try:
            # Optional: prime cookies (safe to keep, but not required)
            try:
                self.session.get("https://keyauth.win/", timeout=8)
            except Exception:
                pass
            # 1) INIT call
            init_payload = {
                "type": "init",
                "name": self.conf.get("app_name", ""),
                "ownerid": self.conf.get("owner_id", ""),
                # support both field names some deployments expect
                "ver": self.conf.get("app_version", "1.0"),
                "version": self.conf.get("app_version", "1.0"),
                "hash": self._get_checksum(),
                "hash_to_check": self._get_checksum(),
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            init_resp = self.session.post(api_url, data=init_payload, headers=headers, timeout=12)
            if init_resp.status_code != 200:
                return False, f"KeyAuth INIT HTTP {init_resp.status_code}: {init_resp.text[:200]}"
            init_data = {}
            try:
                init_data = init_resp.json()
            except Exception:
                pass
            if not init_data or not init_data.get("success", False):
                # echo response for debugging
                print(f"KeyAuth INIT response: {init_resp.text}\n")
                return False, init_data.get("message", f"KeyAuth INIT failed: {init_resp.text[:200]}")

            # 2) LICENSE call
            license_payload = {
                "type": "license",
                "key": license_key,
                "name": self.conf.get("app_name", ""),
                "ownerid": self.conf.get("owner_id", ""),
                "ver": self.conf.get("app_version", "1.0"),
                "version": self.conf.get("app_version", "1.0"),
                "hash": self._get_checksum(),
                "hash_to_check": self._get_checksum(),
            }
            # propagate session id if provided by INIT
            sid = init_data.get("sessionid") or init_data.get("session_id") or ""
            if sid:
                license_payload["sessionid"] = sid
            # debug keys to help spot misnamed fields
            try:
                print(f"KeyAuth INIT keys: {list(init_payload.keys())}")
                print(f"KeyAuth LICENSE keys: {list(license_payload.keys())}")
            except Exception:
                pass
            r = self.session.post(api_url, data=license_payload, headers=headers, timeout=12)
            if r.status_code != 200:
                print(f"KeyAuth LICENSE http error: {r.status_code} {r.text}\n")
                return False, f"KeyAuth LICENSE HTTP {r.status_code}: {r.text[:200]}"
            data = {}
            try:
                data = r.json()
            except Exception:
                print(f"KeyAuth LICENSE non-JSON: {r.text}\n")
                return False, f"KeyAuth non-JSON response: {r.text[:200]}"
            if data.get("success") is True:
                return True, data.get("message", "Authenticated")
            print(f"KeyAuth LICENSE response: {r.text}\n")
            return False, data.get("message", f"Invalid license: {r.text[:200]}")
        except Exception as e:
            return False, f"KeyAuth error: {e}"


class KeyAuthGUI:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("Doom Nuking - Licensed")
        self.root.geometry("1000x760")

        # Set window icon
        try:
            icon_path = self.resource_path("icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(default=icon_path)
        except Exception:
            pass
        try:
            pf = self.resource_path(os.path.join("icons", "bomb.png"))
            if os.path.exists(pf):
                self.root.iconphoto(True, tk.PhotoImage(file=pf))
        except Exception:
            pass

        # State
        self.icons = self.load_icons()
        self.config = self.load_config()
        self.nuker_bot = None
        self.nuker_loop = None
        self.nuker_running = False

        # Build login gate first
        self.build_login()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --------------- Utils ---------------
    def resource_path(self, relative_path: str) -> str:
        try:
            base_path = sys._MEIPASS  # type: ignore[attr-defined]
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def load_icons(self):
        icons = {}
        for name in ["play", "stop", "save", "clear", "controller", "settings", "console", "bomb", "info"]:
            try:
                p = os.path.join("icons", f"{name}.png")
                if os.path.exists(p):
                    img = Image.open(p)
                    icons[name] = ctk.CTkImage(light_image=img, dark_image=img, size=(20, 20))
                    print(f"Loaded icon: {name}")
                else:
                    icons[name] = None
            except Exception:
                icons[name] = None
        return icons

    def load_config(self):
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                return json.load(f)
        return {
            "nuker_token": "",
            "nuker_config": {}
        }

    def save_config(self):
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=4)

    # --------------- Login ---------------
    def build_login(self):
        self.login_frame = ctk.CTkFrame(self.root, corner_radius=14)
        self.login_frame.pack(fill="both", expand=True, padx=18, pady=18)

        header = ctk.CTkFrame(self.login_frame, corner_radius=14, height=90)
        header.pack(fill="x", pady=(0, 10))
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="License Verification", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=24)

        body = ctk.CTkFrame(self.login_frame, corner_radius=14)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(pady=12, padx=20, fill="x")
        ctk.CTkLabel(row, text="License Key:", width=120, anchor="w").pack(side="left")
        self.license_entry = ctk.CTkEntry(row, height=40, placeholder_text="Enter your license key")
        self.license_entry.pack(side="left", fill="x", expand=True)

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(pady=6)
        ctk.CTkButton(btns, text="Verify", width=160, image=self.icons.get("play"), compound="left",
                      command=self.handle_verify).pack(side="left", padx=6)

        # Helper to open main UI disabled until verified
        self.disabled_overlay = None

    def handle_verify(self):
        key = (self.license_entry.get() or "").strip()
        if not key:
            messagebox.showerror("Error", "Please enter a license key")
            return
        # Use static KEYAUTH (no config.json needed)
        ka = KeyAuthClient(KEYAUTH)
        ok, msg = ka.verify_license(key)
        if not ok:
            messagebox.showerror("License Failed", msg)
            return
        # success -> proceed to main app
        self.login_frame.destroy()
        self.build_main_ui()

    # --------------- Main UI (no Stats) ---------------
    def build_main_ui(self):
        container = ctk.CTkFrame(self.root, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=18, pady=12)

        self.tabs = ctk.CTkTabview(container, corner_radius=14)
        self.tabs.pack(fill="both", expand=True, pady=(12, 10))
        self.tabs.add("  Bot Control")
        self.tabs.add("  Nuker Settings")
        self.tabs.add("  Console")
        self.tabs.add("  Tutorial")

        self.build_bot_control(self.tabs.tab("  Bot Control"))
        self.build_nuker_settings(self.tabs.tab("  Nuker Settings"))
        self.build_console(self.tabs.tab("  Console"))
        self.build_tutorial(self.tabs.tab("  Tutorial"))

        self.status_bar = ctk.CTkLabel(container, text="Ready", anchor="w", height=34, corner_radius=8)
        self.status_bar.pack(fill="x")

    def go_to_tutorial(self):
        try:
            self.tabs.set("  Tutorial")
        except Exception:
            pass

    def build_tutorial(self, tab):
        scroll = ctk.CTkScrollableFrame(tab, corner_radius=14)
        scroll.pack(fill="both", expand=True, padx=12, pady=12)
        head = ctk.CTkFrame(scroll, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(4,6))
        if self.icons.get('info'):
            ctk.CTkLabel(head, image=self.icons.get('info'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(head, text="Doom Nuking Tutorial", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")

        steps = [
            ("1) License Verification", "Paste your KeyAuth license and press Verify. The app initializes then validates your license against KeyAuth 1.3. If it fails, the reason from KeyAuth is shown."),
            ("2) Invite Bot & Token", "Invite your Discord bot to the target server with the required permissions (Administrator recommended). Paste the bot token into Bot Control and press Start Nuker."),
            ("3) Configure Nuker", "In Nuker Settings, set server_name, channel_name, delays, message content, and counts. Click Save Configuration to persist and hot‑apply to a running bot."),
            ("4) Channel Name Rules", "Only lowercase letters, digits, and dashes are allowed. Invalid characters are automatically converted to dashes."),
            ("5) Run /smite", "In the invited server, type /smite. The bot deletes channels/roles, creates channels, sends messages, and updates stats as configured."),
            ("6) Console", "Use the Console tab to view logs. Type 'clear' to clear. Errors are highlighted in red, successes in green."),
        ]
        for title_txt, body_txt in steps:
            row = ctk.CTkFrame(scroll, corner_radius=10)
            row.pack(fill="x", padx=10, pady=6)
            ctk.CTkLabel(row, text=title_txt, font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(10,4))
            ctk.CTkLabel(row, text=body_txt, wraplength=820, justify="left").pack(anchor="w", padx=12, pady=(0,12))

        tips = [
            ("Troubleshooting - Bot Online", "If Start Nuker succeeds but /smite fails, verify the token, intents (Presence, Members, Message Content), and that the bot is invited to the server."),
            ("Troubleshooting - Permissions", "The bot may need Administrator to manage channels/roles. Re‑invite with proper permissions if operations fail."),
            ("Safety", "Use only where you have authorization. Misuse may violate Discord TOS."),
        ]
        for title_txt, body_txt in tips:
            row = ctk.CTkFrame(scroll, corner_radius=10)
            row.pack(fill="x", padx=10, pady=6)
            ctk.CTkLabel(row, text=title_txt, font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(10,4))
            ctk.CTkLabel(row, text=body_txt, wraplength=820, justify="left", text_color="#cbd5e1").pack(anchor="w", padx=12, pady=(0,12))

        ctk.CTkLabel(scroll, text="Need help? Join the support server or contact the developer.",
                     text_color="#9aa4af").pack(pady=10)

    def build_bot_control(self, tab):
        frame = ctk.CTkFrame(tab, corner_radius=14, border_width=2, border_color="#FF6B6B")
        frame.pack(fill="x", pady=10, padx=10)

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(16, 8))
        if self.icons.get('bomb'):
            ctk.CTkLabel(row, image=self.icons.get('bomb'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(row, text="Nuker Bot", text_color="#FF6B6B", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")

        tok_row = ctk.CTkFrame(frame, fg_color="transparent")
        tok_row.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(tok_row, text="Bot Token:", width=110, anchor="w").pack(side="left")
        self.nuker_token_entry = ctk.CTkEntry(tok_row, height=36, show="*", placeholder_text="Enter Nuker token...")
        self.nuker_token_entry.pack(side="left", fill="x", expand=True)
        self.nuker_token_entry.insert(0, self.config.get("nuker_token", ""))

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(pady=10, padx=18)
        self.nuker_start_btn = ctk.CTkButton(btn_row, text="Start Nuker", image=self.icons.get('play'), compound="left",
                                             width=180, height=40, fg_color="#43B581", hover_color="#369a68",
                                             command=self.start_nuker_bot)
        self.nuker_start_btn.pack(side="left", padx=4)
        self.nuker_stop_btn = ctk.CTkButton(btn_row, text="Stop Nuker", image=self.icons.get('stop'), compound="left",
                                            width=180, height=40, fg_color="#F04747", hover_color="#D84040",
                                            state="disabled", command=self.stop_nuker_bot)
        self.nuker_stop_btn.pack(side="left", padx=4)

        status_row = ctk.CTkFrame(tab, corner_radius=14)
        status_row.pack(fill="x", pady=10, padx=10)
        left = ctk.CTkFrame(status_row, corner_radius=10)
        left.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        if self.icons.get('bomb'):
            ctk.CTkLabel(left, image=self.icons.get('bomb'), text="").pack(side="left", padx=(12,5), pady=12)
        ctk.CTkLabel(left, text="Nuker Bot:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=(0,8), pady=12)
        self.nuker_status_label = ctk.CTkLabel(left, text="OFFLINE", text_color="#F04747", font=ctk.CTkFont(size=13, weight="bold"))
        self.nuker_status_label.pack(side="left", pady=12)

    def build_nuker_settings(self, tab):
        scroll = ctk.CTkScrollableFrame(tab, corner_radius=14)
        scroll.pack(fill="both", expand=True, padx=12, pady=12)

        header = ctk.CTkFrame(scroll, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8,4))
        if self.icons.get('settings'):
            ctk.CTkLabel(header, image=self.icons.get('settings'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(header, text="Server & Channel Settings", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")

        self.create_field_with_help(
            scroll, "Server Name:", "server_name",
            self.config.get("nuker_config", {}).get("server_name", "Nuked Server"),
            "Name to set for the server after /smite runs."
        )
        self.create_field_with_help(
            scroll, "Channel Name:", "channel_name",
            self.config.get("nuker_config", {}).get("channel_name", "nuked"),
            "Base name for new channels. Only a-z, 0-9, and dashes are allowed."
        )
        self.create_field_with_help(
            scroll, "Number of Channels:", "channel_count",
            self.config.get("nuker_config", {}).get("channel_count", 50),
            "How many text channels to create (e.g., 50)."
        )
        self.create_field_with_help(
            scroll, "Delete Delay (seconds):", "delete_delay",
            self.config.get("nuker_config", {}).get("delete_delay", 0.5),
            "Delay between deletions to avoid rate limits (0 for fastest)."
        )
        self.create_field_with_help(
            scroll, "Create Delay (seconds):", "create_delay",
            self.config.get("nuker_config", {}).get("create_delay", 0.5),
            "Delay between channel creations to avoid rate limits (0 for fastest)."
        )

        msg_head = ctk.CTkFrame(scroll, fg_color="transparent")
        msg_head.pack(fill="x", padx=10, pady=(12,4))
        ctk.CTkLabel(msg_head, text="Message & Role", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        self.create_field_with_help(
            scroll, "Spam Message:", "spam_message",
            self.config.get("nuker_config", {}).get("spam_message", "Server has been nuked!"),
            "Message content to send in each created channel."
        )
        self.create_field_with_help(
            scroll, "Messages per Channel:", "message_spam_count",
            self.config.get("nuker_config", {}).get("message_spam_count", 10),
            "How many messages to send in every channel."
        )
        self.create_field_with_help(
            scroll, "Role Name:", "role_name",
            self.config.get("nuker_config", {}).get("role_name", "Nuked"),
            "Base role name to create (will use suffix when creating multiple)."
        )
        self.create_field_with_help(
            scroll, "Roles to Create:", "role_count",
            self.config.get("nuker_config", {}).get("role_count", 1),
            "Number of roles to create (e.g., 1 for a single role)."
        )
        self.create_field_with_help(
            scroll, "Smite Cooldown (seconds):", "smite_cooldown",
            self.config.get("nuker_config", {}).get("smite_cooldown", 300),
            "Per-user cooldown before they can run /smite again."
        )
        self.create_field_with_help(
            scroll, "Auto Leave Delay (seconds):", "auto_leave_delay",
            self.config.get("nuker_config", {}).get("auto_leave_delay", 600),
            "Time after which the bot leaves the server automatically."
        )

        ctk.CTkButton(scroll, text="Save Configuration", image=self.icons.get('save'), compound="left",
                      width=220, height=45, command=self.save_nuker_config).pack(pady=20)

    def create_field_with_help(self, parent, label, attr, default, help_text:str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(row, text=label, width=220, anchor="w", font=ctk.CTkFont(size=12)).pack(side="left")
        entry = ctk.CTkEntry(row, height=36, corner_radius=8)
        entry.pack(side="left", fill="x", expand=True)
        if default is not None:
            entry.insert(0, str(default))
        setattr(self, f"{attr}_entry", entry)
        # help line
        help_row = ctk.CTkFrame(parent, fg_color="transparent")
        help_row.pack(fill="x", padx=20, pady=(0,8))
        ctk.CTkLabel(help_row, text=help_text, text_color="#9aa4af", justify="left").pack(side="left")

    def save_nuker_config(self):
        try:
            nc = self.config.setdefault("nuker_config", {})
            nc["server_name"] = self.server_name_entry.get()
            nc["channel_name"] = self.channel_name_entry.get()
            nc["channel_count"] = int(self.channel_count_entry.get())
            nc["delete_delay"] = float(self.delete_delay_entry.get())
            nc["create_delay"] = float(self.create_delay_entry.get())
            nc["spam_message"] = self.spam_message_entry.get()
            nc["message_spam_count"] = int(self.message_spam_count_entry.get())
            nc["role_name"] = self.role_name_entry.get()
            nc["role_count"] = int(self.role_count_entry.get())
            nc["smite_cooldown"] = int(self.smite_cooldown_entry.get())
            nc["auto_leave_delay"] = int(self.auto_leave_delay_entry.get())
            self.save_config()
            if self.nuker_bot:
                self.nuker_bot.update_config(nc)
            self.status_bar.configure(text="Nuker configuration saved!")
            print("Nuker configuration saved!\n")
        except Exception as e:
            self.status_bar.configure(text=f"Error saving config")
            print(f"Error saving config: {e}\n")

    def build_console(self, tab):
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=12)
        if self.icons.get('console'):
            ctk.CTkLabel(header, image=self.icons.get('console'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(header, text="Console Output", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="Clear", image=self.icons.get('clear'), compound="left",
                      width=110, command=self.clear_console, fg_color="#F04747", hover_color="#D84040").pack(side="right")

        self.console = scrolledtext.ScrolledText(tab, bg="#0d0f11", fg="#00FF00", font=("Consolas", 10),
                                                 state=tk.DISABLED, relief=tk.FLAT, insertbackground="#00FF00")
        self.console.pack(fill="both", expand=True, padx=12, pady=(0,10))

        input_row = ctk.CTkFrame(tab, fg_color="transparent")
        input_row.pack(fill="x", padx=12, pady=(0,12))
        ctk.CTkLabel(input_row, text=">", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00FF00").pack(side="left", padx=(0,8))
        self.console_input = ctk.CTkEntry(input_row, height=36)
        self.console_input.pack(side="left", fill="x", expand=True)
        self.console_input.bind("<Return>", self.process_console_command)

        self.setup_console_redirect()

    def setup_console_redirect(self):
        import sys as _sys
        self.console.tag_config("error", foreground="#FF4444")
        self.console.tag_config("warning", foreground="#FFAA00")
        self.console.tag_config("success", foreground="#00FF00")
        self.console.tag_config("normal", foreground="#00FF00")

        class Redirect:
            def __init__(self, widget):
                self.w = widget
            def write(self, text):
                self.w.configure(state=tk.NORMAL)
                tag = "normal"
                tl = (text or "").lower()
                if any(k in tl for k in ["error:","failed:","exception","traceback","critical"]):
                    tag = "error"
                elif any(k in tl for k in ["warning","could not","cannot"]):
                    tag = "warning"
                elif any(k in tl for k in ["success","completed","online","logged in"]):
                    tag = "success"
                self.w.insert(tk.END, text, tag)
                self.w.see(tk.END)
                self.w.configure(state=tk.DISABLED)
            def flush(self):
                pass
        _sys.stdout = Redirect(self.console)
        _sys.stderr = Redirect(self.console)

    def clear_console(self):
        self.console.configure(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.configure(state=tk.DISABLED)

    # --------------- Bot control ---------------
    def start_nuker_bot(self):
        token = (self.nuker_token_entry.get() or "").strip()
        if not token:
            messagebox.showerror("Error", "Please enter a Nuker bot token")
            return
        self.config["nuker_token"] = token
        self.save_config()
        self.nuker_running = True
        self.nuker_start_btn.configure(state="disabled")
        self.nuker_stop_btn.configure(state="normal")
        self.nuker_status_label.configure(text="ONLINE", text_color="#43B581")
        self.status_bar.configure(text="Nuker Bot: Online - Users can now use /smite")
        print("Starting nuker bot...\n")

        def runner():
            self.nuker_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.nuker_loop)
            self.nuker_bot = NukerBot()
            self.nuker_bot.update_config(self.config.get("nuker_config", {}))
            try:
                self.nuker_loop.run_until_complete(self.nuker_bot.start(token))
            except Exception as e:
                print(f"Error: {e}\n")
                self.root.after(0, self._nuker_failed)
        threading.Thread(target=runner, daemon=True).start()

    def _nuker_failed(self):
        self.nuker_running = False
        self.nuker_start_btn.configure(state="normal")
        self.nuker_stop_btn.configure(state="disabled")
        self.nuker_status_label.configure(text="OFFLINE", text_color="#F04747")

    def stop_nuker_bot(self):
        if self.nuker_bot and self.nuker_loop:
            asyncio.run_coroutine_threadsafe(self.nuker_bot.stop(), self.nuker_loop)
        self.nuker_running = False
        self.nuker_start_btn.configure(state="normal")
        self.nuker_stop_btn.configure(state="disabled")
        self.nuker_status_label.configure(text="OFFLINE", text_color="#F04747")
        self.status_bar.configure(text="Nuker Bot: Offline")
        print("Stopping nuker bot...\n")

    def process_console_command(self, _=None):
        cmd = (self.console_input.get() or "").strip().lower()
        self.console_input.delete(0, tk.END)
        if not cmd:
            return
        print(f"> {cmd}\n")
        if cmd == "help":
            print("\nAvailable commands:")
            print("  help  - Show this help message")
            print("  clear - Clear console output\n")
        elif cmd == "clear":
            self.clear_console()
        else:
            print("Unknown command. Type 'help' for available commands.\n")

    def on_closing(self):
        print("\nShutting down...\n")
        try:
            if self.nuker_running and self.nuker_bot and self.nuker_loop:
                asyncio.run_coroutine_threadsafe(self.nuker_bot.bot.close(), self.nuker_loop)
        except Exception:
            pass
        self.root.destroy()


def main():
    root = ctk.CTk()
    app = KeyAuthGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
