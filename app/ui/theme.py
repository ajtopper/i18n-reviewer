from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QKeyEvent, QPalette
from PySide6.QtWidgets import QApplication
import qtawesome as qta

ThemeMode = Literal["auto", "light", "dark"]
VALID_THEME_MODES: tuple[ThemeMode, ...] = ("auto", "light", "dark")

DEFAULT_ZOOM_FACTOR = 1.0
MIN_ZOOM_FACTOR = 0.8
MAX_ZOOM_FACTOR = 2.0
ZOOM_STEP = 0.1


def clamp_zoom_factor(value: float) -> float:
    """Clamp and quantize a UI zoom factor to supported bounds [0.8, 2.0]."""
    if not math.isfinite(value):
        return DEFAULT_ZOOM_FACTOR
    clamped = max(MIN_ZOOM_FACTOR, min(MAX_ZOOM_FACTOR, float(value)))
    return round(clamped, 1)


@dataclass(frozen=True)
class ThemeTokens:
    """Semantic color tokens derived from the Stitch design for Light and Dark themes."""

    is_dark: bool
    bg_surface: str
    bg_container_lowest: str
    bg_container_low: str
    bg_container: str
    bg_container_high: str
    text_primary: str
    text_secondary: str
    text_muted: str
    border_subtle: str
    primary: str
    primary_hover: str
    on_primary: str
    secondary_container: str
    on_secondary_container: str
    error: str
    error_bg: str
    warning_bg: str
    warning_fg: str
    warning_border: str
    info_bg: str
    info_fg: str
    info_border: str
    stale_bg: str
    stale_fg: str
    stripe_critical: str
    stripe_warning: str
    stripe_info: str
    token_fg: str
    token_bg: str
    token_styles: dict[str, tuple[str, bool, bool]]
    badge_colors: dict[str, tuple[str, str, str]]


LIGHT_TOKENS = ThemeTokens(
    is_dark=False,
    bg_surface="#f8f9fb",
    bg_container_lowest="#ffffff",
    bg_container_low="#f2f4f6",
    bg_container="#edeef0",
    bg_container_high="#e7e8ea",
    text_primary="#191c1e",
    text_secondary="#3e4942",
    text_muted="#5b5f65",
    border_subtle="#d5ddd7",
    primary="#006b49",
    primary_hover="#00875d",
    on_primary="#ffffff",
    secondary_container="#dfe2ea",
    on_secondary_container="#43474d",
    error="#ba1a1a",
    error_bg="#fee2e2",
    warning_bg="#fef3c7",
    warning_fg="#92400e",
    warning_border="#f59e0b",
    info_bg="#dbeafe",
    info_fg="#1e3a8a",
    info_border="#3b82f6",
    stale_bg="#ede9fe",
    stale_fg="#4c1d95",
    stripe_critical="#dc2626",
    stripe_warning="#f59e0b",
    stripe_info="#3b82f6",
    token_fg="#005237",
    token_bg="#dcfce7",
    token_styles={
        "handlebars": ("#7c3aed", True, False),
        "enricher": ("#0f766e", True, False),
        "url": ("#2563eb", False, True),
        "html": ("#b45309", False, False),
        "placeholder": ("#db2777", True, False),
    },
    badge_colors={
        "OK": ("#dcfce7", "OK", "#15803d"),
        "EDITED": ("#fef9c3", "EDITED", "#b45309"),
        "EDITED_OK": ("#fef9c3", "EDITED · OK", "#a16207"),
        "STALE": ("#ede9fe", "STALE", "#6d28d9"),
        "EMPTY": ("#ffedd5", "[empty]", "#c2410c"),
        "MISSING": ("#f3f4f6", "MISSING", "#6b7280"),
        "SAME_AS_BASE": ("#eff6ff", "= base", "#1d4ed8"),
        "ORPHAN": ("#fef3c7", "ORPHAN", "#b45309"),
        "NON_STRING": ("#e5e7eb", "[non-string]", "#4b5563"),
        "CONFLICT": ("#fee2e2", "CONFLICT", "#b91c1c"),
        "REMOVE": ("#fee2e2", "REMOVE", "#b91c1c"),
        "NOT_APPLICABLE": ("#f9fafb", "", ""),
    },
)

