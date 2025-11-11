import customtkinter as ctk
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import asyncio
import json
import os
import warnings
import sys
from PIL import Image
from nuker import NukerBot
from stats import StatsBot

# Suppress asyncio cleanup warnings
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=".*unclosed.*")
warnings.filterwarnings("ignore", message=".*Task was destroyed.*")

# Appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ModernBotGUI:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("Discord Server Management System")
        self.root.geometry("1100x800")
        
        # Set window icon (bundle-safe) using .ico and PNG fallback
        try:
            icon_path = self.resource_path("icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(default=icon_path)
        except Exception:
            pass
        try:
            png_fallback = self.resource_path(os.path.join("icons", "bomb.png"))
            if os.path.exists(png_fallback):
                self.root.iconphoto(True, tk.PhotoImage(file=png_fallback))
        except Exception:
            pass

        # Animation tracking
        self.pulse_animation_id = None
        self.current_tab_index = 0
        self.animating = False
        self.stats_bot = None
        self.nuker_running = False
        self.stats_running = False
        self.nuker_loop = None
        self.stats_loop = None

        # Icons and config
        self.icons = self.load_icons()
        self.config = self.load_config()
        
        # Bot instances
        self.nuker_bot = None

        # Create UI first
        self.create_ui()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start status pulse (no entrance animation)
        self.start_status_pulse()
    
    def resource_path(self, relative_path: str) -> str:
        """Get absolute path to resource, works for dev and for PyInstaller onefile."""
        try:
            base_path = sys._MEIPASS  # type: ignore[attr-defined]
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def create_ui(self):
        """Create the user interface"""
        container = ctk.CTkFrame(self.root, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=18, pady=18)

        header = ctk.CTkFrame(container, corner_radius=14, height=84)
        header.pack(fill="x")
        header.pack_propagate(False)
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(expand=True)
        if self.icons.get('bomb'):
            ctk.CTkLabel(title_frame, image=self.icons.get('bomb'), text="").pack(side="left", padx=(0,10))
        ctk.CTkLabel(title_frame, text="Discord Server Management System", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")

        self.tabs = ctk.CTkTabview(container, corner_radius=14)
        self.tabs.pack(fill="both", expand=True, pady=(12, 10))
        
        # Add tabs with icons (CustomTkinter doesn't support icons in tab text directly,
        # but we can add them to the tab content or use a workaround)
        self.tabs.add("  Bot Control")
        self.tabs.add("  Nuker Settings")
        self.tabs.add("  Stats Settings")
        self.tabs.add("  Console")
        
        # Customize tab appearance with icons after creation
        self._add_tab_icons()

        self.build_bot_control(self.tabs.tab("  Bot Control"))
        self.build_nuker_settings(self.tabs.tab("  Nuker Settings"))
        self.build_stats_settings(self.tabs.tab("  Stats Settings"))
        self.build_console(self.tabs.tab("  Console"))

        self.status_bar = ctk.CTkLabel(container, text="Ready", anchor="w", height=34, corner_radius=8)
        self.status_bar.pack(fill="x")

    # ---------- Config / Icons ----------
    def load_icons(self):
        icons = {}
        names = ['play','stop','save','clear','controller','settings','stats','console','bomb','chart','info']
        for name in names:
            try:
                p = os.path.join('icons', f'{name}.png')
                if os.path.exists(p):
                    img = Image.open(p)
                    icons[name] = ctk.CTkImage(light_image=img, dark_image=img, size=(20, 20))
                    print(f"Loaded icon: {name}")
                else:
                    print(f"Icon not found: {p}")
                    icons[name] = None
            except Exception as e:
                print(f"Error loading icon {name}: {e}")
                icons[name] = None
        return icons

    def load_config(self):
        if os.path.exists('config.json'):
            with open('config.json','r') as f:
                return json.load(f)
        return {
            "nuker_token":"",
            "stats_token":"",
            "nuker_config":{
                "channel_name":"nuked",
                "channel_count":50,
                "message_spam_count":10,
                "spam_message":"@everyone Server has been nuked!",
                "role_name":"Nuked",
                "server_name":"Nuked Server",
                "delete_delay":0.5,
                "create_delay":0.5,
                "stats_channel_id":1307163815216943208,
                "smite_cooldown":300,
                "auto_leave_delay":600
            },
            "stats_config":{
                "listen_channel_id":1307161175951147010,
                "relay_channel_id":1307182459544141896,
                "stats_channel_id":None
            }
        }

    def save_config(self):
        with open('config.json','w') as f:
            json.dump(self.config, f, indent=4)

    def _add_tab_icons(self):
        """Add icons to tab buttons"""
        try:
            # Access the internal tab buttons and add icons
            tab_dict = {
                "  Bot Control": self.icons.get('controller'),
                "  Nuker Settings": self.icons.get('settings'),
                "  Stats Settings": self.icons.get('stats'),
                "  Console": self.icons.get('console')
            }
            
            # CTkTabview stores buttons in _segmented_button
            for tab_name, icon in tab_dict.items():
                if icon and hasattr(self.tabs, '_segmented_button'):
                    # Try to configure the button with an image
                    try:
                        button = self.tabs._segmented_button._buttons_dict.get(tab_name)
                        if button:
                            button.configure(image=icon, compound="left")
                    except:
                        pass
        except Exception as e:
            print(f"Note: Could not add tab icons: {e}")
    
    def _on_tab_change(self, tab_name):
        """Handle tab change with animation"""
        if not self.animating:
            self.animating = True
            # Set the tab first
            self.tabs.set(tab_name)
            # Animate the tab content
            self._animate_tab_content()
            # Animate status bar
            self._animate_status_bar()
            # Reset animation flag
            self.root.after(300, lambda: setattr(self, 'animating', False))
    
    def _animate_tab_content(self):
        """Animate tab content with slide effect"""
        # Get current tab frame
        current_frame = self.tabs._tab_dict.get(self.tabs.get())
        if current_frame:
            # Fade in effect
            original_alpha = 1.0
            current_frame.configure(fg_color=("gray92", "gray14"))
            
            def fade_in(step=0):
                if step < 5:
                    # Gradually brighten
                    self.root.after(30, lambda: fade_in(step + 1))
                else:
                    current_frame.configure(fg_color="transparent")
            
            fade_in()
    
    def _animate_status_bar(self):
        """Animate status bar on tab change"""
        colors = ["#7289DA", "#5B6EAE", "#4E5D94", "#7289DA", "transparent"]
        
        def pulse_color(index=0):
            if index < len(colors):
                try:
                    self.status_bar.configure(fg_color=colors[index])
                    self.root.after(60, lambda: pulse_color(index + 1))
                except:
                    pass
        
        pulse_color()

    def build_bot_control(self, tab):
        # Nuker section
        nuker = ctk.CTkFrame(tab, corner_radius=14, border_width=2, border_color="#FF6B6B")
        nuker.pack(fill="x", pady=10, padx=10)
        row = ctk.CTkFrame(nuker, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(16, 8))
        if self.icons.get('bomb'):
            ctk.CTkLabel(row, image=self.icons.get('bomb'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(row, text="Nuker Bot", text_color="#FF6B6B", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")

        tok_row = ctk.CTkFrame(nuker, fg_color="transparent")
        tok_row.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(tok_row, text="Bot Token:", width=110, anchor="w").pack(side="left")
        self.nuker_token_entry = ctk.CTkEntry(tok_row, height=36, show="*", placeholder_text="Enter Nuker token...")
        self.nuker_token_entry.pack(side="left", fill="x", expand=True)
        self.nuker_token_entry.insert(0, self.config.get("nuker_token",""))

        btn_row = ctk.CTkFrame(nuker, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(4,16))
        self.nuker_start_btn = ctk.CTkButton(btn_row, text="Start Nuker", image=self.icons.get('play'), compound="left",
                                             width=180, height=40, fg_color="#43B581", hover_color="#3CA374",
                                             command=self.start_nuker_bot)
        self.nuker_start_btn.pack(side="left", padx=4)
        self.nuker_stop_btn = ctk.CTkButton(btn_row, text="Stop Nuker", image=self.icons.get('stop'), compound="left",
                                            width=180, height=40, fg_color="#F04747", hover_color="#D84040",
                                            state="disabled", command=self.stop_nuker_bot)
        self.nuker_stop_btn.pack(side="left", padx=4)

        # Stats section
        stats = ctk.CTkFrame(tab, corner_radius=14, border_width=2, border_color="#5DADE2")
        stats.pack(fill="x", pady=10, padx=10)
        row2 = ctk.CTkFrame(stats, fg_color="transparent")
        row2.pack(fill="x", padx=18, pady=(16, 8))
        if self.icons.get('chart'):
            ctk.CTkLabel(row2, image=self.icons.get('chart'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(row2, text="Stats Bot", text_color="#5DADE2", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")

        tok_row2 = ctk.CTkFrame(stats, fg_color="transparent")
        tok_row2.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(tok_row2, text="Bot Token:", width=110, anchor="w").pack(side="left")
        self.stats_token_entry = ctk.CTkEntry(tok_row2, height=36, show="*", placeholder_text="Enter Stats token...")
        self.stats_token_entry.pack(side="left", fill="x", expand=True)
        self.stats_token_entry.insert(0, self.config.get("stats_token",""))

        btn_row2 = ctk.CTkFrame(stats, fg_color="transparent")
        btn_row2.pack(fill="x", padx=18, pady=(4,16))
        self.stats_start_btn = ctk.CTkButton(btn_row2, text="Start Stats", image=self.icons.get('play'), compound="left",
                                             width=180, height=40, fg_color="#43B581", hover_color="#3CA374",
                                             command=self.start_stats_bot)
        self.stats_start_btn.pack(side="left", padx=4)
        self.stats_stop_btn = ctk.CTkButton(btn_row2, text="Stop Stats", image=self.icons.get('stop'), compound="left",
                                            width=180, height=40, fg_color="#F04747", hover_color="#D84040",
                                            state="disabled", command=self.stop_stats_bot)
        self.stats_stop_btn.pack(side="left", padx=4)

        # Status sections
        status_row = ctk.CTkFrame(tab, corner_radius=14)
        status_row.pack(fill="x", pady=10, padx=10)
        left = ctk.CTkFrame(status_row, corner_radius=10)
        right = ctk.CTkFrame(status_row, corner_radius=10)
        left.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        if self.icons.get('bomb'):
            ctk.CTkLabel(left, image=self.icons.get('bomb'), text="").pack(side="left", padx=(12,5), pady=12)
        ctk.CTkLabel(left, text="Nuker Bot:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=(0,8), pady=12)
        self.nuker_status_label = ctk.CTkLabel(left, text="OFFLINE", text_color="#F04747", font=ctk.CTkFont(size=13, weight="bold"))
        self.nuker_status_label.pack(side="left", pady=12)
        if self.icons.get('chart'):
            ctk.CTkLabel(right, image=self.icons.get('chart'), text="").pack(side="left", padx=(12,5), pady=12)
        ctk.CTkLabel(right, text="Stats Bot:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=(0,8), pady=12)
        self.stats_status_label = ctk.CTkLabel(right, text="OFFLINE", text_color="#F04747", font=ctk.CTkFont(size=13, weight="bold"))
        self.stats_status_label.pack(side="left", pady=12)

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
        
        # Setup console redirect after console widget is created
        self.setup_console_redirect()

    # ---------- Console ----------
    def setup_console_redirect(self):
        import sys
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
                if any(k in tl for k in ["error:","failed:","exception","traceback","critical","❌"]):
                    tag = "error"
                elif any(k in tl for k in ["warning","⚠️","could not","cannot"]):
                    tag = "warning"
                elif any(k in tl for k in ["✅","success","completed","online","logged in"]):
                    tag = "success"
                self.w.insert(tk.END, text, tag)
                self.w.see(tk.END)
                self.w.configure(state=tk.DISABLED)
            def flush(self):
                pass
        sys.stdout = Redirect(self.console)
        sys.stderr = Redirect(self.console)

    def clear_console(self):
        self.console.configure(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.configure(state=tk.DISABLED)

    def build_nuker_settings(self, tab):
        scroll = ctk.CTkScrollableFrame(tab, corner_radius=14)
        scroll.pack(fill="both", expand=True, padx=12, pady=12)

        # Server Settings
        server_header = ctk.CTkFrame(scroll, fg_color="transparent")
        server_header.pack(fill="x", padx=10, pady=(8,4))
        if self.icons.get('settings'):
            ctk.CTkLabel(server_header, image=self.icons.get('settings'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(server_header, text="Server Settings", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        self.create_field(scroll, "Server Name:", "server_name", self.config["nuker_config"].get("server_name", "Nuked Server"))

        # Channel Settings
        channel_header = ctk.CTkFrame(scroll, fg_color="transparent")
        channel_header.pack(fill="x", padx=10, pady=(12,4))
        if self.icons.get('console'):
            ctk.CTkLabel(channel_header, image=self.icons.get('console'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(channel_header, text="Channel Settings", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        self.create_field(scroll, "Channel Name:", "channel_name", self.config["nuker_config"]["channel_name"])
        self.create_field(scroll, "Number of Channels:", "channel_count", self.config["nuker_config"]["channel_count"])
        self.create_field(scroll, "Delete Delay (seconds):", "delete_delay", self.config["nuker_config"]["delete_delay"])
        self.create_field(scroll, "Create Delay (seconds):", "create_delay", self.config["nuker_config"]["create_delay"])

        # Message Settings
        message_header = ctk.CTkFrame(scroll, fg_color="transparent")
        message_header.pack(fill="x", padx=10, pady=(12,4))
        if self.icons.get('info'):
            ctk.CTkLabel(message_header, image=self.icons.get('info'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(message_header, text="Message Settings", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        self.create_field(scroll, "Spam Message:", "spam_message", self.config["nuker_config"]["spam_message"])
        self.create_field(scroll, "Messages per Channel:", "message_spam_count", self.config["nuker_config"]["message_spam_count"])

        # Role Settings
        role_header = ctk.CTkFrame(scroll, fg_color="transparent")
        role_header.pack(fill="x", padx=10, pady=(12,4))
        if self.icons.get('controller'):
            ctk.CTkLabel(role_header, image=self.icons.get('controller'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(role_header, text="Role Settings", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        self.create_field(scroll, "Role Name:", "role_name", self.config["nuker_config"]["role_name"])

        # Stats Channel
        stats_header = ctk.CTkFrame(scroll, fg_color="transparent")
        stats_header.pack(fill="x", padx=10, pady=(12,4))
        if self.icons.get('stats'):
            ctk.CTkLabel(stats_header, image=self.icons.get('stats'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(stats_header, text="Stats Channel", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        self.create_field(scroll, "Stats Channel ID:", "stats_channel_id", self.config["nuker_config"]["stats_channel_id"])

        # Timer Settings
        timer_header = ctk.CTkFrame(scroll, fg_color="transparent")
        timer_header.pack(fill="x", padx=10, pady=(12,4))
        if self.icons.get('controller'):
            ctk.CTkLabel(timer_header, image=self.icons.get('controller'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(timer_header, text="Timer Settings", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        self.create_field(scroll, "Smite Cooldown (seconds):", "smite_cooldown", self.config["nuker_config"].get("smite_cooldown", 300))
        self.create_field(scroll, "Auto Leave Delay (seconds):", "auto_leave_delay", self.config["nuker_config"].get("auto_leave_delay", 600))

        ctk.CTkButton(scroll, text="Save Configuration", image=self.icons.get('save'), compound="left",
                      width=220, height=45, command=self.save_nuker_config).pack(pady=20)

    def build_stats_settings(self, tab):
        frame = ctk.CTkFrame(tab, corner_radius=14)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        config_header = ctk.CTkFrame(frame, fg_color="transparent")
        config_header.pack(fill="x", padx=20, pady=(20,15))
        if self.icons.get('settings'):
            ctk.CTkLabel(config_header, image=self.icons.get('settings'), text="").pack(side="left", padx=(0,8))
        ctk.CTkLabel(config_header, text="Channel Configuration", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        
        self.create_field(frame, "Listen Channel ID:", "listen_channel_id", self.config["stats_config"]["listen_channel_id"])
        self.create_field(frame, "Relay Channel ID:", "relay_channel_id", self.config["stats_config"]["relay_channel_id"])
        self.create_field(frame, "Stats Storage Channel ID:", "stats_storage_channel_id", self.config["stats_config"].get("stats_channel_id", ""))

        ctk.CTkButton(frame, text="Save Configuration", image=self.icons.get('save'), compound="left",
                      width=220, height=45, command=self.save_stats_config).pack(pady=20)

    def create_field(self, parent, label, attr, default):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(row, text=label, width=220, anchor="w", font=ctk.CTkFont(size=12)).pack(side="left")
        entry = ctk.CTkEntry(row, height=36, corner_radius=8)
        entry.pack(side="left", fill="x", expand=True)
        if default is not None:
            entry.insert(0, str(default))
        setattr(self, f"{attr}_entry", entry)

    def save_nuker_config(self):
        try:
            nc = self.config["nuker_config"]
            nc["server_name"] = self.server_name_entry.get()
            nc["channel_name"] = self.channel_name_entry.get()
            nc["channel_count"] = int(self.channel_count_entry.get())
            nc["delete_delay"] = float(self.delete_delay_entry.get())
            nc["create_delay"] = float(self.create_delay_entry.get())
            nc["spam_message"] = self.spam_message_entry.get()
            nc["message_spam_count"] = int(self.message_spam_count_entry.get())
            nc["role_name"] = self.role_name_entry.get()
            nc["stats_channel_id"] = int(self.stats_channel_id_entry.get())
            nc["smite_cooldown"] = int(self.smite_cooldown_entry.get())
            nc["auto_leave_delay"] = int(self.auto_leave_delay_entry.get())
            self.save_config()
            if self.nuker_bot:
                self.nuker_bot.update_config(nc)
            print("Nuker configuration saved!\n")
            self.status_bar.configure(text="Nuker configuration saved successfully!")
            messagebox.showinfo("Success", "Nuker configuration saved successfully!")
        except Exception as e:
            print(f"Error saving config: {e}\n")
            self.status_bar.configure(text=f"Error saving config")
            messagebox.showerror("Error", f"Failed to save configuration: {e}")

    def save_stats_config(self):
        try:
            sc = self.config["stats_config"]
            sc["listen_channel_id"] = int(self.listen_channel_id_entry.get())
            sc["relay_channel_id"] = int(self.relay_channel_id_entry.get())
            storage = self.stats_storage_channel_id_entry.get().strip()
            sc["stats_channel_id"] = int(storage) if storage else None
            self.save_config()
            if self.stats_bot:
                self.stats_bot.update_config(sc)
            print("Stats configuration saved!\n")
            self.status_bar.configure(text="Stats configuration saved successfully!")
            messagebox.showinfo("Success", "Stats configuration saved successfully!")
        except Exception as e:
            print(f"Error saving config: {e}\n")
            self.status_bar.configure(text=f"Error saving config")
            messagebox.showerror("Error", f"Failed to save configuration: {e}")

    def process_console_command(self, _=None):
        cmd = (self.console_input.get() or "").strip().lower()
        self.console_input.delete(0, tk.END)
        if not cmd:
            return
        print(f"> {cmd}\n")
        if cmd == "help":
            print("\nAvailable commands:")
            print("  check - Verify all channel IDs are accessible")
            print("  data  - Display current stats data")
            print("  help  - Show this help message")
            print("  clear - Clear console output\n")
        elif cmd == "clear":
            self.clear_console()
        elif cmd == "check":
            self.check_channels()
        elif cmd == "data":
            self.show_stats_data()
        else:
            print("Unknown command. Type 'help' for available commands.\n")

    def check_channels(self):
        print("\n" + "="*50)
        print("Checking channel accessibility...")
        print("="*50 + "\n")
        if self.stats_bot and self.stats_loop:
            async def check():
                try:
                    listen_id = self.config["stats_config"]["listen_channel_id"]
                    relay_id = self.config["stats_config"]["relay_channel_id"]
                    storage_id = self.config["stats_config"].get("stats_channel_id")
                    
                    listen_ch = self.stats_bot.bot.get_channel(listen_id)
                    relay_ch = self.stats_bot.bot.get_channel(relay_id)
                    storage_ch = self.stats_bot.bot.get_channel(storage_id) if storage_id else None
                    
                    print(f"Listen Channel ({listen_id}): {'Accessible' if listen_ch else 'Not accessible'}")
                    print(f"Relay Channel ({relay_id}): {'Accessible' if relay_ch else 'Not accessible'}")
                    if storage_id:
                        print(f"Storage Channel ({storage_id}): {'Accessible' if storage_ch else 'Not accessible'}")
                    print("\n" + "="*50 + "\n")
                except Exception as e:
                    print(f"Error: {e}\n")
            asyncio.run_coroutine_threadsafe(check(), self.stats_loop)
        else:
            print("Stats bot is not running. Start it first.\n")

    def show_stats_data(self):
        print("\n" + "="*50)
        print("Stats Data")
        print("="*50 + "\n")
        if self.stats_bot and self.stats_loop:
            async def get_data():
                try:
                    print(f"Total Servers Nuked: {self.stats_bot.cumulative_stats.get('total_servers_nuked', 0)}")
                    print(f"Total Members Nuked: {self.stats_bot.cumulative_stats.get('total_members_nuked', 0)}")
                    print("\n" + "="*50 + "\n")
                except Exception as e:
                    print(f"❌ Error: {e}\n")
            asyncio.run_coroutine_threadsafe(get_data(), self.stats_loop)
        else:
            print("⚠️ Stats bot is not running. Start it first.\n")
    
    def pulse_status_indicators(self, brightness=1.0, direction=1):
        """Pulse the status indicators when bots are online"""
        if self.nuker_running or self.stats_running:
            brightness += 0.03 * direction
            
            if brightness >= 1.15:
                direction = -1
                brightness = 1.15
            elif brightness <= 0.85:
                direction = 1
                brightness = 0.85
            
            # Apply pulsing effect
            base_r, base_g, base_b = 67, 181, 129  # #43B581
            new_r = min(255, int(base_r * brightness))
            new_g = min(255, int(base_g * brightness))
            new_b = min(255, int(base_b * brightness))
            color = f"#{new_r:02x}{new_g:02x}{new_b:02x}"
            
            if self.nuker_running:
                self.nuker_status_label.configure(text_color=color)
            
            if self.stats_running:
                self.stats_status_label.configure(text_color=color)
        
        self.pulse_animation_id = self.root.after(50, lambda: self.pulse_status_indicators(brightness, direction))
    
    def start_status_pulse(self):
        """Start pulsing animation for status indicators"""
        self.pulse_status_indicators()
    
    def animate_entrance(self):
        """Animate GUI entrance with fade-in"""
        # Start from slightly visible so UI is shown
        self.root.attributes('-alpha', 0.3)
        self.fade_in(0.3)
    
    def fade_in(self, alpha=0.3):
        """Fade in the window"""
        if alpha < 1.0:
            alpha += 0.07
            self.root.attributes('-alpha', alpha)
            self.root.after(15, lambda: self.fade_in(alpha))
        else:
            self.root.attributes('-alpha', 1.0)
            self.start_status_pulse()

    # ---------- Bot control ----------
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

    def start_stats_bot(self):
        token = (self.stats_token_entry.get() or "").strip()
        if not token:
            messagebox.showerror("Error", "Please enter a Stats bot token")
            return
        self.config["stats_token"] = token
        self.save_config()
        self.stats_running = True
        self.stats_start_btn.configure(state="disabled")
        self.stats_stop_btn.configure(state="normal")
        self.stats_status_label.configure(text="ONLINE", text_color="#43B581")
        self.status_bar.configure(text="Stats Bot: Online - Listening for stats")
        print("Starting stats bot...\n")

        def runner():
            self.stats_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.stats_loop)
            self.stats_bot = StatsBot()
            self.stats_bot.update_config(self.config.get("stats_config", {}))
            try:
                self.stats_loop.run_until_complete(self.stats_bot.start(token))
            except Exception as e:
                print(f"Error: {e}\n")
                self.root.after(0, self._stats_failed)
        threading.Thread(target=runner, daemon=True).start()

    def _stats_failed(self):
        self.stats_running = False
        self.stats_start_btn.configure(state="normal")
        self.stats_stop_btn.configure(state="disabled")
        self.stats_status_label.configure(text="OFFLINE", text_color="#F04747")

    def stop_stats_bot(self):
        if self.stats_bot and self.stats_loop:
            asyncio.run_coroutine_threadsafe(self.stats_bot.stop(), self.stats_loop)
        self.stats_running = False
        self.stats_start_btn.configure(state="normal")
        self.stats_stop_btn.configure(state="disabled")
        self.stats_status_label.configure(text="OFFLINE", text_color="#F04747")
        self.status_bar.configure(text="Stats Bot: Offline")
        print("Stopping stats bot...\n")

    # ---------- Shutdown ----------
    def on_closing(self):
        print("\nShutting down...\n")
        try:
            if self.nuker_running and self.nuker_bot and self.nuker_loop:
                asyncio.run_coroutine_threadsafe(self.nuker_bot.bot.close(), self.nuker_loop)
            if self.stats_running and self.stats_bot and self.stats_loop:
                asyncio.run_coroutine_threadsafe(self.stats_bot.bot.close(), self.stats_loop)
        except Exception:
            pass
        self.root.destroy()


def main():
    root = ctk.CTk()
    app = ModernBotGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
