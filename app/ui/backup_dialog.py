from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.backup_manager import (
    BackupBatch,
    PublishFilePlan,
    PublishPlan,
    delete_backup_batch,
    list_backup_batches,
)


@dataclass(frozen=True)
class RestoreSelection:
    """User selection returned from BackupDialog."""

    batch_id: str
    rel_paths: list[str] | None
    discard_local_drafts: bool


class PublishDialog(QDialog):
    """Pre-publish summary dialog letting the user select target files and confirm warnings."""

    def __init__(self, plan: PublishPlan, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Enviar para Produção")
        self.resize(620, 440)
        self.plan = plan
        self._item_plans: list[tuple[QListWidgetItem, PublishFilePlan]] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Selecione os arquivos modificados para publicar:"))

        self.file_list = QListWidget()
        for fp in plan.file_plans:
            summary = f"{fp.lang} — {fp.rel_path} ({len(fp.edited_keys)} edições, {len(fp.deleted_keys)} remoções)"
            if fp.is_blocked:
                summary += f" [BLOQUEADO: {'; '.join(fp.blocking_reasons)}]"
            item = QListWidgetItem(summary)
            if fp.is_blocked:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setCheckState(Qt.CheckState.Unchecked)
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
            self.file_list.addItem(item)
            self._item_plans.append((item, fp))
        self.file_list.itemChanged.connect(self._refresh_warnings)
        layout.addWidget(self.file_list, 1)

        layout.addWidget(QLabel("Resumo de avisos (confirmação única):"))
        self.warnings_view = QTextEdit()
        self.warnings_view.setReadOnly(True)
        layout.addWidget(self.warnings_view, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText("Publicar selecionados")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_warnings()

    def _refresh_warnings(self) -> None:
        lines: list[str] = []
        for fp in self.selected_plans():
            if fp.duplicate_keys:
                lines.append(f"• [{fp.rel_path}] Chaves duplicadas no arquivo: {', '.join(fp.duplicate_keys)}")
            if fp.unreviewed_dirty_keys:
                lines.append(
                    f"• [{fp.rel_path}] {len(fp.unreviewed_dirty_keys)} célula(s) editada(s) ainda não revisada(s): "
                    + ", ".join(fp.unreviewed_dirty_keys[:8])
                )
            if fp.validation_warnings:
                lines.append(
                    f"• [{fp.rel_path}] {len(fp.validation_warnings)} aviso(s) de validação: "
                    + "; ".join(fp.validation_warnings[:5])
                )
            if fp.deleted_keys:
                lines.append(
                    f"• [{fp.rel_path}] Chaves órfãs que serão removidas: {', '.join(sorted(fp.deleted_keys))}"
                )
        self.warnings_view.setPlainText("\n".join(lines) if lines else "Nenhum aviso pendente nos arquivos selecionados.")

    def selected_plans(self) -> list[PublishFilePlan]:
        return [
            fp
            for item, fp in self._item_plans
            if not fp.is_blocked and item.checkState() == Qt.CheckState.Checked
        ]


class BackupDialog(QDialog):
    """Backup batch viewer supporting manual deletion and batch or single-file rollback."""

    def __init__(
        self,
        project_id: str,
        app_data_dir: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Restaurar Backup")
        self.resize(640, 440)
        self.project_id = project_id
        self.app_data_dir = app_data_dir
        self._batches: list[BackupBatch] = []

        layout = QVBoxLayout(self)
        cols = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(QLabel("Lotes de backup:"))
        self.batch_list = QListWidget()
        self.batch_list.currentRowChanged.connect(self._on_batch_selected)
        left.addWidget(self.batch_list, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel("Arquivos do lote (opcional escolher apenas 1):"))
        self.file_list = QListWidget()
        right.addWidget(self.file_list, 1)

        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        layout.addLayout(cols, 1)

        self.discard_checkbox = QCheckBox(
            "Descartar também rascunhos locais não publicados dos arquivos restaurados"
        )
        layout.addWidget(self.discard_checkbox)

        btn_row = QHBoxLayout()
        self.btn_delete = QPushButton("Excluir lote")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText("Restaurar selecionado")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        btn_row.addWidget(buttons)
        layout.addLayout(btn_row)

        self.reload_batches()

    def reload_batches(self) -> None:
        self.batch_list.clear()
        self.file_list.clear()
        self._batches = list_backup_batches(self.project_id, app_data_dir=self.app_data_dir)
        for b in self._batches:
            self.batch_list.addItem(f"{b.created_at} [{b.kind}] ({len(b.files)} arq.) — {b.batch_id}")
        if self._batches:
            self.batch_list.setCurrentRow(0)

    def _on_batch_selected(self, row: int) -> None:
        self.file_list.clear()
        if row < 0 or row >= len(self._batches):
            return
        self.file_list.addItem("(Todo o lote)")
        for entry in self._batches[row].files:
            self.file_list.addItem(entry.rel_path)
        self.file_list.setCurrentRow(0)

    def _on_delete_clicked(self) -> None:
        batch = self.selected_batch()
        if batch is None:
            return
        ans = QMessageBox.question(
            self,
            "Excluir backup",
            f"Excluir permanentemente o lote de backup '{batch.batch_id}'?",
        )
        if ans == QMessageBox.StandardButton.Yes:
            delete_backup_batch(self.project_id, batch.batch_id, app_data_dir=self.app_data_dir)
            self.reload_batches()

    def selected_batch(self) -> BackupBatch | None:
        row = self.batch_list.currentRow()
        if 0 <= row < len(self._batches):
            return self._batches[row]
        return None

    def restore_choice(self) -> RestoreSelection | None:
        batch = self.selected_batch()
        if batch is None:
            return None
        file_row = self.file_list.currentRow()
        rel_paths: list[str] | None = None
        if file_row > 0 and file_row - 1 < len(batch.files):
            rel_paths = [batch.files[file_row - 1].rel_path]
        return RestoreSelection(
            batch_id=batch.batch_id,
            rel_paths=rel_paths,
            discard_local_drafts=self.discard_checkbox.isChecked(),
        )

