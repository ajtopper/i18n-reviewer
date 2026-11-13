from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPalette
from PySide6.QtWidgets import QApplication
import qtawesome as qta

ThemeMode = Literal["auto", "light", "dark"]
VALID_THEME_MODES: tuple[ThemeMode, ...] = ("auto", "light", "dark")


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


def build_qss(tokens: ThemeTokens) -> str:
    """Build the application QSS stylesheet from ThemeTokens."""
    return f"""
    QMainWindow, QDialog, QWidget {{
        background-color: {tokens.bg_surface};
        color: {tokens.text_primary};
        font-family: "Inter", "Segoe UI", sans-serif;
        font-size: 13px;
    }}
    QToolBar {{
        background-color: {tokens.bg_container_lowest};
        border-bottom: 1px solid {tokens.border_subtle};
        spacing: 6px;
        padding: 6px 10px;
    }}
    QToolBar QToolButton {{
        background-color: transparent;
        color: {tokens.text_primary};
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 4px 8px;
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
        border-radius: 8px;
    }}
    QLabel#SectionHeader {{
        color: {tokens.text_muted};
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        background: transparent;
    }}
    QLabel#KeyChip {{
        background-color: {tokens.bg_container_low};
        color: {tokens.primary};
        border-radius: 4px;
        padding: 6px 8px;
        font-family: "JetBrains Mono", "Consolas", monospace;
        font-size: 12px;
    }}
    QLabel#PillBadge {{
        background-color: {tokens.secondary_container};
        color: {tokens.on_secondary_container};
        border-radius: 10px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 600;
    }}
    QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QSpinBox {{
        background-color: {tokens.bg_container_low};
        color: {tokens.text_primary};
        border: 1px solid {tokens.border_subtle};
        border-radius: 6px;
        padding: 4px 8px;
    }}
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
        border: 1px solid {tokens.primary};
        background-color: {tokens.bg_container_lowest};
    }}
    QPushButton {{
        background-color: {tokens.bg_container};
        color: {tokens.text_primary};
        border: 1px solid {tokens.border_subtle};
        border-radius: 6px;
        padding: 5px 10px;
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
        padding: 6px 12px;
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
        border-radius: 6px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 5px 8px;
        border-radius: 4px;
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
        padding: 6px 8px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
    }}
    QProgressBar {{
        background-color: {tokens.bg_container};
        border: none;
        border-radius: 4px;
        height: 8px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {tokens.primary};
        border-radius: 4px;
    }}
    QStatusBar {{
        background-color: {tokens.bg_container_low};
        border-top: 1px solid {tokens.border_subtle};
        color: {tokens.text_secondary};
    }}
    """


def load_theme_preference(app_data_dir: Path) -> ThemeMode:
    """Load the persisted ui_theme preference from settings.json, defaulting to 'auto'."""
    settings_path = app_data_dir / "settings.json"
    if not settings_path.exists():
        return "auto"
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8-sig"))
        val = data.get("ui_theme")
        if val in VALID_THEME_MODES:
            return val
    except (OSError, ValueError):
        pass
    return "auto"


def save_theme_preference(app_data_dir: Path, mode: ThemeMode) -> None:
    """Persist ui_theme into settings.json while preserving existing settings keys."""
    app_data_dir.mkdir(parents=True, exist_ok=True)
    settings_path = app_data_dir / "settings.json"
    data: dict[str, object] = {}
    if settings_path.exists():
        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            data = {}
    data["ui_theme"] = mode
    settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class ThemeManager(QObject):
    """Applies Native Qt 6 Fusion + QPalette + QSS and tracks OS colorScheme changes."""

    theme_changed = Signal(object)

    def __init__(self, app_data_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.app_data_dir = app_data_dir
        self._mode: ThemeMode = load_theme_preference(app_data_dir)
        self._tokens: ThemeTokens = tokens_for_mode(self._mode)
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @property
    def tokens(self) -> ThemeTokens:
        return self._tokens

    def apply(self) -> ThemeTokens:
        """Apply Fusion style, QPalette, and QSS to the active QApplication."""
        self._tokens = tokens_for_mode(self._mode)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyle("Fusion")
            app.setPalette(build_palette(self._tokens))
            app.setStyleSheet(build_qss(self._tokens))
        self.theme_changed.emit(self._tokens)
        return self._tokens

    def set_mode(self, mode: ThemeMode, persist: bool = True) -> ThemeTokens:
        """Switch theme mode, optionally persist it, and re-apply to the application."""
        self._mode = mode
        if persist:
            save_theme_preference(self.app_data_dir, mode)
        return self.apply()

    def _on_system_scheme_changed(self, _scheme: Qt.ColorScheme) -> None:
        if self._mode == "auto":
            self.apply()


def theme_icon(name: str, color: str) -> QIcon:
    """Return a QtAwesome QIcon tinted with the given hex color, or empty QIcon on fallback."""
    try:
        return qta.icon(name, color=color)
    except Exception:  # pragma: no cover - defensive headless font fallback
        return QIcon()
