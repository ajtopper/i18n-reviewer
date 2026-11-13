"""Isolated live-comparison prototype: Stitch-inspired UI on Qt 6 Native vs qt-material.

Run with:
    .venv\\Scripts\\python.exe scripts/ui_prototype.py
"""

from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, QRect, QSize, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPalette, QSyntaxHighlighter, QTextCharFormat, QTextDocument
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

try:
    from qt_material import apply_stylesheet as qt_material_apply_stylesheet
except ImportError:  # pragma: no cover - optional dependency
    qt_material_apply_stylesheet = None


@dataclass(frozen=True)
class ThemeTokens:
    """Color tokens derived from the Stitch mockup for Light and Dark modes."""

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
    token_fg: str
    token_bg: str
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
    token_fg="#005237",
    token_bg="#dcfce7",
    badge_colors={
        "OK": ("#dcfce7", "OK", "#15803d"),
        "EDITED": ("#fef9c3", "EDITED", "#b45309"),
        "STALE": ("#ede9fe", "STALE", "#6d28d9"),
        "EMPTY": ("#ffedd5", "[empty]", "#c2410c"),
        "MISSING": ("#f3f4f6", "MISSING", "#6b7280"),
        "CONFLICT": ("#fee2e2", "CONFLICT", "#b91c1c"),
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
    token_fg="#71daaa",
    token_bg="#123829",
    badge_colors={
        "OK": ("#133a27", "OK", "#71daaa"),
        "EDITED": ("#3a2e10", "EDITED", "#fcd34d"),
        "STALE": ("#2e1f47", "STALE", "#d7baff"),
        "EMPTY": ("#3f2312", "[empty]", "#fdba74"),
        "MISSING": ("#272b29", "MISSING", "#9ca3af"),
        "CONFLICT": ("#451a1a", "CONFLICT", "#fca5a5"),
    },
)


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


