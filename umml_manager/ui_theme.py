from __future__ import annotations

import configparser
import os
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from typing import Mapping

THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_MODES = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)


@dataclass(frozen=True)
class ThemePalette:
    name: str
    background: str
    sidebar: str
    surface: str
    surface_alt: str
    surface_hover: str
    text: str
    muted: str
    accent: str
    accent_active: str
    accent_soft: str
    secondary: str
    secondary_soft: str
    success: str
    success_soft: str
    warning: str
    warning_soft: str
    danger: str
    danger_soft: str
    border: str
    selection_text: str


LIGHT_PALETTE = ThemePalette(
    name=THEME_LIGHT,
    background="#f7f4ea",
    sidebar="#e8f5e9",
    surface="#fffdf7",
    surface_alt="#f1eee4",
    surface_hover="#e1eadf",
    text="#26342f",
    muted="#66736d",
    accent="#0b7247",
    accent_active="#075c39",
    accent_soft="#d9f2e4",
    secondary="#e65288",
    secondary_soft="#f9dce7",
    success="#188a58",
    success_soft="#d8f0e3",
    warning="#a66a00",
    warning_soft="#f7e8c7",
    danger="#c13f50",
    danger_soft="#f7dce0",
    border="#cad7cd",
    selection_text="#ffffff",
)

DARK_PALETTE = ThemePalette(
    name=THEME_DARK,
    background="#101915",
    sidebar="#13261f",
    surface="#192720",
    surface_alt="#22332b",
    surface_hover="#2b4438",
    text="#f4f7f2",
    muted="#b7c3bc",
    accent="#55d594",
    accent_active="#72e3aa",
    accent_soft="#1f4b38",
    secondary="#f07ca3",
    secondary_soft="#4a2937",
    success="#72dda7",
    success_soft="#214b38",
    warning="#f0c875",
    warning_soft="#4d3e22",
    danger="#f18b98",
    danger_soft="#4c2930",
    border="#375246",
    selection_text="#0e1713",
)

# Compatibility aliases used by a few classic Tk widgets. Dynamic theming updates
# those widgets after construction, so these are only safe initial values.
BACKGROUND = DARK_PALETTE.background
SIDEBAR = DARK_PALETTE.sidebar
SURFACE = DARK_PALETTE.surface
SURFACE_2 = DARK_PALETTE.surface_alt
TEXT = DARK_PALETTE.text
MUTED = DARK_PALETTE.muted
ACCENT = DARK_PALETTE.accent
ACCENT_ACTIVE = DARK_PALETTE.accent_active
SUCCESS = DARK_PALETTE.success
WARNING = DARK_PALETTE.warning
DANGER = DARK_PALETTE.danger


def normalize_theme_mode(value: object) -> str:
    mode = str(value or "").strip().casefold()
    return mode if mode in THEME_MODES else THEME_SYSTEM


def palette_for_mode(mode: str) -> ThemePalette:
    return DARK_PALETTE if normalize_theme_mode(mode) == THEME_DARK else LIGHT_PALETTE


def resolve_theme_mode(
    requested: object,
    *,
    env: Mapping[str, str] | None = None,
    home: str | Path | None = None,
    platform_name: str | None = None,
) -> str:
    mode = normalize_theme_mode(requested)
    if mode != THEME_SYSTEM:
        return mode
    return detect_system_theme(
        env=env,
        home=home,
        platform_name=platform_name,
    )


