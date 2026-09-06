#!/usr/bin/env python
"""RepMark Studio - Tkinter front-end for repmark.exe."""
from __future__ import annotations

import configparser
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import BOTH, BOTTOM, END, LEFT, RIGHT, TOP, VERTICAL, X, Y, BooleanVar, Button, Checkbutton, Entry, Frame, Label, LabelFrame, Menu, PhotoImage, StringVar, Tk, Toplevel, filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import repmark

APP_NAME = "RepMark Studio"
APP_VERSION = repmark.APP_VERSION
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "RepMarkStudio"
CONFIG_FILE = CONFIG_DIR / "settings.ini"


@dataclass(frozen=True)
class ThemePalette:
    app_bg: str
    header_bg: str
    panel_bg: str
    input_bg: str
    log_bg: str
    log_fg: str
    text_fg: str
    help_fg: str
    muted_fg: str
    accent_fg: str
    accent_border: str
    button_bg: str
    primary_button_bg: str
    border: str
    disabled_bg: str
    disabled_fg: str
    ready_bg: str
    busy_bg: str
    tree_selected_bg: str
    tree_selected_fg: str


THEMES: dict[str, ThemePalette] = {
    "Light": ThemePalette(
        app_bg="#f4f2ed",
        header_bg="#eee9e1",
        panel_bg="#f8f7f3",
        input_bg="#ffffff",
        log_bg="#202020",
        log_fg="#f4f4f4",
        text_fg="#2e2e2e",
        help_fg="#555555",
        muted_fg="#7b6b5c",
        accent_fg="#7a4634",
        accent_border="#8b6f5b",
        button_bg="#dcefe2",
        primary_button_bg="#cfe3d6",
        border="#8b6f5b",
        disabled_bg="#e3e3e3",
        disabled_fg="#777777",
        ready_bg="#fff0c7",
        busy_bg="#d9edf7",
        tree_selected_bg="#cfe3d6",
        tree_selected_fg="#000000",
    ),
    "Dark": ThemePalette(
        app_bg="#2D2D2D",
        header_bg="#262626",
        panel_bg="#222222",
        input_bg="#303030",
        log_bg="#181818",
        log_fg="#F0F0F0",
        text_fg="#F0F0F0",
        help_fg="#CDCDCD",
        muted_fg="#B8B8B8",
        accent_fg="#E2B27E",
        accent_border="#CD8434",
        button_bg="#343434",
        primary_button_bg="#3A3A3A",
        border="#9A9A9A",
        disabled_bg="#2B2B2B",
        disabled_fg="#707070",
        ready_bg="#EBAA51",
        busy_bg="#3A3A3A",
        tree_selected_bg="#CD8434",
        tree_selected_fg="#181818",
    ),
}

BG = THEMES["Light"].app_bg
PANEL = THEMES["Light"].panel_bg
BORDER = THEMES["Light"].border
GREEN = THEMES["Light"].button_bg
READY = THEMES["Light"].ready_bg
LOG_BG = THEMES["Light"].log_bg
LOG_FG = THEMES["Light"].log_fg
ACCENT = THEMES["Light"].accent_fg


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundled_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", app_dir())).resolve()


def resource_path(relative: str | Path) -> Path:
    relative = Path(relative)
    for base in (bundled_dir(), app_dir()):
        candidate = base / relative
        if candidate.exists():
            return candidate
    return app_dir() / relative


def app_icon_path() -> Path:
    return resource_path(Path("assets") / "RepMark_RSS.ico")


def banner_image_path() -> Path:
    return resource_path(Path("assets") / "RepMark_RSS.png")


def default_repmark_cmd() -> str:
    for base in (app_dir(), bundled_dir()):
        for name in ("repmark.exe", "repmark"):
            candidate = base / name
            if candidate.exists():
                return str(candidate)
        for name in ("repmark.exe", "repmark"):
            candidate = base / "dist" / name
            if candidate.exists():
                return str(candidate)
    return shutil.which("repmark.exe") or shutil.which("repmark") or str(app_dir() / "repmark.exe")


