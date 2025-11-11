import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import asyncio
import json
import os
import warnings
from PIL import Image, ImageTk, ImageDraw
from nuker import NukerBot
from stats import StatsBot

# Suppress asyncio cleanup warnings
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=".*unclosed.*")
warnings.filterwarnings("ignore", message=".*Task was destroyed.*")

class BotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Discord Server Management System")
        self.root.geometry("900x700")
        self.root.configure(bg="#1a1d21")
        
        # Bot instances
        self.nuker_bot = None
        self.stats_bot = None
        
        # Bot states
        self.nuker_running = False
        self.stats_running = False
        
        # Async loops
        self.nuker_loop = None
        self.stats_loop = None
        
        # Animation tracking
        self.current_tab = 0
        self.animation_running = False
        self.pulse_animation_id = None
        self.fade_step = 0
        
        # Rounded corner cache
        self.rounded_images = {}
        
        # Load icons
        self.icons = self.load_icons()
        
        # Load configuration
        self.config = self.load_config()
        
        # Setup custom styles
        self.setup_styles()
        
        # Create UI
        self.create_ui()
        
        # Redirect print to console
        self.setup_console_redirect()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start entrance animation
        self.animate_entrance()
    
    def load_icons(self):
        """Load all icons from the icons folder"""
        icons = {}
        icon_names = ['play', 'stop', 'save', 'clear', 'controller', 'settings', 
                      'stats', 'console', 'online', 'offline', 'bomb', 'chart', 'info']
        
        for name in icon_names:
            try:
                icon_path = os.path.join("icons", f"{name}.png")
                if os.path.exists(icon_path):
                    img = Image.open(icon_path)
                    img = img.resize((20, 20), Image.Resampling.LANCZOS)
                    icons[name] = ImageTk.PhotoImage(img)
                    print(f"✅ Loaded icon: {name}")
                else:
                    print(f"⚠️ Icon not found: {icon_path}")
                    icons[name] = None
            except Exception as e:
                print(f"⚠️ Error loading icon {name}: {e}")
                icons[name] = None
        
        return icons
    
    def create_rounded_rectangle(self, width, height, radius, color):
        """Create a rounded rectangle image"""
        # Create cache key
        cache_key = f"{width}x{height}_{radius}_{color}"
        if cache_key in self.rounded_images:
            return self.rounded_images[cache_key]
        
        # Create image with alpha channel
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Convert hex color to RGB
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        
        # Draw rounded rectangle
        draw.rounded_rectangle(
            [(0, 0), (width-1, height-1)],
            radius=radius,
            fill=rgb + (255,),
            outline=None
        )
        
        # Cache and return
        photo = ImageTk.PhotoImage(image)
        self.rounded_images[cache_key] = photo
        return photo
    
    def apply_rounded_style(self, widget, bg_color, radius=10):
        """Apply rounded corner style to a widget using canvas"""
        # This is a visual enhancement - actual widget remains rectangular
        # but we can style it to appear rounded
        widget.config(relief=tk.FLAT, bd=0)
    
    def animate_entrance(self):
        """Animate the GUI entrance with fade-in effect"""
        self.root.attributes('-alpha', 0.0)
        self.fade_in()
    
    def fade_in(self, alpha=0.0):
        """Fade in the window"""
        if alpha < 1.0:
            alpha += 0.05
            self.root.attributes('-alpha', alpha)
            self.root.after(20, lambda: self.fade_in(alpha))
        else:
            self.root.attributes('-alpha', 1.0)
            # Start status pulse animation
            self.start_status_pulse()
    
    def setup_styles(self):
        """Setup custom ttk styles for dark theme"""
        style = ttk.Style()
        
        # Configure notebook (tabs container)
        style.theme_use('default')
        style.configure('TNotebook', 
            background='#1a1d21',
            borderwidth=0,
            tabmargins=[2, 5, 2, 0]
        )
        style.configure('TNotebook.Tab',
            background='#2C2F33',
            foreground='#99AAB5',
            padding=[20, 10],
            font=('Arial', 10, 'bold'),
            borderwidth=0
        )
        style.map('TNotebook.Tab',
            background=[('selected', '#7289DA'), ('active', '#5B6EAE')],
            foreground=[('selected', '#FFFFFF'), ('active', '#FFFFFF')],
            expand=[('selected', [1, 1, 1, 0])]
        )
    
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                return json.load(f)
        return {
            "nuker_token": "",
            "stats_token": "",
            "nuker_config": {
                "channel_name": "nuked",
                "channel_count": 50,
                "message_spam_count": 10,
                "spam_message": "@everyone Server has been nuked!",
                "role_name": "Nuked",
                "server_name": "Nuked Server",
                "delete_delay": 0.5,
                "create_delay": 0.5,
                "stats_channel_id": 1307163815216943208,
                "smite_cooldown": 300,
                "auto_leave_delay": 600
            },
            "stats_config": {
                "listen_channel_id": 1307161175951147010,
                "relay_channel_id": 1307182459544141896,
                "stats_channel_id": None
            }
        }
    
    def save_config(self):
        """Save configuration to file"""
        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=4)
    
    def create_ui(self):
        """Create the user interface"""
        # Main container
        main_frame = tk.Frame(self.root, bg="#1a1d21")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Header frame with gradient effect
        header_frame = tk.Frame(main_frame, bg="#7289DA", height=80, highlightthickness=0)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        header_frame.pack_propagate(False)
        self.apply_rounded_style(header_frame, "#7289DA", radius=10)
        
        # Title with icon
        title_label = tk.Label(
            header_frame,
            text="Discord Server Management System",
            font=("Segoe UI", 20, "bold"),
            bg="#7289DA",
            fg="#FFFFFF"
        )
        title_label.pack(expand=True)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Bind tab change event for animations
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Create tabs
        self.create_bot_control_tab()
        self.create_nuker_config_tab()
        self.create_stats_config_tab()
        self.create_console_tab()
        
        # Update tab labels with icons
        self.update_tab_labels()
        
        # Status bar with border
        status_container = tk.Frame(main_frame, bg="#7289DA", height=2)
        status_container.pack(fill=tk.X)
        
        self.status_bar = tk.Label(
            main_frame,
            text="Ready",
            bg="#23272A",
            fg="#FFFFFF",
            anchor=tk.W,
            padx=15,
            font=("Segoe UI", 9)
        )
        self.status_bar.pack(fill=tk.X)
    
    def on_tab_changed(self, event):
        """Handle tab change with animation"""
        new_tab = self.notebook.index(self.notebook.select())
        if new_tab != self.current_tab and not self.animation_running:
            self.animate_tab_transition(new_tab)
        self.current_tab = new_tab
    
    def animate_tab_transition(self, new_tab_index):
        """Animate tab transition with enhanced effects"""
        self.animation_running = True
        
        # Pulse effect on status bar with gradient
        original_bg = self.status_bar.cget('bg')
        colors = ['#7289DA', '#5B6EAE', '#7289DA', original_bg]
        
        def pulse_colors(index=0):
            if index < len(colors):
                self.status_bar.config(bg=colors[index])
                self.root.after(50, lambda: pulse_colors(index + 1))
            else:
                self.animation_running = False
        
        pulse_colors()
    
    def update_tab_labels(self):
        """Update tab labels to include icons"""
        # ttk.Notebook supports image parameter for tabs
        tab_configs = [
            (0, 'controller', 'Bot Control'),
            (1, 'settings', 'Nuker Settings'),
            (2, 'stats', 'Stats Bot Settings'),
            (3, 'console', 'Console')
        ]
        
        for tab_index, icon_name, tab_text in tab_configs:
            if self.icons.get(icon_name):
                self.notebook.tab(tab_index, image=self.icons.get(icon_name), compound=tk.LEFT, text=f" {tab_text}")
    
    def create_bot_control_tab(self):
        """Create bot control tab"""
        tab = tk.Frame(self.notebook, bg="#1a1d21")
        self.notebook.add(tab, text="  Bot Control  ")
        
        # Nuker Bot Section
        nuker_frame = tk.LabelFrame(
            tab,
            text="",
            bg="#23272A",
            fg="#FF6B6B",
            font=("Segoe UI", 13, "bold"),
            padx=20,
            pady=15,
            relief=tk.FLAT,
            borderwidth=0,
            highlightbackground="#FF6B6B",
            highlightthickness=2
        )
        nuker_frame.pack(fill=tk.X, padx=15, pady=15)
        self.apply_rounded_style(nuker_frame, "#23272A", radius=12)
        
        # Custom header with icon
        header_frame = tk.Frame(nuker_frame, bg="#23272A")
        header_frame.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        if self.icons.get('bomb'):
            icon_label = tk.Label(header_frame, image=self.icons.get('bomb'), bg="#23272A")
            icon_label.pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Label(
            header_frame,
            text="Nuker Bot",
            bg="#23272A",
            fg="#FF6B6B",
            font=("Segoe UI", 13, "bold")
        ).pack(side=tk.LEFT)
        
        tk.Label(nuker_frame, text="Bot Token:", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, pady=8)
        self.nuker_token_entry = tk.Entry(nuker_frame, width=50, show="*", bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.nuker_token_entry.grid(row=1, column=1, padx=10, pady=8)
        self.nuker_token_entry.insert(0, self.config["nuker_token"])
        
        tk.Label(
            nuker_frame,
            text="Users can invite the bot and use /smite in their servers",
            bg="#23272A",
            fg="#99AAB5",
            font=("Segoe UI", 9, "italic")
        ).grid(row=2, column=0, columnspan=2, pady=8)
        
        button_frame = tk.Frame(nuker_frame, bg="#23272A")
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        self.nuker_start_btn = tk.Button(
            button_frame,
            text=" Start Nuker Bot" if self.icons.get('play') else "[▶] Start Nuker Bot",
            image=self.icons.get('play') if self.icons.get('play') else None,
            compound=tk.LEFT if self.icons.get('play') else None,
            bg="#43B581",
            fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            command=lambda: self.animate_button_click(self.nuker_start_btn, self.start_nuker_bot),
            width=160,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground="#3CA374",
            bd=0,
            highlightthickness=0
        )
        self.nuker_start_btn.pack(side=tk.LEFT, padx=5)
        self.add_button_hover_effect(self.nuker_start_btn, "#43B581", "#3CA374")
        
        self.nuker_stop_btn = tk.Button(
            button_frame,
            text=" Stop Nuker Bot",
            image=self.icons.get('stop'),
            compound=tk.LEFT,
            bg="#F04747",
            fg="#000000",
            font=("Segoe UI", 10, "bold"),
            command=lambda: self.animate_button_click(self.nuker_stop_btn, self.stop_nuker_bot),
            width=160,
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED,
            activebackground="#D84040",
            disabledforeground="#000000",
            bd=0,
            highlightthickness=0
        )
        self.nuker_stop_btn.pack(side=tk.LEFT, padx=5)
        self.add_button_hover_effect(self.nuker_stop_btn, "#F04747", "#D84040")
        
        # Stats Bot Section
        stats_frame = tk.LabelFrame(
            tab,
            text="",
            bg="#23272A",
            fg="#5DADE2",
            font=("Segoe UI", 13, "bold"),
            padx=20,
            pady=15,
            relief=tk.FLAT,
            borderwidth=0,
            highlightbackground="#5DADE2",
            highlightthickness=2
        )
        stats_frame.pack(fill=tk.X, padx=15, pady=15)
        self.apply_rounded_style(stats_frame, "#23272A", radius=12)
        
        # Custom header with icon
        stats_header_frame = tk.Frame(stats_frame, bg="#23272A")
        stats_header_frame.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        if self.icons.get('chart'):
            stats_icon_label = tk.Label(stats_header_frame, image=self.icons.get('chart'), bg="#23272A")
            stats_icon_label.pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Label(
            stats_header_frame,
            text="Stats Bot",
            bg="#23272A",
            fg="#5DADE2",
            font=("Segoe UI", 13, "bold")
        ).pack(side=tk.LEFT)
        
        tk.Label(stats_frame, text="Bot Token:", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, pady=8)
        self.stats_token_entry = tk.Entry(stats_frame, width=50, show="*", bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.stats_token_entry.grid(row=1, column=1, padx=10, pady=8)
        self.stats_token_entry.insert(0, self.config["stats_token"])
        
        button_frame2 = tk.Frame(stats_frame, bg="#23272A")
        button_frame2.grid(row=2, column=0, columnspan=2, pady=10)
        
        self.stats_start_btn = tk.Button(
            button_frame2,
            text=" Start Stats Bot",
            image=self.icons.get('play'),
            compound=tk.LEFT,
            bg="#43B581",
            fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            command=lambda: self.animate_button_click(self.stats_start_btn, self.start_stats_bot),
            width=160,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground="#3CA374",
            bd=0,
            highlightthickness=0
        )
        self.stats_start_btn.pack(side=tk.LEFT, padx=5)
        self.add_button_hover_effect(self.stats_start_btn, "#43B581", "#3CA374")
        
        self.stats_stop_btn = tk.Button(
            button_frame2,
            text=" Stop Stats Bot",
            image=self.icons.get('stop'),
            compound=tk.LEFT,
            bg="#F04747",
            fg="#000000",
            font=("Segoe UI", 10, "bold"),
            command=lambda: self.animate_button_click(self.stats_stop_btn, self.stop_stats_bot),
            width=160,
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED,
            activebackground="#D84040",
            disabledforeground="#000000",
            bd=0,
            highlightthickness=0
        )
        self.stats_stop_btn.pack(side=tk.LEFT, padx=5)
        self.add_button_hover_effect(self.stats_stop_btn, "#F04747", "#D84040")
        
        # Status indicators
        status_frame = tk.Frame(tab, bg="#23272A", relief=tk.FLAT, borderwidth=0, highlightthickness=0)
        status_frame.pack(fill=tk.X, padx=15, pady=15)
        self.apply_rounded_style(status_frame, "#23272A", radius=10)
        
        # Nuker status
        nuker_status_container = tk.Frame(status_frame, bg="#2C2F33", relief=tk.FLAT, highlightthickness=0)
        nuker_status_container.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.apply_rounded_style(nuker_status_container, "#2C2F33", radius=8)
        
        # Nuker status with icon
        if self.icons.get('bomb'):
            tk.Label(nuker_status_container, image=self.icons.get('bomb'), bg="#2C2F33").pack(side=tk.LEFT, padx=(10, 5))
        tk.Label(nuker_status_container, text="Nuker Bot:", bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        self.nuker_status_label = tk.Label(nuker_status_container, text="OFFLINE", bg="#2C2F33", fg="#F04747", font=("Segoe UI", 11, "bold"))
        self.nuker_status_label.pack(side=tk.LEFT, padx=5)
        
        # Stats status
        stats_status_container = tk.Frame(status_frame, bg="#2C2F33", relief=tk.FLAT, highlightthickness=0)
        stats_status_container.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.apply_rounded_style(stats_status_container, "#2C2F33", radius=8)
        
        # Stats status with icon
        if self.icons.get('chart'):
            tk.Label(stats_status_container, image=self.icons.get('chart'), bg="#2C2F33").pack(side=tk.LEFT, padx=(10, 5))
        tk.Label(stats_status_container, text="Stats Bot:", bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        self.stats_status_label = tk.Label(stats_status_container, text="OFFLINE", bg="#2C2F33", fg="#F04747", font=("Segoe UI", 11, "bold"))
        self.stats_status_label.pack(side=tk.LEFT, padx=5)
    
    def create_nuker_config_tab(self):
        """Create nuker configuration tab"""
        tab = tk.Frame(self.notebook, bg="#1a1d21")
        self.notebook.add(tab, text="  Nuker Settings  ")
        
        # Create scrollable frame
        canvas = tk.Canvas(tab, bg="#1a1d21")
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#1a1d21")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Server Settings
        server_frame = tk.LabelFrame(
            scrollable_frame,
            text="",
            bg="#23272A",
            fg="#E056FD",
            font=("Segoe UI", 12, "bold"),
            padx=20,
            pady=15,
            relief=tk.FLAT,
            highlightbackground="#E056FD",
            highlightthickness=1
        )
        server_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Server Settings header with icon
        server_header = tk.Frame(server_frame, bg="#23272A")
        server_header.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        if self.icons.get('settings'):
            tk.Label(server_header, image=self.icons.get('settings'), bg="#23272A").pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(server_header, text="Server Settings", bg="#23272A", fg="#E056FD", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        
        tk.Label(server_frame, text="Server Name:", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, pady=8, padx=5)
        self.server_name_entry = tk.Entry(server_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.server_name_entry.grid(row=1, column=1, padx=10, pady=8)
        self.server_name_entry.insert(0, self.config["nuker_config"].get("server_name", "Nuked Server"))
        
        # Channel Settings
        channel_frame = tk.LabelFrame(
            scrollable_frame,
            text="",
            bg="#23272A",
            fg="#FAA61A",
            font=("Segoe UI", 12, "bold"),
            padx=20,
            pady=15,
            relief=tk.FLAT,
            highlightbackground="#FAA61A",
            highlightthickness=1
        )
        channel_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Channel Settings header with icon
        channel_header = tk.Frame(channel_frame, bg="#23272A")
        channel_header.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        if self.icons.get('console'):
            tk.Label(channel_header, image=self.icons.get('console'), bg="#23272A").pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(channel_header, text="Channel Settings", bg="#23272A", fg="#FAA61A", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        
        tk.Label(channel_frame, text="Channel Name:", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, pady=8, padx=5)
        self.channel_name_entry = tk.Entry(channel_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.channel_name_entry.grid(row=1, column=1, padx=10, pady=8)
        self.channel_name_entry.insert(0, self.config["nuker_config"]["channel_name"])
        
        tk.Label(channel_frame, text="Number of Channels:", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=2, column=0, sticky=tk.W, pady=8, padx=5)
        self.channel_count_entry = tk.Entry(channel_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.channel_count_entry.grid(row=2, column=1, padx=10, pady=8)
        self.channel_count_entry.insert(0, str(self.config["nuker_config"]["channel_count"]))
        
        tk.Label(channel_frame, text="Delete Delay (seconds):", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=3, column=0, sticky=tk.W, pady=8, padx=5)
        self.delete_delay_entry = tk.Entry(channel_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.delete_delay_entry.grid(row=3, column=1, padx=10, pady=8)
        self.delete_delay_entry.insert(0, str(self.config["nuker_config"]["delete_delay"]))
        
        tk.Label(channel_frame, text="Create Delay (seconds):", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=4, column=0, sticky=tk.W, pady=8, padx=5)
        self.create_delay_entry = tk.Entry(channel_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.create_delay_entry.grid(row=4, column=1, padx=10, pady=8)
        self.create_delay_entry.insert(0, str(self.config["nuker_config"]["create_delay"]))
        
        # Message Settings
        message_frame = tk.LabelFrame(
            scrollable_frame,
            text="",
            bg="#23272A",
            fg="#A29BFE",
            font=("Segoe UI", 12, "bold"),
            padx=20,
            pady=15,
            relief=tk.FLAT,
            highlightbackground="#A29BFE",
            highlightthickness=1
        )
        message_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Message Settings header with icon
        message_header = tk.Frame(message_frame, bg="#23272A")
        message_header.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        if self.icons.get('info'):
            tk.Label(message_header, image=self.icons.get('info'), bg="#23272A").pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(message_header, text="Message Settings", bg="#23272A", fg="#A29BFE", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        
        tk.Label(message_frame, text="Spam Message:", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, pady=8, padx=5)
        self.spam_message_entry = tk.Entry(message_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.spam_message_entry.grid(row=1, column=1, padx=10, pady=8)
        self.spam_message_entry.insert(0, self.config["nuker_config"]["spam_message"])
        
        tk.Label(message_frame, text="Messages per Channel:", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=2, column=0, sticky=tk.W, pady=8, padx=5)
        self.spam_count_entry = tk.Entry(message_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.spam_count_entry.grid(row=2, column=1, padx=10, pady=8)
        self.spam_count_entry.insert(0, str(self.config["nuker_config"]["message_spam_count"]))
        
        # Role Settings
        role_frame = tk.LabelFrame(
            scrollable_frame,
            text="",
            bg="#23272A",
            fg="#FD79A8",
            font=("Segoe UI", 12, "bold"),
            padx=20,
            pady=15,
            relief=tk.FLAT,
            highlightbackground="#FD79A8",
            highlightthickness=1
        )
        role_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Role Settings header with icon
        role_header = tk.Frame(role_frame, bg="#23272A")
        role_header.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        if self.icons.get('controller'):
            tk.Label(role_header, image=self.icons.get('controller'), bg="#23272A").pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(role_header, text="Role Settings", bg="#23272A", fg="#FD79A8", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        
        tk.Label(role_frame, text="Role Name:", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, pady=8, padx=5)
        self.role_name_entry = tk.Entry(role_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.role_name_entry.grid(row=1, column=1, padx=10, pady=8)
        self.role_name_entry.insert(0, self.config["nuker_config"]["role_name"])
        
        # Stats Channel Settings
        stats_channel_frame = tk.LabelFrame(
            scrollable_frame,
            text="",
            bg="#23272A",
            fg="#55EFC4",
            font=("Segoe UI", 12, "bold"),
            padx=20,
            pady=15,
            relief=tk.FLAT,
            highlightbackground="#55EFC4",
            highlightthickness=1
        )
        stats_channel_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Stats Channel header with icon
        stats_ch_header = tk.Frame(stats_channel_frame, bg="#23272A")
        stats_ch_header.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        if self.icons.get('stats'):
            tk.Label(stats_ch_header, image=self.icons.get('stats'), bg="#23272A").pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(stats_ch_header, text="Stats Channel", bg="#23272A", fg="#55EFC4", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        
        tk.Label(stats_channel_frame, text="Stats Channel ID:", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, pady=8, padx=5)
        self.stats_channel_entry = tk.Entry(stats_channel_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.stats_channel_entry.grid(row=1, column=1, padx=10, pady=8)
        self.stats_channel_entry.insert(0, str(self.config["nuker_config"]["stats_channel_id"]))
        
        # Timer Settings
        timer_frame = tk.LabelFrame(
            scrollable_frame,
            text="",
            bg="#23272A",
            fg="#FFA502",
            font=("Segoe UI", 12, "bold"),
            padx=20,
            pady=15,
            relief=tk.FLAT,
            highlightbackground="#FFA502",
            highlightthickness=1
        )
        timer_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Timer Settings header with icon
        timer_header = tk.Frame(timer_frame, bg="#23272A")
        timer_header.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        if self.icons.get('controller'):
            tk.Label(timer_header, image=self.icons.get('controller'), bg="#23272A").pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(timer_header, text="Timer Settings", bg="#23272A", fg="#FFA502", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        
        tk.Label(timer_frame, text="Smite Cooldown (seconds):", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, pady=8, padx=5)
        self.smite_cooldown_entry = tk.Entry(timer_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.smite_cooldown_entry.grid(row=1, column=1, padx=10, pady=8)
        self.smite_cooldown_entry.insert(0, str(self.config["nuker_config"].get("smite_cooldown", 300)))
        
        tk.Label(timer_frame, text="Auto Leave Delay (seconds):", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=2, column=0, sticky=tk.W, pady=8, padx=5)
        self.auto_leave_entry = tk.Entry(timer_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.auto_leave_entry.grid(row=2, column=1, padx=10, pady=8)
        self.auto_leave_entry.insert(0, str(self.config["nuker_config"].get("auto_leave_delay", 600)))
        
        tk.Label(
            timer_frame,
            text="Bot will leave server after auto-leave delay. Timer resets on each /smite.",
            bg="#23272A",
            fg="#99AAB5",
            font=("Segoe UI", 9, "italic")
        ).grid(row=3, column=0, columnspan=2, pady=8)
        
        # Save button
        save_btn = tk.Button(
            scrollable_frame,
            text=" Save Configuration",
            image=self.icons.get('save'),
            compound=tk.LEFT,
            bg="#7289DA",
            fg="#FFFFFF",
            font=("Segoe UI", 11, "bold"),
            command=self.save_nuker_config,
            width=220,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground="#5B6EAE"
        )
        save_btn.pack(pady=20)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_stats_config_tab(self):
        """Create stats bot configuration tab"""
        tab = tk.Frame(self.notebook, bg="#1a1d21")
        self.notebook.add(tab, text="  Stats Bot Settings  ")
        
        config_frame = tk.LabelFrame(
            tab,
            text="",
            bg="#23272A",
            fg="#74B9FF",
            font=("Segoe UI", 13, "bold"),
            padx=20,
            pady=15,
            relief=tk.FLAT,
            highlightbackground="#74B9FF",
            highlightthickness=1
        )
        config_frame.pack(fill=tk.X, padx=15, pady=15)
        
        # Custom header with icon
        config_header_frame = tk.Frame(config_frame, bg="#23272A")
        config_header_frame.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        if self.icons.get('settings'):
            config_icon_label = tk.Label(config_header_frame, image=self.icons.get('settings'), bg="#23272A")
            config_icon_label.pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Label(
            config_header_frame,
            text="Channel Configuration",
            bg="#23272A",
            fg="#74B9FF",
            font=("Segoe UI", 13, "bold")
        ).pack(side=tk.LEFT)
        
        tk.Label(config_frame, text="Listen Channel ID:", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, pady=8, padx=5)
        self.listen_channel_entry = tk.Entry(config_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.listen_channel_entry.grid(row=1, column=1, padx=10, pady=8)
        self.listen_channel_entry.insert(0, str(self.config["stats_config"]["listen_channel_id"]))
        
        tk.Label(config_frame, text="Relay Channel ID:", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=2, column=0, sticky=tk.W, pady=8, padx=5)
        self.relay_channel_entry = tk.Entry(config_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.relay_channel_entry.grid(row=2, column=1, padx=10, pady=8)
        self.relay_channel_entry.insert(0, str(self.config["stats_config"]["relay_channel_id"]))
        
        tk.Label(config_frame, text="Stats Storage Channel ID:", bg="#23272A", fg="#FFFFFF", font=("Segoe UI", 10)).grid(row=3, column=0, sticky=tk.W, pady=8, padx=5)
        self.stats_storage_channel_entry = tk.Entry(config_frame, width=40, bg="#2C2F33", fg="#FFFFFF", font=("Segoe UI", 10), relief=tk.FLAT, insertbackground="#FFFFFF")
        self.stats_storage_channel_entry.grid(row=3, column=1, padx=10, pady=8)
        stats_channel_value = self.config["stats_config"].get("stats_channel_id", "")
        if stats_channel_value:
            self.stats_storage_channel_entry.insert(0, str(stats_channel_value))
        
        info_text = tk.Text(
            config_frame,
            bg="#23272A",
            fg="#99AAB5",
            font=("Segoe UI", 9, "italic"),
            height=5,
            width=70,
            relief=tk.FLAT,
            wrap=tk.WORD,
            borderwidth=0
        )
        info_text.grid(row=4, column=0, columnspan=2, pady=15, padx=5, sticky=tk.EW)
        info_text.insert("1.0", 
            "Listen Channel: Where nuker bot sends stats\n"
            "Relay Channel: Where stats bot posts formatted stats\n"
            "Stats Storage Channel: Where cumulative stats are stored/updated\n"
            "Type 'check' in console to verify all channels are accessible"
        )
        info_text.config(state=tk.DISABLED)
        
        save_btn = tk.Button(
            config_frame,
            text=" Save Configuration",
            image=self.icons.get('save'),
            compound=tk.LEFT,
            bg="#7289DA",
            fg="#FFFFFF",
            font=("Segoe UI", 11, "bold"),
            command=self.save_stats_config,
            width=220,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground="#5B6EAE"
        )
        save_btn.grid(row=5, column=0, columnspan=2, pady=15)
    
    def create_console_tab(self):
        """Create console output tab"""
        tab = tk.Frame(self.notebook, bg="#1a1d21")
        self.notebook.add(tab, text="  Console  ")
        
        # Console header
        header = tk.Frame(tab, bg="#23272A")
        header.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            header,
            text="Console Output",
            bg="#23272A",
            fg="#FFFFFF",
            font=("Segoe UI", 12, "bold")
        ).pack(side=tk.LEFT, padx=10)
        
        clear_btn = tk.Button(
            header,
            text=" Clear",
            image=self.icons.get('clear'),
            compound=tk.LEFT,
            bg="#F04747",
            fg="#000000",
            font=("Segoe UI", 9, "bold"),
            command=self.clear_console,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground="#D84040"
        )
        clear_btn.pack(side=tk.RIGHT, padx=10)
        
        # Console output area
        console_frame = tk.Frame(tab, bg="#1a1d21")
        console_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
        
        self.console = scrolledtext.ScrolledText(
            console_frame,
            bg="#0D0F11",
            fg="#00FF00",
            font=("Consolas", 9),
            state=tk.DISABLED,
            relief=tk.FLAT,
            insertbackground="#00FF00"
        )
        self.console.pack(fill=tk.BOTH, expand=True)
        
        # Command input area
        input_frame = tk.Frame(tab, bg="#23272A")
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Label(
            input_frame,
            text=">",
            bg="#23272A",
            fg="#00FF00",
            font=("Consolas", 10, "bold")
        ).pack(side=tk.LEFT, padx=(5, 5))
        
        self.console_input = tk.Entry(
            input_frame,
            bg="#0D0F11",
            fg="#00FF00",
            font=("Consolas", 10),
            relief=tk.FLAT,
            insertbackground="#00FF00"
        )
        self.console_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.console_input.bind("<Return>", self.process_console_command)
    
    def setup_console_redirect(self):
        """Redirect print statements to console with color coding"""
        import sys
        
        # Configure text tags for colors
        self.console.tag_config("error", foreground="#FF4444")  # Red for critical errors
        self.console.tag_config("warning", foreground="#FFAA00")  # Yellow/Orange for warnings
        self.console.tag_config("success", foreground="#00FF00")  # Green for success
        self.console.tag_config("normal", foreground="#00FF00")  # Default green
        
        class ConsoleRedirect:
            def __init__(self, text_widget, is_stderr=False):
                self.text_widget = text_widget
                self.is_stderr = is_stderr
            
            def write(self, text):
                if not text or text == "\n":
                    self.text_widget.configure(state=tk.NORMAL)
                    self.text_widget.insert(tk.END, text)
                    self.text_widget.see(tk.END)
                    self.text_widget.configure(state=tk.DISABLED)
                    return
                
                self.text_widget.configure(state=tk.NORMAL)
                
                # Determine color based on content
                tag = "normal"
                text_lower = text.lower()
                
                # Critical errors (red)
                if any(word in text_lower for word in ["error:", "failed:", "exception", "traceback", "critical", "❌"]):
                    # But check if it's a non-critical error
                    if any(word in text_lower for word in ["unclosed connector", "task was destroyed", "event loop is closed"]):
                        tag = "warning"  # These are cleanup warnings, not critical
                    else:
                        tag = "error"
                
                # Warnings (yellow)
                elif any(word in text_lower for word in ["warning", "⚠️", "could not", "cannot"]):
                    tag = "warning"
                
                # Success (green - already default)
                elif any(word in text_lower for word in ["✅", "success", "completed", "online", "logged in"]):
                    tag = "success"
                
                self.text_widget.insert(tk.END, text, tag)
                self.text_widget.see(tk.END)
                self.text_widget.configure(state=tk.DISABLED)
            
            def flush(self):
                pass
        
        sys.stdout = ConsoleRedirect(self.console)
        sys.stderr = ConsoleRedirect(self.console, is_stderr=True)
    
    def clear_console(self):
        """Clear console output"""
        self.console.configure(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.configure(state=tk.DISABLED)
    
    def process_console_command(self, event=None):
        """Process commands entered in the console"""
        command = self.console_input.get().strip().lower()
        self.console_input.delete(0, tk.END)
        
        if not command:
            return
        
        print(f"> {command}")
        
        if command == "check":
            self.check_channels()
        elif command == "data":
            self.check_stats_data()
        elif command == "help":
            print("\nAvailable commands:")
            print("  check - Verify all channel IDs are accessible")
            print("  data  - Display current stats data from storage channel")
            print("  help  - Show this help message")
            print("  clear - Clear console output")
        elif command == "clear":
            self.clear_console()
        else:
            print(f"Unknown command: {command}")
            print("Type 'help' for available commands")
    
    def check_channels(self):
        """Check if all configured channels are accessible"""
        print("\n" + "="*50)
        print("Checking channel accessibility...")
        print("="*50)
        
        # Check if at least one bot is running
        if not self.stats_running and not self.nuker_running:
            print("⚠️ No bots are running. Start at least one bot to check channels.")
            return
        
        # Create async task to check channels
        async def check_all_channels():
            try:
                # Check Nuker Bot Stats Channel
                if self.nuker_running and self.nuker_bot:
                    print("\n[Nuker Bot Channels]")
                    nuker_stats_id = self.config["nuker_config"]["stats_channel_id"]
                    nuker_stats_channel = self.nuker_bot.bot.get_channel(nuker_stats_id)
                    if not nuker_stats_channel:
                        try:
                            nuker_stats_channel = await self.nuker_bot.bot.fetch_channel(nuker_stats_id)
                        except:
                            pass
                    
                    if nuker_stats_channel:
                        print(f"✅ Nuker Stats Channel: #{nuker_stats_channel.name} in {nuker_stats_channel.guild.name}")
                    else:
                        print(f"❌ Nuker Stats Channel (ID: {nuker_stats_id}): NOT ACCESSIBLE")
                        print(f"   This is where the nuker bot sends stats messages!")
                
                # Check Stats Bot Channels
                if self.stats_running and self.stats_bot:
                    print("\n[Stats Bot Channels]")
                    
                    # Check listen channel
                    listen_id = self.config["stats_config"]["listen_channel_id"]
                    listen_channel = self.stats_bot.bot.get_channel(listen_id)
                    if not listen_channel:
                        try:
                            listen_channel = await self.stats_bot.bot.fetch_channel(listen_id)
                        except:
                            pass
                    
                    if listen_channel:
                        print(f"✅ Listen Channel: #{listen_channel.name} in {listen_channel.guild.name}")
                    else:
                        print(f"❌ Listen Channel (ID: {listen_id}): NOT ACCESSIBLE")
                    
                    # Check relay channel
                    relay_id = self.config["stats_config"]["relay_channel_id"]
                    relay_channel = self.stats_bot.bot.get_channel(relay_id)
                    if not relay_channel:
                        try:
                            relay_channel = await self.stats_bot.bot.fetch_channel(relay_id)
                        except:
                            pass
                    
                    if relay_channel:
                        print(f"✅ Relay Channel: #{relay_channel.name} in {relay_channel.guild.name}")
                    else:
                        print(f"❌ Relay Channel (ID: {relay_id}): NOT ACCESSIBLE")
                    
                    # Check stats storage channel
                    stats_id = self.config["stats_config"].get("stats_channel_id")
                    if stats_id:
                        stats_channel = self.stats_bot.bot.get_channel(stats_id)
                        if not stats_channel:
                            try:
                                stats_channel = await self.stats_bot.bot.fetch_channel(stats_id)
                            except:
                                pass
                        
                        if stats_channel:
                            print(f"✅ Stats Storage Channel: #{stats_channel.name} in {stats_channel.guild.name}")
                        else:
                            print(f"❌ Stats Storage Channel (ID: {stats_id}): NOT ACCESSIBLE")
                    else:
                        print(f"⚠️ Stats Storage Channel: Not configured")
                
                print("\n" + "="*50)
                print("Channel check complete!")
                print("="*50 + "\n")
                
            except Exception as e:
                print(f"❌ Error checking channels: {e}")
        
        # Run the async check on whichever bot is running
        if self.nuker_running and self.nuker_loop:
            asyncio.run_coroutine_threadsafe(check_all_channels(), self.nuker_loop)
        elif self.stats_running and self.stats_loop:
            asyncio.run_coroutine_threadsafe(check_all_channels(), self.stats_loop)
    
    def check_stats_data(self):
        """Check and display current stats data from storage channel"""
        print("\n" + "="*50)
        print("Checking stats data...")
        print("="*50)
        
        if not self.stats_running or not self.stats_bot:
            print("⚠️ Stats bot is not running. Start it first to check data.")
            return
        
        # Create async task to check stats
        async def check_stats():
            try:
                stats_id = self.config["stats_config"].get("stats_channel_id")
                
                if not stats_id:
                    print("⚠️ No stats storage channel configured")
                    print("   Configure one in Stats Bot Settings to enable persistent stats")
                    return
                
                # Get the stats channel
                stats_channel = self.stats_bot.bot.get_channel(stats_id)
                if not stats_channel:
                    try:
                        stats_channel = await self.stats_bot.bot.fetch_channel(stats_id)
                    except:
                        pass
                
                if not stats_channel:
                    print(f"❌ Stats storage channel (ID: {stats_id}) not accessible")
                    return
                
                print(f"✅ Stats Channel: #{stats_channel.name} in {stats_channel.guild.name}")
                print()
                
                # Look for ANY stats message
                found_message = False
                async for message in stats_channel.history(limit=10):
                    if "Total servers nuked:" in message.content and "Total members nuked:" in message.content:
                        print("📊 Current Stats Message:")
                        print("-" * 50)
                        print(message.content)
                        print("-" * 50)
                        print(f"Message ID: {message.id}")
                        print(f"Author: {message.author.name}")
                        print(f"Last Updated: {message.edited_at or message.created_at}")
                        found_message = True
                        break
                
                if not found_message:
                    print("⚠️ No stats message found in channel")
                    print("   The bot will create one when the first nuke happens")
                
                # Show current in-memory stats
                print()
                print("💾 In-Memory Stats:")
                print(f"   Total Servers Nuked: {self.stats_bot.stats['total_servers_nuked']}")
                print(f"   Total Members Nuked: {self.stats_bot.stats['total_members_nuked']}")
                
                print("="*50)
                print("Stats data check complete!")
                print("="*50 + "\n")
                
            except Exception as e:
                print(f"❌ Error checking stats data: {e}")
        
        # Run the async check
        if self.stats_loop:
            asyncio.run_coroutine_threadsafe(check_stats(), self.stats_loop)
    
    def animate_button_click(self, button, callback):
        """Animate button click with enhanced scale and glow effect"""
        if str(button['state']) == 'disabled':
            return
        
        original_relief = button.cget('relief')
        original_bg = button.cget('bg')
        original_fg = button.cget('fg')
        active_bg = button.cget('activebackground')
        
        # Multi-stage animation
        def stage1():
            button.config(relief=tk.SUNKEN, bg=active_bg)
        
        def stage2():
            button.config(relief=tk.FLAT)
        
        def stage3():
            # Glow effect - brighten
            button.config(bg=self.brighten_color(active_bg, 1.2))
        
        def stage4():
            button.config(bg=active_bg)
        
        def stage5():
            button.config(bg=original_bg)
            callback()
        
        # Execute animation stages
        stage1()
        self.root.after(30, stage2)
        self.root.after(60, stage3)
        self.root.after(90, stage4)
        self.root.after(120, stage5)
    
    def brighten_color(self, hex_color, factor):
        """Brighten a hex color by a factor"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        rgb = tuple(min(255, int(c * factor)) for c in rgb)
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    
    def add_button_hover_effect(self, button, normal_color, hover_color):
        """Add smooth hover effect to button with transition"""
        button._hover_animation = None
        
        def on_enter(e):
            if str(button['state']) != 'disabled':
                self.smooth_color_transition(button, normal_color, hover_color, steps=5)
        
        def on_leave(e):
            if str(button['state']) != 'disabled':
                self.smooth_color_transition(button, hover_color, normal_color, steps=5)
        
        button.bind('<Enter>', on_enter)
        button.bind('<Leave>', on_leave)
    
    def smooth_color_transition(self, widget, start_color, end_color, steps=10, current_step=0):
        """Smoothly transition between two colors"""
        if current_step >= steps:
            widget.config(bg=end_color)
            return
        
        # Calculate intermediate color
        start_rgb = self.hex_to_rgb(start_color)
        end_rgb = self.hex_to_rgb(end_color)
        
        ratio = current_step / steps
        current_rgb = tuple(
            int(start_rgb[i] + (end_rgb[i] - start_rgb[i]) * ratio)
            for i in range(3)
        )
        
        current_color = f"#{current_rgb[0]:02x}{current_rgb[1]:02x}{current_rgb[2]:02x}"
        widget.config(bg=current_color)
        
        self.root.after(20, lambda: self.smooth_color_transition(
            widget, start_color, end_color, steps, current_step + 1
        ))
    
    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def start_status_pulse(self):
        """Start pulsing animation for online status indicators"""
        self.pulse_status_indicators()
    
    def pulse_status_indicators(self, brightness=1.0, direction=1):
        """Pulse the status indicators when bots are online"""
        # Only pulse if bots are running
        if self.nuker_running or self.stats_running:
            # Calculate new brightness
            brightness += 0.05 * direction
            
            if brightness >= 1.2:
                direction = -1
                brightness = 1.2
            elif brightness <= 0.8:
                direction = 1
                brightness = 0.8
            
            # Apply to online status labels
            if self.nuker_running:
                base_color = self.hex_to_rgb('#43B581')
                new_color = tuple(min(255, int(c * brightness)) for c in base_color)
                self.nuker_status_label.config(fg=f"#{new_color[0]:02x}{new_color[1]:02x}{new_color[2]:02x}")
            
            if self.stats_running:
                base_color = self.hex_to_rgb('#43B581')
                new_color = tuple(min(255, int(c * brightness)) for c in base_color)
                self.stats_status_label.config(fg=f"#{new_color[0]:02x}{new_color[1]:02x}{new_color[2]:02x}")
        
        # Continue animation
        self.pulse_animation_id = self.root.after(50, lambda: self.pulse_status_indicators(brightness, direction))
    
    def save_nuker_config(self):
        """Save nuker configuration"""
        try:
            self.config["nuker_config"]["server_name"] = self.server_name_entry.get()
            self.config["nuker_config"]["channel_name"] = self.channel_name_entry.get()
            self.config["nuker_config"]["channel_count"] = int(self.channel_count_entry.get())
            self.config["nuker_config"]["message_spam_count"] = int(self.spam_count_entry.get())
            self.config["nuker_config"]["spam_message"] = self.spam_message_entry.get()
            self.config["nuker_config"]["role_name"] = self.role_name_entry.get()
            self.config["nuker_config"]["delete_delay"] = float(self.delete_delay_entry.get())
            self.config["nuker_config"]["create_delay"] = float(self.create_delay_entry.get())
            self.config["nuker_config"]["stats_channel_id"] = int(self.stats_channel_entry.get())
            self.config["nuker_config"]["smite_cooldown"] = int(self.smite_cooldown_entry.get())
            self.config["nuker_config"]["auto_leave_delay"] = int(self.auto_leave_entry.get())
            
            if self.nuker_bot:
                self.nuker_bot.update_config(self.config["nuker_config"])
            
            self.save_config()
            messagebox.showinfo("Success", "Nuker configuration saved!")
            print("Nuker configuration updated")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
    
    def save_stats_config(self):
        """Save stats bot configuration"""
        try:
            self.config["stats_config"]["listen_channel_id"] = int(self.listen_channel_entry.get())
            self.config["stats_config"]["relay_channel_id"] = int(self.relay_channel_entry.get())
            
            # Handle stats storage channel (optional)
            stats_storage_value = self.stats_storage_channel_entry.get().strip()
            if stats_storage_value:
                self.config["stats_config"]["stats_channel_id"] = int(stats_storage_value)
            else:
                self.config["stats_config"]["stats_channel_id"] = None
            
            if self.stats_bot:
                self.stats_bot.update_config(self.config["stats_config"])
            
            self.save_config()
            messagebox.showinfo("Success", "Stats bot configuration saved!")
            print("Stats bot configuration updated")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
    
    def start_nuker_bot(self):
        """Start the nuker bot"""
        token = self.nuker_token_entry.get().strip()
        if not token:
            messagebox.showerror("Error", "Please enter a bot token")
            return
        
        self.config["nuker_token"] = token
        self.save_config()
        
        def run_bot():
            self.nuker_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.nuker_loop)
            
            self.nuker_bot = NukerBot()
            self.nuker_bot.update_config(self.config["nuker_config"])
            
            try:
                self.nuker_loop.run_until_complete(self.nuker_bot.start(token))
            except Exception as e:
                print(f"Nuker bot error: {e}")
                self.nuker_running = False
                self.root.after(0, self.update_nuker_ui, False)
        
        self.nuker_running = True
        threading.Thread(target=run_bot, daemon=True).start()
        
        self.update_nuker_ui(True)
        print("Starting nuker bot...")
    
    def stop_nuker_bot(self):
        """Stop the nuker bot"""
        if self.nuker_bot and self.nuker_loop:
            asyncio.run_coroutine_threadsafe(self.nuker_bot.stop(), self.nuker_loop)
            self.nuker_running = False
            self.update_nuker_ui(False)
            print("Stopping nuker bot...")
    
    def start_stats_bot(self):
        """Start the stats bot"""
        token = self.stats_token_entry.get().strip()
        if not token:
            messagebox.showerror("Error", "Please enter a bot token")
            return
        
        self.config["stats_token"] = token
        self.save_config()
        
        def run_bot():
            self.stats_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.stats_loop)
            
            self.stats_bot = StatsBot()
            self.stats_bot.update_config(self.config["stats_config"])
            
            try:
                self.stats_loop.run_until_complete(self.stats_bot.start(token))
            except Exception as e:
                print(f"Stats bot error: {e}")
                self.stats_running = False
                self.root.after(0, self.update_stats_ui, False)
        
        self.stats_running = True
        threading.Thread(target=run_bot, daemon=True).start()
        
        self.update_stats_ui(True)
        print("Starting stats bot...")
    
    def stop_stats_bot(self):
        """Stop the stats bot"""
        if self.stats_bot and self.stats_loop:
            asyncio.run_coroutine_threadsafe(self.stats_bot.stop(), self.stats_loop)
            self.stats_running = False
            self.update_stats_ui(False)
            print("Stopping stats bot...")
    
    def update_nuker_ui(self, running):
        """Update nuker bot UI state with animation"""
        if running:
            # Animate state change
            self.animate_status_change(self.nuker_status_label, "ONLINE", "#43B581")
            self.nuker_start_btn.config(state=tk.DISABLED)
            self.nuker_stop_btn.config(state=tk.NORMAL)
            self.status_bar.config(text="Nuker Bot: Online - Users can now use /smite")
            # Flash the status container
            self.flash_widget(self.nuker_status_label.master, "#2C2F33", "#43B581", 3)
        else:
            self.animate_status_change(self.nuker_status_label, "OFFLINE", "#F04747")
            self.nuker_start_btn.config(state=tk.NORMAL)
            self.nuker_stop_btn.config(state=tk.DISABLED)
            self.status_bar.config(text="Nuker Bot: Offline")
            self.flash_widget(self.nuker_status_label.master, "#2C2F33", "#F04747", 3)
    
    def update_stats_ui(self, running):
        """Update stats bot UI state with animation"""
        if running:
            self.animate_status_change(self.stats_status_label, "ONLINE", "#43B581")
            self.stats_start_btn.config(state=tk.DISABLED)
            self.stats_stop_btn.config(state=tk.NORMAL)
            self.flash_widget(self.stats_status_label.master, "#2C2F33", "#43B581", 3)
        else:
            self.animate_status_change(self.stats_status_label, "OFFLINE", "#F04747")
            self.stats_start_btn.config(state=tk.NORMAL)
            self.stats_stop_btn.config(state=tk.DISABLED)
            self.flash_widget(self.stats_status_label.master, "#2C2F33", "#F04747", 3)
    
    def animate_status_change(self, label, text, color):
        """Animate status label change with fade effect"""
        # Fade out
        def fade_out(alpha=1.0):
            if alpha > 0:
                # Simulate fade by adjusting color brightness
                rgb = self.hex_to_rgb(label.cget('fg'))
                faded = tuple(int(c * alpha) for c in rgb)
                label.config(fg=f"#{faded[0]:02x}{faded[1]:02x}{faded[2]:02x}")
                self.root.after(20, lambda: fade_out(alpha - 0.2))
            else:
                label.config(text=text)
                fade_in()
        
        # Fade in
        def fade_in(alpha=0.0):
            if alpha < 1.0:
                rgb = self.hex_to_rgb(color)
                faded = tuple(int(c * alpha) for c in rgb)
                label.config(fg=f"#{faded[0]:02x}{faded[1]:02x}{faded[2]:02x}")
                self.root.after(20, lambda: fade_in(alpha + 0.2))
            else:
                label.config(fg=color)
        
        fade_out()
    
    def flash_widget(self, widget, normal_color, flash_color, times, current=0):
        """Flash a widget's background color"""
        if current >= times * 2:
            widget.config(bg=normal_color)
            return
        
        color = flash_color if current % 2 == 0 else normal_color
        widget.config(bg=color)
        self.root.after(100, lambda: self.flash_widget(widget, normal_color, flash_color, times, current + 1))
    
    def on_closing(self):
        """Handle window close event - shutdown bots gracefully"""
        # Stop pulse animation
        if self.pulse_animation_id:
            self.root.after_cancel(self.pulse_animation_id)
        
        # Fade out animation
        self.fade_out_and_close()
    
    def fade_out_and_close(self, alpha=1.0):
        """Fade out the window before closing"""
        if alpha > 0:
            alpha -= 0.1
            self.root.attributes('-alpha', alpha)
            self.root.after(20, lambda: self.fade_out_and_close(alpha))
        else:
            self.perform_shutdown()
    
    def perform_shutdown(self):
        """Perform actual shutdown after fade out"""
        print("\n" + "="*50)
        print("Shutting down...")
        print("="*50)
        
        # Stop nuker bot if running
        if self.nuker_running and self.nuker_bot and self.nuker_loop:
            print("Stopping Nuker Bot...")
            try:
                future = asyncio.run_coroutine_threadsafe(self.nuker_bot.bot.close(), self.nuker_loop)
                future.result(timeout=3)  # Wait up to 3 seconds
                self.nuker_running = False
                print("✅ Nuker Bot stopped")
            except Exception as e:
                print(f"⚠️ Error stopping nuker bot: {e}")
        
        # Stop stats bot if running
        if self.stats_running and self.stats_bot and self.stats_loop:
            print("Stopping Stats Bot...")
            try:
                future = asyncio.run_coroutine_threadsafe(self.stats_bot.bot.close(), self.stats_loop)
                future.result(timeout=3)  # Wait up to 3 seconds
                self.stats_running = False
                print("✅ Stats Bot stopped")
            except Exception as e:
                print(f"⚠️ Error stopping stats bot: {e}")
        
        print("Shutdown complete. Goodbye!")
        
        # Destroy the window
        self.root.destroy()

def main():
    root = tk.Tk()
    app = BotGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