def detect_system_theme(
    *,
    env: Mapping[str, str] | None = None,
    home: str | Path | None = None,
    platform_name: str | None = None,
) -> str:
    values = os.environ if env is None else env
    platform_value = sys.platform if platform_name is None else platform_name

    override = normalize_theme_mode(values.get("UMML_SYSTEM_THEME", ""))
    if override in {THEME_LIGHT, THEME_DARK}:
        return override

    for key in ("GTK_THEME", "KDE_COLOR_SCHEME", "QT_STYLE_OVERRIDE"):
        detected = _mode_from_name(values.get(key, ""))
        if detected:
            return detected

    if platform_value.startswith("win"):
        detected = _windows_theme()
        if detected:
            return detected

    root = Path(home).expanduser() if home is not None else Path.home()
    for path, detector in (
        (root / ".config" / "kdeglobals", _theme_from_kdeglobals),
        (root / ".config" / "gtk-4.0" / "settings.ini", _theme_from_gtk_settings),
        (root / ".config" / "gtk-3.0" / "settings.ini", _theme_from_gtk_settings),
    ):
        detected = detector(path)
        if detected:
            return detected

    return THEME_LIGHT


def _mode_from_name(value: object) -> str | None:
    name = str(value or "").strip().casefold()
    if not name:
        return None
    if any(marker in name for marker in ("dark", "black", "night")):
        return THEME_DARK
    if any(marker in name for marker in ("light", "white", "day")):
        return THEME_LIGHT
    return None


def _read_config(path: Path) -> configparser.ConfigParser | None:
    if not path.is_file():
        return None
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, UnicodeError, configparser.Error):
        return None
    return parser


def _theme_from_kdeglobals(path: Path) -> str | None:
    parser = _read_config(path)
    if parser is None:
        return None
    general = parser["General"] if parser.has_section("General") else {}
    named = _mode_from_name(general.get("ColorScheme", ""))
    if named:
        return named
    colors = parser["Colors:Window"] if parser.has_section("Colors:Window") else {}
    return _mode_from_rgb(colors.get("BackgroundNormal", ""))


def _theme_from_gtk_settings(path: Path) -> str | None:
    parser = _read_config(path)
    if parser is None or not parser.has_section("Settings"):
        return None
    settings = parser["Settings"]
    prefer_dark = str(settings.get("gtk-application-prefer-dark-theme", "")).strip()
    if prefer_dark in {"1", "true", "True"}:
        return THEME_DARK
    return _mode_from_name(settings.get("gtk-theme-name", ""))


def _mode_from_rgb(value: object) -> str | None:
    pieces = [item.strip() for item in str(value or "").split(",")]
    if len(pieces) != 3:
        return None
    try:
        red, green, blue = (max(0, min(255, int(item))) for item in pieces)
    except ValueError:
        return None
    luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
    return THEME_DARK if luminance < 0.5 else THEME_LIGHT


def _windows_theme() -> str | None:
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return THEME_LIGHT if int(value) else THEME_DARK
    except (ImportError, OSError, TypeError, ValueError):
        return None


def configure_theme(root: tk.Misc, mode: object = THEME_SYSTEM) -> ThemePalette:
    resolved = resolve_theme_mode(mode)
    palette = palette_for_mode(resolved)
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    try:
        root.tk_setPalette(
            background=palette.background,
            foreground=palette.text,
            activeBackground=palette.surface_hover,
            activeForeground=palette.text,
            highlightColor=palette.accent,
            selectBackground=palette.accent,
            selectForeground=palette.selection_text,
        )
    except tk.TclError:
        pass

    try:
        root.configure(background=palette.background)
    except tk.TclError:
        pass

    _configure_ttk_styles(style, palette)
    apply_widget_theme(root, palette, recursive=True)
    return palette


