from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.core.project_manager import (
    CellKind,
    ManifestInfo,
    ManifestLangEntry,
    PackageSession,
    discover_manifest,
    load_package_session,
)
from app.ui.delegates import StatusCellDelegate
from app.ui.table_model import PackageFilterProxyModel, TranslationTableModel


class OpenPackageDialog(QDialog):
    """Dialog for selecting base language, optional external base, and conditional entries."""

    def __init__(self, manifest: ManifestInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Configurar pacote: {manifest.package_id}")
        self.resize(520, 380)
        self.manifest = manifest
        self.external_base_path: Path | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.base_combo = QComboBox()
        editable_langs: list[str] = []
        for entry in manifest.entries:
            if entry.editable and entry.lang not in editable_langs:
                editable_langs.append(entry.lang)
                self.base_combo.addItem(f"{entry.lang} ({entry.name})", entry.lang)
        if manifest.default_base_lang:
            idx = self.base_combo.findData(manifest.default_base_lang)
            if idx >= 0:
                self.base_combo.setCurrentIndex(idx)
        form.addRow("Idioma base:", self.base_combo)

        ext_row = QHBoxLayout()
        self.ext_label = QLabel("(nenhum — usar do manifest)")
        btn_ext = QPushButton("Escolher JSON externo...")
        btn_ext.clicked.connect(self._pick_external_base)
        ext_row.addWidget(self.ext_label, 1)
        ext_row.addWidget(btn_ext)
        form.addRow("Base externa:", ext_row)
        layout.addLayout(form)

        layout.addWidget(QLabel("Arquivos declarados em languages[]:"))
        self.entry_list = QListWidget()
        for entry in manifest.entries:
            cond = f" [{entry.conditional}]" if entry.conditional else ""
            suffix = " (HTTP - somente leitura)" if entry.is_http else (" (inválido)" if not entry.editable else "")
            item = QListWidgetItem(f"{entry.lang} — {entry.path}{cond}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            if entry.editable:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.entry_list.addItem(item)
        layout.addWidget(self.entry_list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _pick_external_base(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo JSON de referência",
            str(self.manifest.package_root),
            "JSON (*.json)",
        )
        if path_str:
            self.external_base_path = Path(path_str)
            self.ext_label.setText(self.external_base_path.name)

    def selected_base_lang(self) -> str:
        if self.external_base_path is not None:
            return "en"
        data = self.base_combo.currentData()
        return str(data) if data else self.manifest.default_base_lang

    def selected_entries(self) -> list[ManifestLangEntry]:
        chosen: list[ManifestLangEntry] = []
        for i in range(self.entry_list.count()):
            item = self.entry_list.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(entry, ManifestLangEntry) and entry.editable:
                if item.checkState() == Qt.CheckState.Checked:
                    chosen.append(entry)
        return chosen


class MainWindow(QMainWindow):
    """Main desktop window displaying multilingual translation table and inspector."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("i18n Reviewer")
        self.resize(1360, 780)
        self.session: PackageSession | None = None
        self.lang_checkboxes: dict[str, QCheckBox] = {}
        self._lang_actions: list[QAction] = []

        self.table_model = TranslationTableModel()
        self.proxy_model = PackageFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        self._build_toolbar()
        self._build_central()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Abra um module.json ou system.json do Foundry para começar.")

    def _build_toolbar(self) -> None:
        self.toolbar = QToolBar("Principal")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self.open_action = QAction("Abrir Pacote...", self)
        self.open_action.triggered.connect(self._on_open_package_clicked)
        self.toolbar.addAction(self.open_action)
        self.toolbar.addSeparator()

        self.toolbar.addWidget(QLabel(" Arquivo: "))
        self.file_filter_combo = QComboBox()
        self.file_filter_combo.addItem("Todos os arquivos", None)
        self.file_filter_combo.currentIndexChanged.connect(self._on_file_filter_changed)
        self.toolbar.addWidget(self.file_filter_combo)

        self.toolbar.addSeparator()
        self.lang_anchor_action = self.toolbar.addSeparator()

        spacer = QWidget()
        spacer.setSizePolicy(
            spacer.sizePolicy().horizontalPolicy().Expanding,
            spacer.sizePolicy().verticalPolicy().Preferred,
        )
        self.toolbar.addWidget(spacer)

        self.toggle_inspector_button = QPushButton("Inspector")
        self.toggle_inspector_button.setCheckable(True)
        self.toggle_inspector_button.setChecked(True)
        self.toggle_inspector_button.clicked.connect(self._toggle_inspector)
        self.toolbar.addWidget(self.toggle_inspector_button)

    def _build_central(self) -> None:
        container = QWidget()
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.diagnostic_banner = QLabel("")
        self.diagnostic_banner.setWordWrap(True)
        self.diagnostic_banner.setStyleSheet(
            "QLabel { background: #fef3c7; color: #92400e; padding: 6px 10px; "
            "border-bottom: 1px solid #f59e0b; font-weight: bold; }"
        )
        self.diagnostic_banner.setVisible(False)
        root_layout.addWidget(self.diagnostic_banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setItemDelegate(StatusCellDelegate(self.table))
        self.table.setWordWrap(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setMinimumSectionSize(44)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.selectionModel().currentChanged.connect(self._on_current_changed)

        self.inspector_panel = QFrame()
        self.inspector_panel.setMinimumWidth(300)
        self.inspector_panel.setMaximumWidth(400)
        self.inspector_panel.setFrameShape(QFrame.Shape.StyledPanel)
        pv = QVBoxLayout(self.inspector_panel)

        self.inspector_key_label = QLabel("Selecione uma célula")
        self.inspector_key_label.setWordWrap(True)
        self.inspector_key_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.inspector_origin_label = QLabel("")
        self.inspector_origin_label.setWordWrap(True)
        self.inspector_state_label = QLabel("")
        self.inspector_state_label.setWordWrap(True)
        self.inspector_diag_label = QLabel("")
        self.inspector_diag_label.setWordWrap(True)

        pv.addWidget(self.inspector_key_label)
        pv.addWidget(self.inspector_origin_label)
        pv.addWidget(self.inspector_state_label)
        pv.addWidget(self.inspector_diag_label)
        pv.addStretch()

        splitter.addWidget(self.table)
        splitter.addWidget(self.inspector_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(container)

    def _on_open_package_clicked(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir manifest do Foundry VTT",
            "",
            "Foundry Manifest (module.json system.json);;JSON (*.json)",
        )
        if not path_str:
            return
        manifest = discover_manifest(Path(path_str))
        dlg = OpenPackageDialog(manifest, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.open_package_manifest(
                Path(path_str),
                base_lang=dlg.selected_base_lang(),
                selected_entries=dlg.selected_entries(),
                base_external_path=dlg.external_base_path,
            )

    def open_package_manifest(
        self,
        manifest_path: Path,
        base_lang: str | None = None,
        selected_entries: list[ManifestLangEntry] | None = None,
        base_external_path: Path | None = None,
    ) -> PackageSession:
        manifest = discover_manifest(manifest_path)
        session = load_package_session(
            manifest,
            base_lang=base_lang,
            selected_entries=selected_entries,
            base_external_path=base_external_path,
        )
        self.load_session(session)
        return session

    def load_session(self, session: PackageSession) -> None:
        self.session = session
        self.table_model.set_session(session)
        self.setWindowTitle(f"i18n Reviewer — {session.manifest.package_id}")

        self.table.setColumnWidth(0, 230)
        self.table.setColumnWidth(1, 260)
        for col in range(2, 2 + len(session.target_langs)):
            self.table.setColumnWidth(col, 240)
            self.table.setColumnHidden(col, False)

        self._rebuild_language_checkboxes(session.target_langs)
        self._rebuild_file_filter(session)
        self._refresh_diagnostics_banner(session)
        self._refresh_statusbar(session)

        if self.proxy_model.rowCount() > 0:
            col = 2 if session.target_langs else 1
            self.table.setCurrentIndex(self.proxy_model.index(0, col))

    def _rebuild_language_checkboxes(self, target_langs: list[str]) -> None:
        for action in self._lang_actions:
            self.toolbar.removeAction(action)
        self._lang_actions.clear()
        self.lang_checkboxes.clear()

        for col_offset, lang in enumerate(target_langs, start=2):
            cb = QCheckBox(lang)
            cb.setChecked(True)
            cb.toggled.connect(
                lambda checked, c=col_offset: self.table.setColumnHidden(c, not checked)
            )
            action = self.toolbar.insertWidget(self.lang_anchor_action, cb)
            self.lang_checkboxes[lang] = cb
            self._lang_actions.append(action)

    def _rebuild_file_filter(self, session: PackageSession) -> None:
        self.file_filter_combo.blockSignals(True)
        self.file_filter_combo.clear()
        self.file_filter_combo.addItem("Todos os arquivos", None)
        for lf in session.files:
            self.file_filter_combo.addItem(f"{lf.lang}: {lf.rel_path}", lf.rel_path)
        self.file_filter_combo.setCurrentIndex(0)
        self.file_filter_combo.blockSignals(False)
        self.proxy_model.set_file_filter(None)

    def _refresh_diagnostics_banner(self, session: PackageSession) -> None:
        if not session.warnings and not session.file_diagnostics:
            self.diagnostic_banner.setVisible(False)
            self.diagnostic_banner.setText("")
            return
        lines: list[str] = []
        for w in session.warnings[:4]:
            path_part = f" ({w.path})" if w.path else ""
            lines.append(f"[{w.kind}]{path_part} {w.message}")
        if len(session.warnings) > 4:
            lines.append(f"... e mais {len(session.warnings) - 4} aviso(s).")
        self.diagnostic_banner.setText(" | ".join(lines))
        self.diagnostic_banner.setVisible(True)

    def _refresh_statusbar(self, session: PackageSession) -> None:
        total_keys = len(session.rows)
        missing_count = sum(
            1 for r in session.rows for c in r.cells.values() if c.kind == CellKind.MISSING
        )
        orphan_count = sum(
            1 for r in session.rows for c in r.cells.values() if c.kind == CellKind.ORPHAN
        )
        diag_count = len(session.warnings) + sum(len(v) for v in session.file_diagnostics.values())
        self.statusBar().showMessage(
            f"{total_keys} chaves · {missing_count} missing · {orphan_count} órfãs · {diag_count} avisos/erros"
        )

    def _on_file_filter_changed(self) -> None:
        self.proxy_model.set_file_filter(self.file_filter_combo.currentData())

    def _toggle_inspector(self, checked: bool) -> None:
        self.inspector_panel.setVisible(checked)

    def _on_current_changed(self, current: QModelIndex, _prev: QModelIndex) -> None:
        if self.session is None or not current.isValid():
            return
        src = self.proxy_model.mapToSource(current)
        if not src.isValid():
            return
        row_data = self.table_model.get_row(src.row())
        if row_data is None:
            return

        col = src.column()
        if col < 2 or not self.session.target_langs:
            self.inspector_key_label.setText(f"{row_data.key_path}\nIdioma: {self.session.base_lang} (Base)")
            self.inspector_origin_label.setText(
                f"Origem: {row_data.base_source_file or '(ausente)'} (linha {row_data.base_line})"
            )
            self.inspector_state_label.setText("Estado: Referência (somente leitura)")
            self.inspector_diag_label.setText("")
            return

        lang = self.session.target_langs[col - 2]
        cell = row_data.cells.get(lang)
        if cell is None:
            return
        conds = self.session.lang_conditionals.get(lang, [])
        cond_suffix = f"\nCondição: {', '.join(conds)}" if conds else ""
        self.inspector_key_label.setText(f"{row_data.key_path}\nIdioma: {lang}{cond_suffix}")
        origin = cell.source_file or row_data.base_source_file or "(desconhecido)"
        line_info = f" (linha {cell.line})" if cell.line else ""
        self.inspector_origin_label.setText(f"Origem: {origin}{line_info}")
        self.inspector_state_label.setText(
            f"Estado: {cell.kind.name} · Somente leitura: {'Sim' if cell.readonly else 'Não'}"
        )

        diags: list[str] = []
        files_to_check = [cell.source_file] if cell.source_file else []
        for fatal_path in self.session.fatal_files_by_lang.get(lang, []):
            if fatal_path not in files_to_check:
                files_to_check.append(fatal_path)
        for fpath in files_to_check:
            for issue in self.session.file_diagnostics.get(fpath, []):
                if issue.key_path in ("", row_data.key_path) or issue.kind in ("invalid_json", "leaf_before_branch"):
                    diags.append(f"[{issue.kind}] ({fpath}:{issue.line}) {issue.message}")
        for w in self.session.warnings:
            if w.kind == "multi_file_collision" and w.lang == lang and w.key_path == row_data.key_path:
                diags.append(f"[{w.kind}] {w.message}")
        self.inspector_diag_label.setText("\n".join(diags) if diags else "Diagnóstico do arquivo: OK")