def safe_open_path(path: Path) -> bool:
    try:
        if hasattr(os, "startfile"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except Exception:
        return False


class RepMarkGui:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title(f"{APP_NAME} {APP_VERSION}")
        self.apply_default_window_size()
        root.configure(bg=BG)
        try:
            root.iconbitmap(default=str(app_icon_path()))
        except Exception:
            pass

        self.config = self.load_config()
        self.yaml_path = StringVar(value=self.config.get("settings", "yaml_path", fallback=str(resource_path("config.yaml"))))
        self.repmark_cmd = StringVar(value=self.resolve_repmark_cmd(self.config.get("settings", "repmark_cmd", fallback="")))
        self.csv_path = StringVar(value=self.config.get("settings", "csv_path", fallback=""))
        self.csv_prefix = StringVar(value=self.config.get("settings", "csv_prefix", fallback="NS"))
        self.draw_bboxes = BooleanVar(value=self.config.getboolean("settings", "draw_bboxes", fallback=False))
        self.log_bboxes = BooleanVar(value=self.config.getboolean("settings", "log_bboxes", fallback=False))
        self.preview_after_run = BooleanVar(value=self.config.getboolean("settings", "preview_after_run", fallback=True))
        self.open_folder_after_run = BooleanVar(value=self.config.getboolean("settings", "open_folder_after_run", fallback=False))
        saved_theme = self.config.get("settings", "theme", fallback="Light")
        self.theme_name = StringVar(value=saved_theme if saved_theme in THEMES else "Light")
        self.worker: threading.Thread | None = None
        self.last_output_path: Path | None = None
        self.banner_image = None

        self.configure_style()
        self.build_ui()
        self.apply_theme()
        self.log_line(f"{APP_NAME} ready. Choose a YAML config, then click Generate Decal.")

    def apply_default_window_size(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(980, max(860, screen_w - 100))
        height = min(820, max(700, screen_h - 80))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 3)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(820, 640)

    def palette(self) -> ThemePalette:
        return THEMES.get(self.theme_name.get(), THEMES["Light"])

    def configure_style(self) -> None:
        colors = self.palette()
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=colors.app_bg)
        style.configure("TLabel", background=colors.app_bg, foreground=colors.text_fg, font=("Segoe UI", 9))
        style.configure("TButton", background=colors.button_bg, foreground=colors.text_fg, bordercolor=colors.border, font=("Segoe UI", 9))
        style.configure("Primary.TButton", background=colors.primary_button_bg, foreground=colors.text_fg, bordercolor=colors.accent_border, font=("Segoe UI", 10, "bold"))
        style.configure("TScrollbar", background=colors.button_bg, troughcolor=colors.app_bg, bordercolor=colors.border, arrowcolor=colors.text_fg)
        style.configure("TMenubutton", background=colors.button_bg, foreground=colors.text_fg, bordercolor=colors.border)
        style.configure(
            "TEntry",
            fieldbackground=colors.input_bg,
            foreground=colors.text_fg,
            insertcolor=colors.text_fg,
            bordercolor=colors.border,
            lightcolor=colors.border,
            darkcolor=colors.border,
        )

    def apply_theme(self) -> None:
        colors = self.palette()
        self.configure_style()
        self.root.configure(bg=colors.app_bg)
        self.apply_theme_to_widget(self.root, colors)
        if hasattr(self, "ready_label"):
            self.set_ready(self.ready_label.cget("text"), busy=self.ready_label.cget("text") == "RUNNING")

    def apply_theme_to_widget(self, widget, colors: ThemePalette) -> None:
        cls = widget.winfo_class()
        parent_bg = colors.app_bg
        try:
            parent = widget.master
            if parent is not None and parent.winfo_class() not in {"Tk", "Toplevel"}:
                parent_bg = parent.cget("bg")
        except Exception:
            pass
        try:
            if cls == "Frame":
                current = widget.cget("bg")
                role_bg = colors.panel_bg if str(current).lower() in {PANEL.lower(), "#222222"} else colors.app_bg
                widget.configure(bg=role_bg, highlightbackground=colors.border)
            elif cls == "Labelframe":
                widget.configure(bg=colors.panel_bg, fg=colors.accent_fg, highlightbackground=colors.border)
            elif cls == "Label":
                current_fg = str(widget.cget("fg")).lower()
                fg = colors.accent_fg if current_fg in {ACCENT.lower(), "#c0925b", "#7b4f3f"} else colors.muted_fg if current_fg in {"#666", "#555", "#7b6b5c"} else colors.text_fg
                widget.configure(bg=parent_bg, fg=fg)
            elif cls in {"Button", "Menubutton"}:
                label = str(widget.cget("text"))
                bg = colors.primary_button_bg if label == "Generate Decal" else colors.button_bg
                if str(widget.cget("state")) == "disabled":
                    bg = colors.disabled_bg
                widget.configure(bg=bg, fg=colors.text_fg, activebackground=colors.accent_border, activeforeground=colors.tree_selected_fg, disabledforeground=colors.disabled_fg, highlightbackground=colors.border)
            elif cls == "Checkbutton":
                widget.configure(bg=parent_bg, fg=colors.text_fg, activebackground=parent_bg, activeforeground=colors.accent_fg, selectcolor=colors.input_bg, highlightbackground=colors.border)
            elif cls == "Entry":
                widget.configure(bg=colors.input_bg, fg=colors.text_fg, insertbackground=colors.text_fg, disabledbackground=colors.disabled_bg, disabledforeground=colors.disabled_fg, highlightbackground=colors.border)
            elif cls == "Text":
                widget.configure(bg=colors.log_bg, fg=colors.log_fg, insertbackground=colors.log_fg)
            elif cls == "Toplevel":
                widget.configure(bg=colors.app_bg)
        except Exception:
            pass
        for child in widget.winfo_children():
            self.apply_theme_to_widget(child, colors)

    def load_config(self) -> configparser.ConfigParser:
        cp = configparser.ConfigParser()
        if CONFIG_FILE.exists():
            cp.read(CONFIG_FILE)
        if not cp.has_section("settings"):
            cp.add_section("settings")
        return cp

    def save_config(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.config.set("settings", "yaml_path", self.yaml_path.get())
        self.config.set("settings", "repmark_cmd", self.repmark_cmd.get())
        self.config.set("settings", "csv_path", self.csv_path.get())
        self.config.set("settings", "csv_prefix", self.csv_prefix.get())
        self.config.set("settings", "draw_bboxes", str(self.draw_bboxes.get()))
        self.config.set("settings", "log_bboxes", str(self.log_bboxes.get()))
        self.config.set("settings", "preview_after_run", str(self.preview_after_run.get()))
        self.config.set("settings", "open_folder_after_run", str(self.open_folder_after_run.get()))
        self.config.set("settings", "theme", self.theme_name.get())
        with CONFIG_FILE.open("w", encoding="utf-8") as f:
            self.config.write(f)

    def resolve_repmark_cmd(self, configured: str) -> str:
        cmd = configured.strip()
        if cmd and (Path(cmd).exists() or shutil.which(cmd)):
            return cmd
        return default_repmark_cmd()

    def build_ui(self) -> None:
        self.content = Frame(self.root, bg=BG)
        self.content.pack(side=TOP, fill=BOTH, expand=True)
        self.build_banner()

        main = Frame(self.content, bg=BG)
        main.pack(fill=BOTH, expand=True, padx=14, pady=(4, 8))
        left = Frame(main, bg=BG)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 6))
        right = Frame(main, bg=BG)
        right.pack(side=RIGHT, fill=BOTH, expand=False, padx=(6, 0))

        self.build_config_panel(left)
        self.build_roster_panel(left)
        self.build_options_panel(left)
        self.build_status_panel(right)
        self.build_settings_panel(right)
        self.build_buttons()
        self.build_log()

    def build_banner(self) -> None:
        banner = Frame(self.content, bg="#eee9e1", highlightbackground=BORDER, highlightthickness=1)
        banner.pack(fill=X, padx=14, pady=(10, 8), ipady=8)
        try:
            self.banner_image = PhotoImage(file=str(banner_image_path())).subsample(4, 4)
            logo = Label(banner, image=self.banner_image, bg="#eee9e1")
        except Exception:
            self.banner_image = None
            logo = Label(banner, text="RM", bg="#3b2a2a", fg="#c0925b", font=("Segoe UI", 18, "bold"), width=5)
        logo.pack(side=LEFT, padx=(18, 10), pady=6)
        title = Frame(banner, bg="#eee9e1")
        title.pack(side=LEFT, fill=X, expand=True)
        Label(title, text=APP_NAME, bg="#eee9e1", fg="#2e2e2e", font=("Segoe UI", 26, "bold")).pack(anchor="w")
        Label(title, text="REPORTING MARK DECAL GENERATOR", bg="#eee9e1", fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        Label(banner, text=f"v{APP_VERSION}", bg="#efefef", fg="#555", relief="groove", padx=8, pady=3).pack(side=RIGHT, padx=14)

    def panel(self, parent: Frame, title: str) -> LabelFrame:
        lf = LabelFrame(parent, text=title, bg=PANEL, fg="#7b4f3f", padx=8, pady=8)
        lf.pack(fill=BOTH, expand=False, pady=(0, 10))
        return lf

    def build_config_panel(self, parent: Frame) -> None:
        lf = self.panel(parent, "Configuration")
        Label(lf, text="YAML config:", bg=PANEL).grid(row=0, column=0, sticky="w")
        Entry(lf, textvariable=self.yaml_path, width=58).grid(row=0, column=1, sticky="ew", padx=(6, 6))
        Button(lf, text="Browse...", command=self.browse_yaml).grid(row=0, column=2, padx=(0, 4))
        Button(lf, text="Recent ▾", command=self.show_recent_menu).grid(row=0, column=3)
        Button(lf, text="New Default Config", command=self.create_default_config).grid(row=1, column=1, sticky="w", padx=(6, 4), pady=(8, 0))
        Button(lf, text="Edit Config", command=self.open_config).grid(row=1, column=1, sticky="e", padx=(4, 4), pady=(8, 0))
        Button(lf, text="Open Config Folder", command=self.open_config_folder).grid(row=1, column=2, columnspan=2, sticky="ew", pady=(8, 0))
        lf.columnconfigure(1, weight=1)

    def build_roster_panel(self, parent: Frame) -> None:
        lf = self.panel(parent, "Optional CSV Roster")
        Label(lf, text="CSV roster:", bg=PANEL).grid(row=0, column=0, sticky="w")
        Entry(lf, textvariable=self.csv_path, width=58).grid(row=0, column=1, sticky="ew", padx=(6, 6))
        Button(lf, text="Browse...", command=self.browse_csv).grid(row=0, column=2, padx=(0, 4))
        Button(lf, text="Clear", command=lambda: self.csv_path.set("")).grid(row=0, column=3)
        Label(lf, text="Prefix:", bg=PANEL).grid(row=1, column=0, sticky="w", pady=(8, 0))
        Entry(lf, textvariable=self.csv_prefix, width=10).grid(row=1, column=1, sticky="w", padx=(6, 6), pady=(8, 0))
        Label(lf, text="One-column CSV files use this prefix; header CSV files may supply their own prefix column.", bg=PANEL, fg="#666").grid(row=2, column=1, columnspan=3, sticky="w", padx=(6, 0), pady=(4, 0))
        lf.columnconfigure(1, weight=1)

    def build_options_panel(self, parent: Frame) -> None:
        lf = self.panel(parent, "Run Options")
        Checkbutton(lf, text="Draw red debug boxes", variable=self.draw_bboxes, bg=PANEL).grid(row=0, column=0, sticky="w", pady=2)
        Checkbutton(lf, text="Print bounding boxes to log", variable=self.log_bboxes, bg=PANEL).grid(row=1, column=0, sticky="w", pady=2)
        Checkbutton(lf, text="Preview image after generation", variable=self.preview_after_run, bg=PANEL).grid(row=2, column=0, sticky="w", pady=2)
        Checkbutton(lf, text="Open output folder after generation", variable=self.open_folder_after_run, bg=PANEL).grid(row=3, column=0, sticky="w", pady=2)
        theme_row = Frame(lf, bg=PANEL)
        theme_row.grid(row=4, column=0, sticky="w", pady=(8, 0))
        Label(theme_row, text="Theme:", bg=PANEL).pack(side=LEFT)
        self.theme_menu = ttk.OptionMenu(theme_row, self.theme_name, self.theme_name.get(), *THEMES.keys(), command=self.change_theme)
        self.theme_menu.pack(side=LEFT, padx=(6, 0))

    def build_status_panel(self, parent: Frame) -> None:
        lf = self.panel(parent, "Status")
        self.ready_label = Label(lf, text="READY", bg=READY, relief="groove", width=26, pady=5)
        self.ready_label.pack(fill=X, pady=(0, 8))
        self.output_label_var = StringVar(value="No output generated yet")
        Label(lf, text="Last output:", bg=PANEL, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        Label(lf, textvariable=self.output_label_var, bg=PANEL, fg="#666", wraplength=260, justify="left").pack(fill=X, anchor="w", pady=(2, 8))
        Button(lf, text="Open Last Image", command=self.open_last_output).pack(fill=X, pady=(0, 4))
        Button(lf, text="Open Last Folder", command=self.open_last_folder).pack(fill=X)

    def build_settings_panel(self, parent: Frame) -> None:
        lf = self.panel(parent, "Program Settings")
        Label(lf, text="repmark.exe:", bg=PANEL).grid(row=0, column=0, sticky="w")
        Entry(lf, textvariable=self.repmark_cmd, width=34).grid(row=0, column=1, sticky="ew", padx=(5, 5))
        Button(lf, text="Browse...", command=self.browse_repmark).grid(row=0, column=2)
        Label(lf, text="The GUI calls repmark.exe as a standalone command-line tool.", bg=PANEL, fg="#666").grid(row=1, column=1, columnspan=2, sticky="w", padx=(5, 0), pady=(6, 0))
        lf.columnconfigure(1, weight=1)

    def build_buttons(self) -> None:
        row = Frame(self.root, bg=BG)
        row.pack(side=BOTTOM, fill=X, padx=18, pady=(0, 8))
        self.generate_button = Button(row, text="Generate Decal", bg=GREEN, width=16, command=self.generate)
        self.generate_button.pack(side=LEFT, padx=(0, 8))
        Button(row, text="Clear Log", bg=GREEN, width=10, command=self.clear_log).pack(side=LEFT, padx=(0, 8))
        Button(row, text="Copy Log", bg=GREEN, width=10, command=self.copy_log).pack(side=LEFT, padx=(0, 8))
        Button(row, text="Exit", bg=GREEN, width=10, command=self.root.destroy).pack(side=LEFT, padx=(0, 8))
        Button(row, text="Help", bg=GREEN, width=10, command=self.show_help).pack(side=RIGHT, padx=(8, 0))

    def build_log(self) -> None:
        log_panel = LabelFrame(self.root, text="RepMark Output Log", bg=BG, fg="#7b4f3f", padx=6, pady=6)
        log_panel.pack(side=BOTTOM, fill=BOTH, expand=True, padx=18, pady=(0, 6))
        self.log = ScrolledText(log_panel, bg=LOG_BG, fg=LOG_FG, insertbackground=LOG_FG, height=14, wrap="word")
        self.log.pack(fill=BOTH, expand=True)
        self.log.config(state="disabled")

    def change_theme(self, *_args) -> None:
        self.save_config()
        self.apply_theme()

    def set_ready(self, text: str, busy: bool = False) -> None:
        colors = self.palette()
        self.ready_label.config(text=text, bg=(colors.busy_bg if busy else colors.ready_bg), fg=colors.text_fg)
        self.generate_button.config(state=("disabled" if busy else "normal"), bg=(colors.disabled_bg if busy else colors.primary_button_bg))

    def log_line(self, text: str) -> None:
        self.log.config(state="normal")
        self.log.insert(END, text.rstrip() + "\n")
        self.log.see(END)
        self.log.config(state="disabled")

    def clear_log(self) -> None:
        self.log.config(state="normal")
        self.log.delete("1.0", END)
        self.log.config(state="disabled")

    def copy_log(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log.get("1.0", END).rstrip())
        self.log_line("[RepMark] Log copied to clipboard.")

    def browse_yaml(self) -> None:
        path = filedialog.askopenfilename(parent=self.root, initialdir=str(Path(self.yaml_path.get() or app_dir()).parent), title="Select repmark YAML config", filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*")])
        if path:
            self.yaml_path.set(path)
            self.save_recent(path)

    def browse_csv(self) -> None:
        start = Path(self.csv_path.get() or self.yaml_path.get() or app_dir()).expanduser()
        initialdir = str(start.parent if start.suffix else start)
        path = filedialog.askopenfilename(parent=self.root, initialdir=initialdir, title="Select reporting mark CSV roster", filetypes=[("CSV files", "*.csv"), ("All files", "*")])
        if path:
            self.csv_path.set(path)
            self.save_config()

    def browse_repmark(self) -> None:
        path = filedialog.askopenfilename(parent=self.root, initialdir=str(app_dir()), title="Select repmark.exe", filetypes=[("RepMark executable", "repmark.exe"), ("Executable", "*.exe"), ("All files", "*")])
        if path:
            self.repmark_cmd.set(path)
            self.save_config()

    def save_recent(self, path: str) -> None:
        old = [p for p in self.config.get("settings", "recent", fallback="").split("|") if p and p != path]
        recent = [path, *old][:8]
        self.config.set("settings", "recent", "|".join(recent))
        self.save_config()

    def show_recent_menu(self) -> None:
        menu = Menu(self.root, tearoff=0)
        recent = [p for p in self.config.get("settings", "recent", fallback="").split("|") if p]
        if not recent:
            menu.add_command(label="No recent configs", state="disabled")
        for path in recent:
            menu.add_command(label=path, command=lambda p=path: self.select_recent(p))
        menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def select_recent(self, path: str) -> None:
        self.yaml_path.set(path)
        self.save_config()

    def create_default_config(self) -> None:
        path = filedialog.asksaveasfilename(parent=self.root, initialdir=str(app_dir()), initialfile="config.yaml", defaultextension=".yaml", filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*")], title="Create default repmark config")
        if not path:
            return
        target = Path(path)
        if target.exists() and not messagebox.askyesno("Replace config?", f"Replace existing config?\n\n{target}", parent=self.root):
            return
        if target.exists():
            target.unlink()
        self.yaml_path.set(str(target))
        self.run_repmark(extra_args=[], create_only=True)

    def open_config(self) -> None:
        path = Path(self.yaml_path.get()).expanduser()
        if not path.exists():
            messagebox.showwarning("Config not found", f"Config file does not exist yet:\n\n{path}", parent=self.root)
            return
        if not safe_open_path(path):
            messagebox.showerror("Open failed", f"Could not open config file:\n\n{path}", parent=self.root)

    def open_config_folder(self) -> None:
        path = Path(self.yaml_path.get()).expanduser()
        folder = path.parent if path.name else app_dir()
        if not safe_open_path(folder):
            messagebox.showerror("Open failed", f"Could not open folder:\n\n{folder}", parent=self.root)

    def open_last_output(self) -> None:
        if not self.last_output_path or not self.last_output_path.exists():
            messagebox.showinfo("No output", "No generated output image has been found yet.", parent=self.root)
            return
        if not safe_open_path(self.last_output_path):
            messagebox.showerror("Open failed", f"Could not open image:\n\n{self.last_output_path}", parent=self.root)

    def open_last_folder(self) -> None:
        if not self.last_output_path:
            messagebox.showinfo("No output", "No generated output folder has been found yet.", parent=self.root)
            return
        if not safe_open_path(self.last_output_path.parent):
            messagebox.showerror("Open failed", f"Could not open folder:\n\n{self.last_output_path.parent}", parent=self.root)

    def build_command(self, extra_args: list[str] | None = None, include_run_options: bool = True) -> list[str]:
        cmd = [self.repmark_cmd.get(), "--yaml", self.yaml_path.get()]
        if self.csv_path.get().strip():
            cmd.extend(["--csv", self.csv_path.get().strip()])
        if self.csv_prefix.get().strip():
            cmd.extend(["--prefix", self.csv_prefix.get().strip()])
        if include_run_options and self.draw_bboxes.get():
            cmd.append("--draw-bboxes")
        if include_run_options and self.log_bboxes.get():
            cmd.append("--log-bboxes")
        if include_run_options and self.preview_after_run.get():
            cmd.append("--preview")
        if extra_args:
            cmd.extend(extra_args)
        return cmd

    def generate(self) -> None:
        self.run_repmark(extra_args=[])

    def run_repmark(self, extra_args: list[str], create_only: bool = False) -> None:
        self.save_config()
        repmark_cmd = self.repmark_cmd.get().strip()
        if not repmark_cmd or not (Path(repmark_cmd).exists() or shutil.which(repmark_cmd)):
            messagebox.showerror("repmark.exe not found", f"Could not find repmark.exe:\n\n{repmark_cmd}", parent=self.root)
            return
        self.clear_log()
        self.set_ready("RUNNING", busy=True)
        self.worker = threading.Thread(target=self.run_worker, args=(extra_args, create_only), daemon=True)
        self.worker.start()

    def run_worker(self, extra_args: list[str], create_only: bool) -> None:
        cmd = self.build_command(extra_args, include_run_options=not create_only)
        cwd = app_dir()
        self.root.after(0, self.log_line, "-" * 72)
        self.root.after(0, self.log_line, f"[RepMark] Working folder: {cwd}")
        self.root.after(0, self.log_line, f"[RepMark] Command: {subprocess.list2cmdline(cmd)}")
        output_lines: list[str] = []
        return_code = 1
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", creationflags=creationflags)
            assert proc.stdout is not None
            for line in proc.stdout:
                stripped = line.rstrip()
                output_lines.append(stripped)
                self.root.after(0, self.log_line, stripped)
            return_code = proc.wait()
        except Exception as exc:
            output_lines.append(f"FAILED: {exc}")
            self.root.after(0, self.log_line, f"FAILED: {exc}")
        self.root.after(0, self.finish_run, return_code, output_lines, create_only)

    def finish_run(self, return_code: int, output_lines: list[str], create_only: bool) -> None:
        self.log_line(f"[RepMark exit code: {return_code}]")
        self.set_ready("READY" if return_code == 0 else "ERROR")
        self.last_output_path = self.find_output_path(output_lines)
        if self.last_output_path:
            self.output_label_var.set(str(self.last_output_path))
        if return_code == 0:
            self.save_recent(self.yaml_path.get())
            if self.open_folder_after_run.get() and self.last_output_path:
                safe_open_path(self.last_output_path.parent)
            if create_only:
                messagebox.showinfo("Config created", f"Default config created:\n\n{self.yaml_path.get()}", parent=self.root)
            else:
                messagebox.showinfo("RepMark complete", "Decal generation completed successfully.", parent=self.root)
        else:
            messagebox.showerror("RepMark failed", "Decal generation failed. See the output log for details.", parent=self.root)

    def find_output_path(self, output_lines: list[str]) -> Path | None:
        marker = "Output saved to "
        for line in reversed(output_lines):
            if marker in line:
                raw = line.split(marker, 1)[1].strip()
                path = Path(raw)
                if not path.is_absolute():
                    path = app_dir() / path
                return path.resolve()
        return None

    def show_help(self) -> None:
        colors = self.palette()
        win = Toplevel(self.root)
        win.title(f"{APP_NAME} Help")
        win.configure(bg=colors.app_bg)
        text = ScrolledText(win, width=88, height=28, bg=colors.log_bg, fg=colors.log_fg, insertbackground=colors.log_fg)
        text.pack(fill=BOTH, expand=True, padx=8, pady=8)
        text.insert(END, f"""{APP_NAME} {APP_VERSION}\n\nThis is a focused front-end for repmark.exe. It keeps the command-line EXE as the source of truth and runs it in the background so the GUI stays responsive.\n\nWorkflow:\n  1. Choose a YAML config.\n  2. Optionally choose a CSV roster and reporting mark prefix.\n  3. Select debug/output options.\n  4. Click Generate Decal.\n  5. Review validation messages, layout warnings, and generated file paths in the log.\n\nTips:\n  - Use Draw red debug boxes when positioning text.\n  - Use Print bounding boxes to log when placing decals in Blender/Open Rails.\n  - Use New Default Config to create a starter YAML file.\n  - A one-column CSV can contain only numbers; the Prefix field supplies NS or another reporting mark.\n  - The default output folder is out/ beside the running EXE.\n""")
        text.config(state="disabled")


def run_self_tests() -> int:
    assert app_icon_path().name == "RepMark_RSS.ico"
    assert banner_image_path().name == "RepMark_RSS.png"
    repmark_cmd = default_repmark_cmd()
    assert repmark_cmd.endswith(("repmark.exe", "repmark"))
    if getattr(sys, "frozen", False):
        assert Path(repmark_cmd).exists()
    assert THEMES["Light"].app_bg == "#f4f2ed"
    assert THEMES["Dark"].input_bg == "#303030"
    cmd = ["repmark.exe", "--yaml", "config.yaml", "--preview"]
    assert "--preview" in cmd
    assert repmark.reporting_marks_to_lines([("NS", "998235")]) == (["998 235"], [{"value": "NS 998235", "stacked": True}])
    print("repmark gui self-tests passed")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return run_self_tests()
    root = Tk()
    RepMarkGui(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