def _configure_ttk_styles(style: ttk.Style, palette: ThemePalette) -> None:
    style.configure(
        ".",
        background=palette.background,
        foreground=palette.text,
        fieldbackground=palette.surface_alt,
        bordercolor=palette.border,
        lightcolor=palette.border,
        darkcolor=palette.border,
        troughcolor=palette.surface_alt,
        focuscolor=palette.accent,
        font=("TkDefaultFont", 10),
    )
    style.configure("TFrame", background=palette.background)
    style.configure("Sidebar.TFrame", background=palette.sidebar)
    style.configure("Surface.TFrame", background=palette.surface)
    style.configure("AccentStripe.TFrame", background=palette.secondary)
    style.configure("TLabel", background=palette.background, foreground=palette.text)
    style.configure("Muted.TLabel", foreground=palette.muted)
    style.configure("Surface.TLabel", background=palette.surface, foreground=palette.text)
    style.configure(
        "SurfaceMuted.TLabel",
        background=palette.surface,
        foreground=palette.muted,
    )
    style.configure(
        "Title.TLabel",
        foreground=palette.accent,
        font=("TkDefaultFont", 23, "bold italic"),
    )
    style.configure(
        "PageTitle.TLabel",
        foreground=palette.text,
        font=("TkDefaultFont", 17, "bold"),
    )
    style.configure(
        "CardTitle.TLabel",
        background=palette.surface,
        foreground=palette.text,
        font=("TkDefaultFont", 11, "bold"),
    )
    style.configure(
        "Badge.TLabel",
        background=palette.surface_alt,
        foreground=palette.text,
        padding=(9, 4),
        font=("TkDefaultFont", 9, "bold"),
    )
    style.configure(
        "Good.Badge.TLabel",
        background=palette.success_soft,
        foreground=palette.success,
        padding=(9, 4),
        font=("TkDefaultFont", 9, "bold"),
    )
    style.configure(
        "Warning.Badge.TLabel",
        background=palette.warning_soft,
        foreground=palette.warning,
        padding=(9, 4),
        font=("TkDefaultFont", 9, "bold"),
    )
    style.configure(
        "TButton",
        background=palette.surface_alt,
        foreground=palette.text,
        padding=(11, 7),
        borderwidth=1,
        relief="flat",
    )
    style.map(
        "TButton",
        background=[
            ("pressed", palette.accent_soft),
            ("active", palette.surface_hover),
            ("disabled", palette.surface),
        ],
        foreground=[("disabled", palette.muted)],
    )
    style.configure(
        "Accent.TButton",
        background=palette.accent,
        foreground=palette.selection_text,
        padding=(13, 8),
        font=("TkDefaultFont", 10, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[
            ("pressed", palette.accent_active),
            ("active", palette.accent_active),
            ("disabled", palette.surface_alt),
        ],
        foreground=[("disabled", palette.muted)],
    )
    style.configure("Danger.TButton", foreground=palette.danger)
    style.map(
        "Danger.TButton",
        background=[("active", palette.danger_soft), ("pressed", palette.danger_soft)],
        foreground=[("active", palette.danger), ("pressed", palette.danger)],
    )
    style.configure(
        "Nav.TButton",
        background=palette.sidebar,
        foreground=palette.muted,
        anchor="w",
        padding=(18, 11),
        borderwidth=0,
    )
    style.map(
        "Nav.TButton",
        background=[("active", palette.surface_hover)],
        foreground=[("active", palette.text)],
    )
    style.configure(
        "Active.Nav.TButton",
        background=palette.accent_soft,
        foreground=palette.accent,
        anchor="w",
        padding=(18, 11),
        font=("TkDefaultFont", 10, "bold"),
        borderwidth=0,
    )
    style.map(
        "Active.Nav.TButton",
        background=[("active", palette.accent_soft)],
        foreground=[("active", palette.accent)],
    )
    style.configure(
        "TLabelframe",
        background=palette.surface,
        foreground=palette.text,
        bordercolor=palette.border,
        lightcolor=palette.border,
        darkcolor=palette.border,
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "TLabelframe.Label",
        background=palette.surface,
        foreground=palette.accent,
        font=("TkDefaultFont", 10, "bold"),
    )
    style.configure(
        "TEntry",
        fieldbackground=palette.surface_alt,
        foreground=palette.text,
        insertcolor=palette.text,
        bordercolor=palette.border,
        padding=7,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", palette.accent)],
        fieldbackground=[("disabled", palette.surface)],
        foreground=[("disabled", palette.muted)],
    )
    style.configure(
        "TCombobox",
        fieldbackground=palette.surface_alt,
        background=palette.surface_alt,
        foreground=palette.text,
        arrowcolor=palette.accent,
        bordercolor=palette.border,
        padding=6,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", palette.surface_alt)],
        selectbackground=[("readonly", palette.surface_alt)],
        selectforeground=[("readonly", palette.text)],
        bordercolor=[("focus", palette.accent)],
    )
    style.configure(
        "Treeview",
        background=palette.surface,
        fieldbackground=palette.surface,
        foreground=palette.text,
        rowheight=31,
        bordercolor=palette.border,
        borderwidth=1,
    )
    style.configure(
        "Treeview.Heading",
        background=palette.surface_alt,
        foreground=palette.text,
        relief="flat",
        padding=8,
        font=("TkDefaultFont", 9, "bold"),
    )
    style.map(
        "Treeview",
        background=[("selected", palette.accent)],
        foreground=[("selected", palette.selection_text)],
    )
    style.map("Treeview.Heading", background=[("active", palette.surface_hover)])
    style.configure("TNotebook", background=palette.background, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=palette.surface_alt,
        foreground=palette.muted,
        padding=(15, 8),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", palette.accent_soft), ("active", palette.surface_hover)],
        foreground=[("selected", palette.accent), ("active", palette.text)],
    )
    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=palette.surface_alt,
        background=palette.secondary,
        bordercolor=palette.border,
    )
    style.configure(
        "TScrollbar",
        background=palette.surface_alt,
        troughcolor=palette.surface,
        arrowcolor=palette.accent,
        bordercolor=palette.border,
    )
    style.configure("TSeparator", background=palette.border)