DARK_TOKENS = ThemeTokens(
    is_dark=True,
    bg_surface="#111413",
    bg_container_lowest="#181c1b",
    bg_container_low="#1e2321",
    bg_container="#252b28",
    bg_container_high="#2f3633",
    text_primary="#e3e7e4",
    text_secondary="#b6c2bc",
    text_muted="#8b9690",
    border_subtle="#343d39",
    primary="#00875d",
    primary_hover="#00a370",
    on_primary="#ffffff",
    secondary_container="#2d3431",
    on_secondary_container="#c9d2cd",
    error="#ffb4ab",
    error_bg="#451a1a",
    warning_bg="#3a2e10",
    warning_fg="#fcd34d",
    warning_border="#d97706",
    info_bg="#172554",
    info_fg="#bfdbfe",
    info_border="#3b82f6",
    stale_bg="#2e1f47",
    stale_fg="#d7baff",
    stripe_critical="#ef4444",
    stripe_warning="#f59e0b",
    stripe_info="#60a5fa",
    token_fg="#71daaa",
    token_bg="#123829",
    token_styles={
        "handlebars": ("#c4b5fd", True, False),
        "enricher": ("#5eead4", True, False),
        "url": ("#93c5fd", False, True),
        "html": ("#fcd34d", False, False),
        "placeholder": ("#f9a8d4", True, False),
    },
    badge_colors={
        "OK": ("#133a27", "OK", "#15803d"),
        "EDITED": ("#3a2e10", "EDITED", "#b45309"),
        "EDITED_OK": ("#3a2e10", "EDITED · OK", "#a16207"),
        "STALE": ("#2e1f47", "STALE", "#6d28d9"),
        "EMPTY": ("#3f2312", "[empty]", "#c2410c"),
        "MISSING": ("#272b29", "MISSING", "#4b5563"),
        "SAME_AS_BASE": ("#172554", "= base", "#1d4ed8"),
        "ORPHAN": ("#3a2e10", "ORPHAN", "#b45309"),
        "NON_STRING": ("#272b29", "[non-string]", "#4b5563"),
        "CONFLICT": ("#451a1a", "CONFLICT", "#b91c1c"),
        "REMOVE": ("#451a1a", "REMOVE", "#b91c1c"),
        "NOT_APPLICABLE": ("#181c1b", "", ""),
    },
)


def resolve_is_dark(mode: ThemeMode, system_scheme: Qt.ColorScheme | None = None) -> bool:
    """Resolve whether dark tokens should be active for the given mode and OS scheme."""
    if mode == "dark":
        return True
    if mode == "light":
        return False
    scheme = system_scheme
    if scheme is None:
        scheme = QGuiApplication.styleHints().colorScheme()
    return scheme == Qt.ColorScheme.Dark


def tokens_for_mode(mode: ThemeMode, system_scheme: Qt.ColorScheme | None = None) -> ThemeTokens:
    """Return Light or Dark ThemeTokens for the requested mode."""
    return DARK_TOKENS if resolve_is_dark(mode, system_scheme) else LIGHT_TOKENS


