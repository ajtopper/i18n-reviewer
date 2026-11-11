from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QEvent, QFileSystemWatcher, QModelIndex, QObject, QTimer, Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeyEvent, QKeySequence, QUndoStack
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
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
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
    PackageNotFoundError,
    PackageSession,
    SyncConflict,
    UnsupportedProjectVersionError,
    apply_conflict_resolutions,
    check_external_disk_changes,
    clear_recovery_draft,
    commit_sync_preview,
    default_app_data_dir,
    discover_manifest,
    has_recovery_draft,
    load_package_session,
    load_project_file,
    prepare_disk_sync,
    resolve_loaded_file_path,
    save_project_file,
    write_recovery_draft,
)
from app.ui.commands import (
    EditCellCommand,
    RevertCellCommand,
    ReviewCellCommand,
    ToggleOrphanDeletionCommand,
)
from app.ui.conflict_dialog import ConflictResolutionDialog
from app.ui.delegates import StatusCellDelegate
from app.ui.table_model import PackageFilterProxyModel, StatusFilterMode, TranslationTableModel


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


class ExpandedEditorDialog(QDialog):
    """Side-by-side Base x Translation editor for long or multi-line strings (Shift+F2)."""

    def __init__(
        self,
        base_text: str,
        target_text: str,
        key_path: str,
        lang: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Editor Expandido — {key_path} ({lang})")
        self.resize(780, 420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Chave: {key_path} · Idioma: {lang}"))

        cols = QHBoxLayout()
        left_box = QVBoxLayout()
        left_box.addWidget(QLabel("Referência (Base):"))
        self.base_view = QPlainTextEdit()
        self.base_view.setReadOnly(True)
        self.base_view.setPlainText(base_text)
        left_box.addWidget(self.base_view)

        right_box = QVBoxLayout()
        right_box.addWidget(QLabel(f"Tradução ({lang}):"))
        self.target_edit = QPlainTextEdit()
        self.target_edit.setPlainText(target_text)
        right_box.addWidget(self.target_edit)

        cols.addLayout(left_box, 1)
        cols.addLayout(right_box, 1)
        layout.addLayout(cols, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.target_edit.setFocus()

    def edited_text(self) -> str:
        return self.target_edit.toPlainText()


class MainWindow(QMainWindow):
    """Main desktop window displaying multilingual translation table and inspector."""

    def __init__(self, app_data_dir: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("i18n Reviewer")
        self.resize(1360, 780)
        self.app_data_dir = app_data_dir or default_app_data_dir()
        self.session: PackageSession | None = None
        self._project_unsaved: bool = False
        self.lang_checkboxes: dict[str, QCheckBox] = {}
        self._lang_actions: list[QAction] = []

        self.undo_stack = QUndoStack(self)
        self.table_model = TranslationTableModel(undo_stack=self.undo_stack)
        self.proxy_model = PackageFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        self.fs_watcher = QFileSystemWatcher(self)
        self.fs_watcher.fileChanged.connect(lambda _: self.check_for_external_changes())

        self.search_debounce = QTimer(self)
        self.search_debounce.setSingleShot(True)
        self.search_debounce.setInterval(150)
        self.search_debounce.timeout.connect(self._apply_debounced_search)

        self._build_toolbar()
        self._build_central()
        self._bind_shortcuts()
        self.table_model.cell_edited.connect(self._on_cell_edited)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Abra um module.json ou system.json do Foundry para começar.")

    def _build_toolbar(self) -> None:
        self.toolbar = QToolBar("Principal")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self.open_action = QAction("Novo Projeto...", self)
        self.open_action.triggered.connect(self._on_open_package_clicked)
        self.toolbar.addAction(self.open_action)

        self.open_proj_action = QAction("Abrir Projeto...", self)
        self.open_proj_action.triggered.connect(self._on_open_project_clicked)
        self.toolbar.addAction(self.open_proj_action)

        self.save_proj_action = QAction("Salvar Projeto (Ctrl+S)", self)
        self.save_proj_action.triggered.connect(lambda: self.save_project())
        self.toolbar.addAction(self.save_proj_action)

        undo_action = self.undo_stack.createUndoAction(self, "Desfazer")
        undo_action.setShortcuts([QKeySequence(QKeySequence.StandardKey.Undo), QKeySequence("Ctrl+Z")])
        redo_action = self.undo_stack.createRedoAction(self, "Refazer")
        redo_action.setShortcuts([QKeySequence(QKeySequence.StandardKey.Redo), QKeySequence("Ctrl+Y")])
        self.undo_action = undo_action
        self.redo_action = redo_action
        self.toolbar.addAction(undo_action)
        self.toolbar.addAction(redo_action)
        self.toolbar.addSeparator()

        self.toolbar.addWidget(QLabel(" Filtro: "))
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItem("Todas", "all")
        self.status_filter_combo.addItem("Apenas Pendentes", "pending")
        self.status_filter_combo.addItem("Apenas Editadas", "edited")
        self.status_filter_combo.currentIndexChanged.connect(self._on_status_filter_changed)
        self.toolbar.addWidget(self.status_filter_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar chave ou texto (Ctrl+F)...")
        self.search_input.setMaximumWidth(230)
        self.search_input.textChanged.connect(lambda _: self.search_debounce.start())
        self.toolbar.addWidget(self.search_input)

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

        self.external_change_banner = QFrame()
        self.external_change_banner.setStyleSheet(
            "QFrame { background: #dbeafe; border-bottom: 1px solid #3b82f6; padding: 4px 10px; }"
        )
        ext_layout = QHBoxLayout(self.external_change_banner)
        ext_layout.setContentsMargins(6, 4, 6, 4)
        self.external_change_label = QLabel("Arquivos do pacote foram alterados externamente no disco.")
        self.external_change_label.setStyleSheet("color: #1e3a8a; font-weight: bold;")
        self.btn_sync_now = QPushButton("Sincronizar agora")
        self.btn_sync_now.clicked.connect(self.sync_with_disk)
        ext_layout.addWidget(self.external_change_label, 1)
        ext_layout.addWidget(self.btn_sync_now)
        self.external_change_banner.setVisible(False)
        root_layout.addWidget(self.external_change_banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.cell_delegate = StatusCellDelegate(self.table)
        self.table.setItemDelegate(self.cell_delegate)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setMinimumSectionSize(44)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
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
        self.inspector_stale_label = QLabel("")
        self.inspector_stale_label.setWordWrap(True)
        self.inspector_stale_label.setStyleSheet(
            "background: #ede9fe; color: #4c1d95; padding: 6px; border-radius: 4px;"
        )
        self.inspector_stale_label.setVisible(False)
        self.inspector_diag_label = QLabel("")
        self.inspector_diag_label.setWordWrap(True)

        self.btn_review_next = QPushButton("Marcar Revisado + Próxima (Ctrl+Enter)")
        self.btn_review_next.clicked.connect(self.review_and_advance)
        self.btn_next_pending = QPushButton("Próxima Pendente (Ctrl+Down)")
        self.btn_next_pending.clicked.connect(self.jump_to_next_pending)
        self.btn_expanded_editor = QPushButton("Editor Expandido (Shift+F2)")
        self.btn_expanded_editor.clicked.connect(self.open_expanded_editor)
        self.btn_revert_cell = QPushButton("Reverter para produção")
        self.btn_revert_cell.clicked.connect(self.revert_current_cell)
        self.btn_orphan_delete = QPushButton("Remover chave órfã...")
        self.btn_orphan_delete.clicked.connect(self.toggle_orphan_deletion_current_cell)

        pv.addWidget(self.inspector_key_label)
        pv.addWidget(self.inspector_origin_label)
        pv.addWidget(self.inspector_state_label)
        pv.addWidget(self.inspector_stale_label)
        pv.addWidget(self.inspector_diag_label)
        pv.addStretch()
        pv.addWidget(self.btn_review_next)
        pv.addWidget(self.btn_next_pending)
        pv.addWidget(self.btn_expanded_editor)
        pv.addWidget(self.btn_revert_cell)
        pv.addWidget(self.btn_orphan_delete)

        splitter.addWidget(self.table)
        splitter.addWidget(self.inspector_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(container)

    def _bind_shortcuts(self) -> None:
        self.installEventFilter(self)
        self.table.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            mods = event.modifiers()
            key = event.key()
            ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

            if ctrl and key == Qt.Key.Key_S:
                self.save_project()
                return True
            if ctrl and key == Qt.Key.Key_F:
                self.search_input.setFocus()
                return True
            if ctrl and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.review_and_advance()
                return True
            if ctrl and key == Qt.Key.Key_Down:
                self.jump_to_next_pending()
                return True
            if shift and key == Qt.Key.Key_F2:
                self.open_expanded_editor()
                return True
            if ctrl and not shift and key == Qt.Key.Key_Z and watched is self.table:
                self.undo_stack.undo()
                return True
            if ctrl and key == Qt.Key.Key_Y and watched is self.table:
                self.undo_stack.redo()
                return True
        return super().eventFilter(watched, event)

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

    def _update_window_title(self) -> None:
        if self.session is None:
            self.setWindowTitle("i18n Reviewer")
            return
        star = " *" if self._project_unsaved else ""
        self.setWindowTitle(f"i18n Reviewer — {self.session.manifest.package_id}{star}")

    def _watch_session_files(self, session: PackageSession) -> None:
        existing = self.fs_watcher.files()
        if existing:
            self.fs_watcher.removePaths(existing)
        paths_to_watch: list[str] = []
        for lf in session.files:
            cand = resolve_loaded_file_path(session, lf)
            if cand is not None and cand.exists():
                paths_to_watch.append(str(cand))
        if paths_to_watch:
            self.fs_watcher.addPaths(paths_to_watch)

    def _on_open_project_clicked(self) -> None:
        default_dir = str(self.app_data_dir / "projects")
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir projeto i18n Reviewer",
            default_dir,
            "i18n Reviewer Project (*.i18nproj)",
        )
        if path_str:
            self.open_project_file(Path(path_str))

    def open_project_file(self, project_path: Path) -> bool:
        try:
            loaded = load_project_file(project_path)
        except PackageNotFoundError:
            ans = QMessageBox.question(
                self,
                "Pacote não encontrado",
                "A pasta do pacote Foundry não foi encontrada. Deseja relocalizá-la agora?",
            )
            if ans != QMessageBox.StandardButton.Yes:
                return False
            reloc = QFileDialog.getExistingDirectory(self, "Relocalizar pasta do pacote")
            if not reloc:
                return False
            try:
                loaded = load_project_file(project_path, relocated_root=Path(reloc))
            except PackageNotFoundError as exc:
                QMessageBox.warning(self, "Pacote inválido", str(exc))
                return False
        except UnsupportedProjectVersionError as exc:
            QMessageBox.critical(self, "Versão não suportada", str(exc))
            return False

        session = loaded.session
        if has_recovery_draft(session.project_id, self.app_data_dir):
            ans = QMessageBox.question(
                self,
                "Recuperação de rascunho",
                "Foi encontrado um rascunho não salvo de uma sessão anterior. Deseja restaurá-lo?",
            )
            if ans == QMessageBox.StandardButton.Yes:
                loaded = load_project_file(
                    project_path,
                    relocated_root=session.manifest.package_root,
                    apply_recovery_dir=self.app_data_dir,
                )
                session = loaded.session
                self._project_unsaved = True
            else:
                clear_recovery_draft(session.project_id, self.app_data_dir)
                self._project_unsaved = False
        else:
            self._project_unsaved = bool(loaded.sync_report.conflicts)

        if loaded.sync_report.blocked_files:
            QMessageBox.warning(
                self,
                "Arquivos bloqueados na sincronização",
                f"Arquivos ausentes ou inválidos impediram sincronização completa: {', '.join(loaded.sync_report.blocked_files)}",
            )

        self.load_session(session, preserve_unsaved=self._project_unsaved)
        if loaded.sync_report.conflicts:
            if self._prompt_conflict_resolutions(session, loaded.sync_report.conflicts):
                self._project_unsaved = True
                self.table_model.set_session(session)
                self._refresh_statusbar(session)
                self._update_window_title()
        return True

    def save_project(self, project_path: Path | None = None) -> bool:
        if self.session is None:
            return False
        target = project_path or self.session.project_path
        if target is None:
            default_dir = self.app_data_dir / "projects"
            default_dir.mkdir(parents=True, exist_ok=True)
            suggested = str(default_dir / f"{self.session.manifest.package_id}.i18nproj")
            path_str, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar Projeto (.i18nproj)",
                suggested,
                "i18n Reviewer Project (*.i18nproj)",
            )
            if not path_str:
                return False
            target = Path(path_str)
        save_project_file(self.session, target, app_data_dir=self.app_data_dir)
        self._project_unsaved = False
        self._update_window_title()
        return True

    def check_for_external_changes(self) -> None:
        if self.session is None:
            return
        changed = check_external_disk_changes(self.session)
        if changed:
            self.external_change_label.setText(
                f"Alteração externa detectada em: {', '.join(changed)}"
            )
            self.external_change_banner.setVisible(True)
        else:
            self.external_change_banner.setVisible(False)

    def sync_with_disk(self) -> None:
        if self.session is None:
            return
        preview = prepare_disk_sync(self.session)
        if preview.report.blocked_files:
            QMessageBox.warning(
                self,
                "Sincronização bloqueada",
                f"Não foi possível sincronizar porque há arquivos ausentes ou inválidos: {', '.join(preview.report.blocked_files)}",
            )
            return
        if preview.report.conflicts:
            if not self._prompt_conflict_resolutions(preview.fresh_session, preview.report.conflicts):
                return
            self._project_unsaved = True
        commit_sync_preview(self.session, preview)
        self.load_session(self.session, preserve_unsaved=self._project_unsaved)
        self.external_change_banner.setVisible(False)

    def _prompt_conflict_resolutions(
        self,
        target_session: PackageSession,
        conflicts: list[SyncConflict],
    ) -> bool:
        if not conflicts:
            return True
        dlg = ConflictResolutionDialog(conflicts, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        apply_conflict_resolutions(target_session, dlg.resolutions())
        return True

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.WindowActivate:
            self.check_for_external_changes()
        super().changeEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.session is not None and self._project_unsaved:
            ans = QMessageBox.question(
                self,
                "Alterações não salvas",
                "Existem alterações não salvas no projeto (.i18nproj). Deseja salvar antes de fechar?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if ans == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if ans == QMessageBox.StandardButton.Save:
                if not self.save_project():
                    event.ignore()
                    return
        if self.session is not None:
            clear_recovery_draft(self.session.project_id, self.app_data_dir)
        super().closeEvent(event)

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
        self._project_unsaved = False
        self.load_session(session)
        return session

    def load_session(self, session: PackageSession, preserve_unsaved: bool = False) -> None:
        self.session = session
        if not preserve_unsaved:
            self._project_unsaved = False
        self.undo_stack.clear()
        self.cell_delegate.invalidate_cache()
        self.table_model.set_session(session)
        self._update_window_title()
        self._watch_session_files(session)
        self.external_change_banner.setVisible(False)

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
        reviewed_count = sum(
            1 for r in session.rows for c in r.cells.values() if c.review_status == "reviewed"
        )
        dirty_count = sum(
            1 for r in session.rows for c in r.cells.values() if c.is_dirty
        )
        missing_count = sum(
            1 for r in session.rows for c in r.cells.values() if c.is_missing
        )
        orphan_count = sum(
            1 for r in session.rows for c in r.cells.values() if c.kind == CellKind.ORPHAN
        )
        diag_count = len(session.warnings) + sum(len(v) for v in session.file_diagnostics.values())
        self.statusBar().showMessage(
            f"{total_keys} chaves · {reviewed_count} revisadas · {dirty_count} editadas · "
            f"{missing_count} missing · {orphan_count} órfãs · {diag_count} avisos/erros"
        )

    def _on_status_filter_changed(self) -> None:
        mode = cast(StatusFilterMode, self.status_filter_combo.currentData() or "all")
        self.proxy_model.set_status_filter(mode)

    def _apply_debounced_search(self) -> None:
        self.proxy_model.set_search_query(self.search_input.text())

    def _on_file_filter_changed(self) -> None:
        self.proxy_model.set_file_filter(self.file_filter_combo.currentData())

    def _toggle_inspector(self, checked: bool) -> None:
        self.inspector_panel.setVisible(checked)

    def _current_source_pos(self) -> tuple[int, int] | None:
        cur = self.table.currentIndex()
        if not cur.isValid():
            return None
        src = self.proxy_model.mapToSource(cur)
        if not src.isValid():
            return None
        return src.row(), src.column()

    def mark_current_reviewed(self) -> bool:
        pos = self._current_source_pos()
        if pos is None or pos[1] < 2:
            return False
        row, col = pos
        cell = self.table_model.get_cell(row, col)
        if cell is None or not cell.can_mark_reviewed():
            return False
        self.undo_stack.push(
            ReviewCellCommand(cell, row, col, self.table_model.notify_cell_changed)
        )
        return True

    def review_and_advance(self) -> None:
        self.mark_current_reviewed()
        self.jump_to_next_pending()

    def jump_to_next_pending(self) -> None:
        current_index = self.table.currentIndex()
        row_count = self.proxy_model.rowCount()
        if row_count == 0 or not self.table_model.target_langs:
            return
        start_col = current_index.column() if current_index.isValid() and current_index.column() >= 2 else 2
        start_row = (current_index.row() + 1) if current_index.isValid() else 0

        # Procura primeiro na coluna atual; se não houver pendentes, busca nas demais colunas visíveis
        visible_cols = [
            c for c in range(2, self.table_model.columnCount()) if not self.table.isColumnHidden(c)
        ]
        ordered_cols = [start_col] + [c for c in visible_cols if c != start_col]

        for col_offset, col in enumerate(ordered_cols):
            begin_row = start_row if col_offset == 0 else 0
            for offset in range(row_count):
                row_idx = (begin_row + offset) % row_count
                proxy_index = self.proxy_model.index(row_idx, col)
                source_index = self.proxy_model.mapToSource(proxy_index)
                cell = self.table_model.get_cell(source_index.row(), col)
                if cell is not None and cell.is_pending:
                    self.table.setCurrentIndex(proxy_index)
                    self.table.scrollTo(proxy_index)
                    return

    def revert_current_cell(self) -> None:
        pos = self._current_source_pos()
        if pos is None or pos[1] < 2:
            return
        row, col = pos
        row_data = self.table_model.get_row(row)
        cell = self.table_model.get_cell(row, col)
        if row_data is None or cell is None or not cell.is_dirty:
            return
        self.undo_stack.push(
            RevertCellCommand(cell, row_data.base_text, row, col, self.table_model.notify_cell_changed)
        )

    def toggle_orphan_deletion_current_cell(self) -> None:
        pos = self._current_source_pos()
        if pos is None or pos[1] < 2:
            return
        row, col = pos
        row_data = self.table_model.get_row(row)
        cell = self.table_model.get_cell(row, col)
        if row_data is None or cell is None or cell.readonly or cell.kind != CellKind.ORPHAN:
            return
        target_flag = not cell.marked_for_deletion
        prompt = (
            f"Marcar a chave órfã '{row_data.key_path}' para remoção no próximo envio para produção?"
            if target_flag
            else f"Cancelar a remoção da chave órfã '{row_data.key_path}'?"
        )
        ans = QMessageBox.question(self, "Remover chave órfã", prompt)
        if ans != QMessageBox.StandardButton.Yes:
            return
        self.undo_stack.push(
            ToggleOrphanDeletionCommand(cell, target_flag, row, col, self.table_model.notify_cell_changed)
        )

    def open_expanded_editor(self) -> None:
        pos = self._current_source_pos()
        if pos is None or pos[1] < 2 or self.session is None:
            return
        row, col = pos
        row_data = self.table_model.get_row(row)
        cell = self.table_model.get_cell(row, col)
        if row_data is None or cell is None or not cell.can_edit():
            return
        lang = self.session.target_langs[col - 2]
        dlg = ExpandedEditorDialog(
            row_data.base_text or "",
            cell.local_value or "",
            row_data.key_path,
            lang,
            self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_val = dlg.edited_text()
            if cell.will_apply_edit(new_val):
                self.undo_stack.push(
                    EditCellCommand(
                        cell=cell,
                        base_text=row_data.base_text,
                        new_value=new_val,
                        row=row,
                        col=col,
                        notify=self.table_model.notify_cell_changed,
                    )
                )

    def _on_context_menu(self, pos: object) -> None:
        from PySide6.QtCore import QPoint

        if not isinstance(pos, QPoint):
            return
        proxy_index = self.table.indexAt(pos)
        if not proxy_index.isValid():
            return
        self.table.setCurrentIndex(proxy_index)
        source_index = self.proxy_model.mapToSource(proxy_index)
        if not source_index.isValid() or source_index.column() < 2:
            return
        cell = self.table_model.get_cell(source_index.row(), source_index.column())
        if cell is None:
            return

        menu = QMenu(self)
        menu.addAction("Marcar como Revisado", self.mark_current_reviewed)
        menu.addAction("Marcar Revisado + Próxima (Ctrl+Enter)", self.review_and_advance)
        menu.addAction("Editor Expandido (Shift+F2)...", self.open_expanded_editor)
        if cell.is_dirty:
            menu.addAction("Reverter para produção", self.revert_current_cell)
        if cell.kind == CellKind.ORPHAN and not cell.readonly:
            label = "Cancelar remoção de órfã" if cell.marked_for_deletion else "Remover chave órfã..."
            menu.addAction(label, self.toggle_orphan_deletion_current_cell)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_cell_edited(self, _row: int, _col: int) -> None:
        if self.session is not None:
            self._project_unsaved = True
            self._update_window_title()
            write_recovery_draft(self.session, app_data_dir=self.app_data_dir)
            self._refresh_statusbar(self.session)
        self._on_current_changed(self.table.currentIndex(), QModelIndex())

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
            self.inspector_stale_label.setVisible(False)
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
        dirty_str = "Sim" if cell.is_dirty else "Não"
        self.inspector_state_label.setText(
            f"Estado: {cell.kind.name} · Revisão: {cell.review_status} · Dirty: {dirty_str}"
        )
        if cell.review_status == "stale" or cell.previous_base is not None:
            prev_txt = cell.previous_base if cell.previous_base is not None else "(ausente)"
            curr_txt = row_data.base_text if row_data.base_text is not None else "(ausente)"
            self.inspector_stale_label.setText(f"Base mudou (STALE):\nAntes: {prev_txt}\nAgora: {curr_txt}")
            self.inspector_stale_label.setVisible(True)
        else:
            self.inspector_stale_label.setVisible(False)

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