def apply_widget_theme(
    widget: tk.Misc,
    palette: ThemePalette,
    *,
    recursive: bool = False,
) -> None:
    options: dict[str, object] = {}
    if isinstance(widget, (tk.Tk, tk.Toplevel)):
        options = {"background": palette.background}
    elif isinstance(widget, tk.Text):
        options = {
            "background": palette.surface_alt,
            "foreground": palette.text,
            "insertbackground": palette.text,
            "selectbackground": palette.accent,
            "selectforeground": palette.selection_text,
            "highlightbackground": palette.border,
            "highlightcolor": palette.accent,
        }
    elif isinstance(widget, tk.Listbox):
        options = {
            "background": palette.surface,
            "foreground": palette.text,
            "selectbackground": palette.accent,
            "selectforeground": palette.selection_text,
            "highlightbackground": palette.border,
            "highlightcolor": palette.accent,
        }
    elif isinstance(widget, tk.Canvas):
        options = {
            "background": palette.surface,
            "highlightbackground": palette.border,
        }
    elif isinstance(widget, tk.Frame):
        options = {"background": palette.surface_alt}
    elif isinstance(widget, tk.Label):
        parent_background = palette.surface_alt
        try:
            parent_background = str(widget.master.cget("background"))
        except (AttributeError, tk.TclError):
            pass
        options = {
            "background": parent_background,
            "foreground": palette.text,
        }
    elif isinstance(widget, tk.Entry):
        options = {
            "background": palette.surface_alt,
            "foreground": palette.text,
            "insertbackground": palette.text,
            "selectbackground": palette.accent,
            "selectforeground": palette.selection_text,
        }
    elif isinstance(widget, tk.Menu):
        options = {
            "background": palette.surface,
            "foreground": palette.text,
            "activebackground": palette.accent,
            "activeforeground": palette.selection_text,
        }

    if options:
        try:
            widget.configure(**options)
        except tk.TclError:
            pass

    if recursive:
        try:
            children = widget.winfo_children()
        except tk.TclError:
            children = ()
        for child in children:
            apply_widget_theme(child, palette, recursive=True)