def build_palette(tokens: ThemeTokens) -> QPalette:
    """Build a QPalette aligned with the Stitch color tokens."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(tokens.bg_surface))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(tokens.text_primary))
    palette.setColor(QPalette.ColorRole.Base, QColor(tokens.bg_container_lowest))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens.bg_container_low))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(tokens.bg_container))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(tokens.text_primary))
    palette.setColor(QPalette.ColorRole.Text, QColor(tokens.text_primary))
    palette.setColor(QPalette.ColorRole.Button, QColor(tokens.bg_container))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(tokens.text_primary))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(tokens.primary))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(tokens.on_primary))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(tokens.text_muted))
    return palette


def build_qss(tokens: ThemeTokens, zoom: float = DEFAULT_ZOOM_FACTOR) -> str:
    """Build the application QSS stylesheet from ThemeTokens and zoom scale factor."""
    z = clamp_zoom_factor(zoom)

    def _px(base: float, minimum: int = 1) -> int:
        return max(minimum, round(base * z))

    return f"""
    QMainWindow, QDialog, QWidget {{
        background-color: {tokens.bg_surface};
        color: {tokens.text_primary};
        font-family: "Inter", "Segoe UI", sans-serif;
        font-size: {_px(13, 9)}px;
    }}
    QToolBar {{
        background-color: {tokens.bg_container_lowest};
        border-bottom: 1px solid {tokens.border_subtle};
        spacing: {_px(6, 3)}px;
        padding: {_px(6, 3)}px {_px(10, 5)}px;
    }}
    QToolBar QToolButton {{
        background-color: transparent;
        color: {tokens.text_primary};
        border: 1px solid transparent;
        border-radius: {_px(6, 3)}px;
        padding: {_px(4, 2)}px {_px(8, 4)}px;
    }}
    QToolBar QToolButton:hover {{
        background-color: {tokens.bg_container_high};
        border-color: {tokens.border_subtle};
    }}
    QFrame#SidebarPanel {{
        background-color: {tokens.bg_container_low};
        border-right: 1px solid {tokens.border_subtle};
    }}
    QFrame#ContextBar {{
        background-color: {tokens.bg_container_low};
        border-bottom: 1px solid {tokens.border_subtle};
    }}
    QFrame#InspectorPanel {{
        background-color: {tokens.bg_container_low};
        border-left: 1px solid {tokens.border_subtle};
    }}
    QFrame#InspectorCard {{
        background-color: {tokens.bg_container_lowest};
        border: 1px solid {tokens.border_subtle};
        border-radius: {_px(8, 4)}px;
    }}
    QLabel#SectionHeader {{
        color: {tokens.text_muted};
        font-size: {_px(11, 8)}px;
        font-weight: 600;
        text-transform: uppercase;
        background: transparent;
    }}
    QLabel#KeyChip {{
        background-color: {tokens.bg_container_low};
        color: {tokens.primary};
        border-radius: {_px(4, 2)}px;
        padding: {_px(6, 3)}px {_px(8, 4)}px;
        font-family: "JetBrains Mono", "Consolas", monospace;
        font-size: {_px(12, 8)}px;
    }}
    QLabel#PillBadge {{
        background-color: {tokens.secondary_container};
        color: {tokens.on_secondary_container};
        border-radius: {_px(10, 5)}px;
        padding: {_px(2, 1)}px {_px(8, 4)}px;
        font-size: {_px(11, 8)}px;
        font-weight: 600;
    }}
    QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QSpinBox {{
        background-color: {tokens.bg_container_low};
        color: {tokens.text_primary};
        border: 1px solid {tokens.border_subtle};
        border-radius: {_px(6, 3)}px;
        padding: {_px(4, 2)}px {_px(8, 4)}px;
    }}
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
        border: 1px solid {tokens.primary};
        background-color: {tokens.bg_container_lowest};
    }}
    QPushButton {{
        background-color: {tokens.bg_container};
        color: {tokens.text_primary};
        border: 1px solid {tokens.border_subtle};
        border-radius: {_px(6, 3)}px;
        padding: {_px(5, 2)}px {_px(10, 5)}px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {tokens.bg_container_high};
    }}
    QPushButton:checked {{
        background-color: {tokens.secondary_container};
        color: {tokens.on_secondary_container};
        border-color: {tokens.primary};
    }}
    QPushButton#PrimaryCTA {{
        background-color: {tokens.primary};
        color: {tokens.on_primary};
        border: none;
        font-weight: 600;
        padding: {_px(6, 3)}px {_px(12, 6)}px;
    }}
    QPushButton#PrimaryCTA:hover {{
        background-color: {tokens.primary_hover};
    }}
    QPushButton#DangerLink {{
        background-color: transparent;
        border: none;
        color: {tokens.error};
        font-weight: 500;
    }}
    QListWidget {{
        background-color: transparent;
        border: 1px solid {tokens.border_subtle};
        border-radius: {_px(6, 3)}px;
        outline: none;
    }}
    QListWidget::item {{
        padding: {_px(5, 2)}px {_px(8, 4)}px;
        border-radius: {_px(4, 2)}px;
        color: {tokens.text_secondary};
    }}
    QListWidget::item:hover {{
        background-color: {tokens.bg_container_high};
    }}
    QListWidget::item:selected {{
        background-color: {tokens.primary};
        color: {tokens.on_primary};
        font-weight: 600;
    }}
    QTableView {{
        background-color: {tokens.bg_container_lowest};
        alternate-background-color: {tokens.bg_container_low};
        gridline-color: {tokens.border_subtle};
        border: none;
        selection-background-color: {tokens.secondary_container};
        selection-color: {tokens.text_primary};
    }}
    QHeaderView::section {{
        background-color: {tokens.bg_container};
        color: {tokens.text_secondary};
        border: none;
        border-bottom: 1px solid {tokens.border_subtle};
        border-right: 1px solid {tokens.border_subtle};
        padding: {_px(6, 3)}px {_px(8, 4)}px;
        font-size: {_px(11, 8)}px;
        font-weight: 600;
        text-transform: uppercase;
    }}
    QMenu {{
        background-color: {tokens.bg_container_lowest};
        color: {tokens.text_primary};
        border: 1px solid {tokens.border_subtle};
        padding: {_px(4, 2)}px;
    }}
    QMenu::item {{
        padding: {_px(5, 3)}px {_px(14, 8)}px;
        border-radius: {_px(4, 2)}px;
    }}
    QMenu::item:selected {{
        background-color: {tokens.primary};
        color: {tokens.on_primary};
    }}
    QProgressBar {{
        background-color: {tokens.bg_container};
        border: none;
        border-radius: {_px(4, 2)}px;
        height: {_px(8, 4)}px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {tokens.primary};
        border-radius: {_px(4, 2)}px;
    }}
    QStatusBar {{
        background-color: {tokens.bg_container_low};
        border-top: 1px solid {tokens.border_subtle};
        color: {tokens.text_secondary};
    }}
    QPushButton#ZoomPill {{
        background-color: transparent;
        border: 1px solid {tokens.border_subtle};
        border-radius: {_px(4, 2)}px;
        padding: {_px(2, 1)}px {_px(8, 4)}px;
        font-size: {_px(11, 8)}px;
        font-weight: 600;
        color: {tokens.text_secondary};
    }}
    QPushButton#ZoomPill:hover {{
        background-color: {tokens.bg_container_high};
        color: {tokens.text_primary};
    }}
    """


def _read_settings_dict(app_data_dir: Path) -> dict[str, object]:
    settings_path = app_data_dir / "settings.json"
    if not settings_path.exists():
        return {}
    try:
        loaded = json.loads(settings_path.read_text(encoding="utf-8-sig"))
        if isinstance(loaded, dict):
            return loaded
    except (OSError, ValueError):
        pass
    return {}


def _save_settings_key(app_data_dir: Path, key: str, value: object) -> None:
    app_data_dir.mkdir(parents=True, exist_ok=True)
    data = _read_settings_dict(app_data_dir)
    data[key] = value
    settings_path = app_data_dir / "settings.json"
    settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_theme_preference(app_data_dir: Path) -> ThemeMode:
    """Load the persisted ui_theme preference from settings.json, defaulting to 'auto'."""
    val = _read_settings_dict(app_data_dir).get("ui_theme")
    if val in VALID_THEME_MODES:
        return val
    return "auto"


def save_theme_preference(app_data_dir: Path, mode: ThemeMode) -> None:
    """Persist ui_theme into settings.json while preserving existing settings keys."""
    _save_settings_key(app_data_dir, "ui_theme", mode)


def load_zoom_preference(app_data_dir: Path) -> float:
    """Load the persisted ui_zoom factor from settings.json, defaulting to 1.0."""
    val = _read_settings_dict(app_data_dir).get("ui_zoom")
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return clamp_zoom_factor(float(val))
    return DEFAULT_ZOOM_FACTOR


def save_zoom_preference(app_data_dir: Path, zoom: float) -> None:
    """Persist ui_zoom into settings.json while preserving existing settings keys."""
    _save_settings_key(app_data_dir, "ui_zoom", clamp_zoom_factor(zoom))


class ThemeManager(QObject):
    """Applies Native Qt 6 Fusion + QPalette + QSS + UI zoom and tracks OS colorScheme changes."""

    theme_changed = Signal(object)
    zoom_changed = Signal(float)

    def __init__(self, app_data_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.app_data_dir = app_data_dir
        self._mode: ThemeMode = load_theme_preference(app_data_dir)
        self._zoom: float = load_zoom_preference(app_data_dir)
        self._tokens: ThemeTokens = tokens_for_mode(self._mode)
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @property
    def zoom(self) -> float:
        return self._zoom

    @property
    def zoom_percent(self) -> int:
        return round(self._zoom * 100)

    @property
    def tokens(self) -> ThemeTokens:
        return self._tokens

    def apply(self) -> ThemeTokens:
        """Apply Fusion style, QPalette, and scaled QSS to the active QApplication."""
        self._tokens = tokens_for_mode(self._mode)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyle("Fusion")
            app.setPalette(build_palette(self._tokens))
            app.setStyleSheet(build_qss(self._tokens, zoom=self._zoom))
        self.theme_changed.emit(self._tokens)
        self.zoom_changed.emit(self._zoom)
        return self._tokens

    def set_mode(self, mode: ThemeMode, persist: bool = True) -> ThemeTokens:
        """Switch theme mode, optionally persist it, and re-apply to the application."""
        self._mode = mode
        if persist:
            save_theme_preference(self.app_data_dir, mode)
        return self.apply()

    def set_zoom(self, zoom: float, persist: bool = True) -> float:
        """Update UI zoom factor, optionally persist it, and re-apply scaled QSS."""
        clamped = clamp_zoom_factor(zoom)
        changed = clamped != self._zoom
        self._zoom = clamped
        if persist:
            save_zoom_preference(self.app_data_dir, clamped)
        if changed:
            self.apply()
        return self._zoom

    def zoom_in(self, persist: bool = True) -> float:
        """Increase UI zoom by one step."""
        return self.set_zoom(self._zoom + ZOOM_STEP, persist=persist)

    def zoom_out(self, persist: bool = True) -> float:
        """Decrease UI zoom by one step."""
        return self.set_zoom(self._zoom - ZOOM_STEP, persist=persist)

    def reset_zoom(self, persist: bool = True) -> float:
        """Reset UI zoom back to 100%."""
        return self.set_zoom(DEFAULT_ZOOM_FACTOR, persist=persist)

    def _on_system_scheme_changed(self, _scheme: Qt.ColorScheme) -> None:
        if self._mode == "auto":
            self.apply()


def handle_zoom_key_event(event: QKeyEvent, theme_manager: ThemeManager) -> bool:
    """Handle Ctrl++ / Ctrl+= / Ctrl+- / Ctrl+0 zoom shortcuts consistently across windows."""
    mods = event.modifiers()
    if not (mods & Qt.KeyboardModifier.ControlModifier):
        return False
    if mods & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
        return False
    key = event.key()
    if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
        theme_manager.zoom_in()
        return True
    if key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
        theme_manager.zoom_out()
        return True
    if key == Qt.Key.Key_0:
        theme_manager.reset_zoom()
        return True
    return False


def theme_icon(name: str, color: str) -> QIcon:
    """Return a QtAwesome QIcon tinted with the given hex color, or empty QIcon on fallback."""
    try:
        return qta.icon(name, color=color)
    except Exception:  # pragma: no cover - defensive headless font fallback
        return QIcon()