def build_native_qss(tokens: ThemeTokens) -> str:
    """Build clean Qt 6 QSS implementing the Stitch hierarchy."""
    return f"""
    QMainWindow, QWidget {{
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
    QLineEdit, QComboBox, QPlainTextEdit {{
        background-color: {tokens.bg_container_low};
        color: {tokens.text_primary};
        border: 1px solid {tokens.border_subtle};
        border-radius: 6px;
        padding: 4px 8px;
    }}
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
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
        border: none;
        outline: none;
    }}
    QListWidget::item {{
        padding: 6px 8px;
        border-radius: 6px;
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


@dataclass
class SampleRow:
    key: str
    file_name: str
    base_text: str
    pt_br: str
    es: str
    pt_status: str
    es_status: str
    glossary_hint: str = ""


SAMPLE_ROWS: list[SampleRow] = [
    SampleRow(
        "HEAVYLORE.Settings.SoundVolume",
        "en.json",
        "Sound volume",
        "Volume dos sons",
        "Volumen de sonido",
        "OK",
        "OK",
    ),
    SampleRow(
        "HEAVYLORE.Settings.PlayersCanBind",
        "en.json",
        "Players may bind books",
        "Jogadores podem encadernar livros",
        "Los jugadores pueden encuadernar",
        "OK",
        "EDITED",
    ),
    SampleRow(
        "HEAVYLORE.Material.rough-leather",
        "items_lore.json",
        "Rough Hide ({count})",
        "Couro Não Curado ({count})",
        "Cuero sin curtir ({count})",
        "OK",
        "STALE",
        "rough-leather -> Couro Não Curado",
    ),
    SampleRow(
        "HEAVYLORE.Material.vellum",
        "items_lore.json",
        "Vellum",
        "Velino",
        "",
        "EDITED",
        "EMPTY",
    ),
    SampleRow(
        "HEAVYLORE.Dialogue.Archivist",
        "dialogues_act_1.json",
        "Welcome to the <b>Library</b>, @UUID[Actor.123]{Archivist}.",
        "Bem-vindo à <b>Biblioteca</b>, @UUID[Actor.123]{Arquivista}.",
        "Bienvenido a la <b>Biblioteca</b>.",
        "STALE",
        "CONFLICT",
    ),
    SampleRow(
        "HEAVYLORE.Dialogue.MissingKey",
        "dialogues_act_1.json",
        "The ink has faded.",
        "",
        "La tinta se ha desvanecido.",
        "MISSING",
        "OK",
    ),
]


class PrototypeTableModel(QAbstractTableModel):
    """Minimal multi-language table model matching i18n-reviewer columns."""

    HEADERS = ("Key", "en (Base)", "pt-BR", "es")

    def __init__(self, rows: list[SampleRow]) -> None:
        super().__init__()
        self._rows = rows

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def row_at(self, row: int) -> SampleRow:
        return self._rows[row]

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        item = self._rows[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return (item.key, item.base_text, item.pt_br, item.es)[col]
        if role == Qt.ItemDataRole.UserRole:
            if col == 2:
                return item.pt_status
            if col == 3:
                return item.es_status
            return ""
        if role == Qt.ItemDataRole.UserRole + 1:
            return item.file_name
        return None


class PrototypeFilterProxy(QSortFilterProxyModel):
    """Filters sample rows by search query, file, and status."""

    def __init__(self) -> None:
        super().__init__()
        self.search_text = ""
        self.file_filter = "All files"
        self.status_filter = "All"

    def set_filters(self, search_text: str, file_filter: str, status_filter: str) -> None:
        self.search_text = search_text.strip().lower()
        self.file_filter = file_filter
        self.status_filter = status_filter
        self.invalidateRowsFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex) -> bool:
        model = self.sourceModel()
        if not isinstance(model, PrototypeTableModel):
            return True
        row = model.row_at(source_row)
        if self.file_filter != "All files" and row.file_name != self.file_filter:
            return False
        statuses = {row.pt_status, row.es_status}
        if self.status_filter == "Pending Only" and not (statuses & {"EMPTY", "MISSING", "STALE", "CONFLICT"}):
            return False
        if self.status_filter == "Edited Only" and "EDITED" not in statuses:
            return False
        if self.status_filter == "All Alerts" and not (statuses & {"STALE", "CONFLICT", "MISSING"}):
            return False
        if self.search_text:
            haystack = f"{row.key} {row.base_text} {row.pt_br} {row.es}".lower()
            return self.search_text in haystack
        return True


class PrototypeStatusDelegate(QStyledItemDelegate):
    """Renders theme-aware status badges on translation cells."""

    def __init__(self, tokens: ThemeTokens, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tokens = tokens

    def set_tokens(self, tokens: ThemeTokens) -> None:
        self.tokens = tokens

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> None:
        status = index.data(Qt.ItemDataRole.UserRole) or ""
        badge = self.tokens.badge_colors.get(status)
        if not badge or index.column() < 2:
            super().paint(painter, option, index)
            return

        bg_hex, label, fg_hex = badge
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(self.tokens.secondary_container))
        else:
            painter.fillRect(option.rect, QColor(bg_hex))

        badge_font = QFont(option.font)
        badge_font.setPointSize(max(8, badge_font.pointSize() - 2))
        badge_font.setBold(True)
        painter.setFont(badge_font)
        painter.setPen(QColor(fg_hex))
        badge_rect = QRect(option.rect.left() + 8, option.rect.top() + 3, option.rect.width() - 16, 16)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)

        painter.setFont(option.font)
        painter.setPen(QColor(self.tokens.text_primary))
        text_rect = option.rect.adjusted(8, 18, -8, -4)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, text)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> QSize:
        base = super().sizeHint(option, index)
        return QSize(base.width(), max(base.height(), 52))


class PrototypeTokenHighlighter(QSyntaxHighlighter):
    """Highlights {vars}, <b> tags, and @UUID[...] tokens using active theme tokens."""

    def __init__(self, doc: QTextDocument, tokens: ThemeTokens) -> None:
        super().__init__(doc)
        self.tokens = tokens

    def set_tokens(self, tokens: ThemeTokens) -> None:
        self.tokens = tokens
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self.tokens.token_fg))
        fmt.setBackground(QColor(self.tokens.token_bg))
        fmt.setFontWeight(QFont.Weight.Bold)
        import re

        for match in re.finditer(r"(\{[^}]+\}|</?[a-zA-Z]+>|@UUID\[[^\]]+\](?:\{[^}]+\})?)", text):
            self.setFormat(match.start(), match.end() - match.start(), fmt)


class PrototypeWindow(QMainWindow):
    """Live comparison window for Qt 6 Native vs qt-material with Stitch layout."""

    THEMES = (
        "Qt 6 Native (Light)",
        "Qt 6 Native (Dark)",
        "Qt 6 Native (Auto)",
        "qt-material (Light Teal)",
        "qt-material (Dark Teal)",
    )

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("i18n-reviewer — UI Prototype (Stitch Adaptation)")
        self.resize(1360, 820)
        self._tokens = LIGHT_TOKENS
        self._model = PrototypeTableModel(SAMPLE_ROWS)
        self._proxy = PrototypeFilterProxy()
        self._proxy.setSourceModel(self._model)

        self._build_toolbar()
        self._build_body()
        self._build_status_bar()
        self.apply_theme("Qt 6 Native (Light)")
        self._select_initial_row()

        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Prototype Controls")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.btn_sidebar = QPushButton("Sidebar")
        self.btn_sidebar.setCheckable(True)
        self.btn_sidebar.setChecked(True)
        self.btn_sidebar.toggled.connect(self._on_toggle_sidebar)
        tb.addWidget(self.btn_sidebar)

        tb.addSeparator()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter keys or text (Ctrl+F)...")
        self.search_input.setMinimumWidth(240)
        self.search_input.textChanged.connect(self._refresh_filters)
        tb.addWidget(self.search_input)

        tb.addWidget(QLabel("  Theme: "))
        self.theme_combo = QComboBox()
        for name in self.THEMES:
            if name.startswith("qt-material") and qt_material_apply_stylesheet is None:
                continue
            self.theme_combo.addItem(name)
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        tb.addWidget(self.theme_combo)

        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding, spacer.sizePolicy().verticalPolicy().Preferred)
        tb.addWidget(spacer)

        tb.addWidget(QPushButton("Glossary..."))
        tb.addWidget(QPushButton("Enricher Rules..."))
        self.btn_publish = QPushButton("Send to Production")
        self.btn_publish.setObjectName("PrimaryCTA")
        tb.addWidget(self.btn_publish)

    def _build_body(self) -> None:
        root = QSplitter(Qt.Orientation.Horizontal)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("SidebarPanel")
        self.sidebar.setFixedWidth(220)
        sb_layout = QVBoxLayout(self.sidebar)
        sb_layout.setContentsMargins(10, 12, 10, 12)
        sb_layout.setSpacing(6)

        lbl_filters = QLabel("Status Filters")
        lbl_filters.setObjectName("SectionHeader")
        sb_layout.addWidget(lbl_filters)
        self.status_list = QListWidget()
        for item_text in ("All", "Pending Only", "Edited Only", "All Alerts"):
            self.status_list.addItem(QListWidgetItem(item_text))
        self.status_list.setCurrentRow(0)
        self.status_list.currentTextChanged.connect(self._refresh_filters)
        sb_layout.addWidget(self.status_list, 1)

        lbl_files = QLabel("Package Files")
        lbl_files.setObjectName("SectionHeader")
        sb_layout.addWidget(lbl_files)
        self.file_list = QListWidget()
        for fname in ("All files", "en.json", "dialogues_act_1.json", "items_lore.json"):
            self.file_list.addItem(QListWidgetItem(fname))
        self.file_list.setCurrentRow(0)
        self.file_list.currentTextChanged.connect(self._refresh_filters)
        sb_layout.addWidget(self.file_list, 1)

        center = QWidget()
        c_layout = QVBoxLayout(center)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        ctx_bar = QFrame()
        ctx_bar.setObjectName("ContextBar")
        ctx_layout = QHBoxLayout(ctx_bar)
        ctx_layout.setContentsMargins(12, 6, 12, 6)
        self.ctx_breadcrumb = QLabel("All files / All")
        self.ctx_count_pill = QLabel("6 keys shown")
        self.ctx_count_pill.setObjectName("PillBadge")
        self.btn_compact = QPushButton("Compact")
        self.btn_compact.setCheckable(True)
        self.btn_compact.toggled.connect(self._on_density_toggled)
        ctx_layout.addWidget(self.ctx_breadcrumb)
        ctx_layout.addWidget(self.ctx_count_pill)
        ctx_layout.addStretch()
        ctx_layout.addWidget(self.btn_compact)
        c_layout.addWidget(ctx_bar)

        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.delegate = PrototypeStatusDelegate(self._tokens, self.table)
        self.table.setItemDelegate(self.delegate)
        self.table.selectionModel().currentRowChanged.connect(self._on_row_selected)
        c_layout.addWidget(self.table, 3)

        editor_box = QFrame()
        editor_box.setObjectName("ContextBar")
        ed_layout = QVBoxLayout(editor_box)
        ed_layout.setContentsMargins(12, 8, 12, 8)
        ed_lbl = QLabel("TokenHighlighter Preview (pt-BR)")
        ed_lbl.setObjectName("SectionHeader")
        self.token_editor = QPlainTextEdit()
        self.token_editor.setMaximumHeight(68)
        self.highlighter = PrototypeTokenHighlighter(self.token_editor.document(), self._tokens)
        ed_layout.addWidget(ed_lbl)
        ed_layout.addWidget(self.token_editor)
        c_layout.addWidget(editor_box)

        self.inspector = QFrame()
        self.inspector.setObjectName("InspectorPanel")
        self.inspector.setMinimumWidth(320)
        self.inspector.setMaximumWidth(380)
        ins_layout = QVBoxLayout(self.inspector)
        ins_layout.setContentsMargins(12, 12, 12, 12)
        ins_layout.setSpacing(10)

        card_meta = QFrame()
        card_meta.setObjectName("InspectorCard")
        cm_layout = QVBoxLayout(card_meta)
        lbl_m = QLabel("Key Metadata & Location")
        lbl_m.setObjectName("SectionHeader")
        self.ins_key = QLabel("Select a row")
        self.ins_key.setObjectName("KeyChip")
        self.ins_key.setWordWrap(True)
        self.ins_file = QLabel("File: -")
        cm_layout.addWidget(lbl_m)
        cm_layout.addWidget(self.ins_key)
        cm_layout.addWidget(self.ins_file)

        card_val = QFrame()
        card_val.setObjectName("InspectorCard")
        cv_layout = QVBoxLayout(card_val)
        lbl_v = QLabel("Validation & Glossary")
        lbl_v.setObjectName("SectionHeader")
        self.ins_expansion_lbl = QLabel("String Expansion: 0%")
        self.ins_progress = QProgressBar()
        self.ins_progress.setRange(0, 200)
        self.ins_glossary = QLabel("No glossary match")
        self.ins_glossary.setWordWrap(True)
        cv_layout.addWidget(lbl_v)
        cv_layout.addWidget(self.ins_expansion_lbl)
        cv_layout.addWidget(self.ins_progress)
        cv_layout.addWidget(self.ins_glossary)

        ins_layout.addWidget(card_meta)
        ins_layout.addWidget(card_val)
        ins_layout.addStretch()

        self.btn_review_next = QPushButton("Mark Reviewed + Next (Ctrl+Enter)")
        self.btn_review_next.setObjectName("PrimaryCTA")
        self.btn_next_pending = QPushButton("Next Pending (Ctrl+Down)")
        self.btn_expanded = QPushButton("Expanded Editor (Shift+F2)")
        self.btn_remove_orphan = QPushButton("Remove orphan key...")
        self.btn_remove_orphan.setObjectName("DangerLink")
        ins_layout.addWidget(self.btn_review_next)
        ins_layout.addWidget(self.btn_next_pending)
        ins_layout.addWidget(self.btn_expanded)
        ins_layout.addWidget(self.btn_remove_orphan)

        root.addWidget(self.sidebar)
        root.addWidget(center)
        root.addWidget(self.inspector)
        root.setStretchFactor(1, 3)
        self.setCentralWidget(root)

    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        self.status_theme_lbl = QLabel("Theme: -")
        sb.addPermanentWidget(self.status_theme_lbl)
        sb.showMessage("Prototype ready — switch themes in the toolbar to compare.")
        self.setStatusBar(sb)

    def _on_toggle_sidebar(self, checked: bool) -> None:
        self.sidebar.setVisible(checked)

    def _on_density_toggled(self, compact: bool) -> None:
        self.table.verticalHeader().setDefaultSectionSize(42 if compact else 56)

    def _refresh_filters(self) -> None:
        file_item = self.file_list.currentItem()
        status_item = self.status_list.currentItem()
        file_name = file_item.text() if file_item else "All files"
        status_name = status_item.text() if status_item else "All"
        self._proxy.set_filters(self.search_input.text(), file_name, status_name)
        self.ctx_breadcrumb.setText(f"{file_name} / {status_name}")
        self.ctx_count_pill.setText(f"{self._proxy.rowCount()} keys shown")

    def _select_initial_row(self) -> None:
        if self._proxy.rowCount() > 2:
            self.table.selectRow(2)
        elif self._proxy.rowCount() > 0:
            self.table.selectRow(0)

    def _on_row_selected(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        src = self._proxy.mapToSource(current)
        row = self._model.row_at(src.row())
        self.ins_key.setText(row.key)
        self.ins_file.setText(f"File: {row.file_name}  |  pt-BR: {row.pt_status}  |  es: {row.es_status}")
        self.token_editor.setPlainText(row.pt_br)
        base_len = max(1, len(row.base_text))
        ratio = int((len(row.pt_br) / base_len) * 100)
        self.ins_expansion_lbl.setText(f"String Expansion: {ratio}% ({len(row.base_text)} -> {len(row.pt_br)} chars)")
        self.ins_progress.setValue(min(200, ratio))
        self.ins_glossary.setText(f"Glossary: {row.glossary_hint}" if row.glossary_hint else "Glossary: no exact term match")

    def _on_system_scheme_changed(self, _scheme: Any) -> None:
        if self.theme_combo.currentText() == "Qt 6 Native (Auto)":
            self.apply_theme("Qt 6 Native (Auto)")

    def apply_theme(self, theme_name: str) -> None:
        """Apply either Qt 6 Native (Fusion+QPalette+QSS) or qt-material live."""
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return

        if theme_name.startswith("qt-material") and qt_material_apply_stylesheet is not None:
            is_dark = "Dark" in theme_name
            self._tokens = DARK_TOKENS if is_dark else LIGHT_TOKENS
            xml = "dark_teal.xml" if is_dark else "light_teal.xml"
            qt_material_apply_stylesheet(app, theme=xml, invert_secondary=not is_dark)
        else:
            if theme_name == "Qt 6 Native (Auto)":
                scheme = QGuiApplication.styleHints().colorScheme()
                is_dark = scheme == Qt.ColorScheme.Dark
            else:
                is_dark = "Dark" in theme_name
            self._tokens = DARK_TOKENS if is_dark else LIGHT_TOKENS
            app.setStyle("Fusion")
            app.setPalette(build_palette(self._tokens))
            app.setStyleSheet(build_native_qss(self._tokens))

        self.delegate.set_tokens(self._tokens)
        self.highlighter.set_tokens(self._tokens)
        self.table.viewport().update()
        self.status_theme_lbl.setText(f"Theme: {theme_name}")


def main() -> int:
    app = QApplication(sys.argv)
    win = PrototypeWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
