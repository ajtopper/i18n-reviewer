from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.project_manager import ConflictChoice, ConflictResolution, SyncConflict


class _ConflictRowWidget(QWidget):
    """Single 3-way conflict item showing Snapshot x Disk x Local edit."""

    def __init__(self, conflict: SyncConflict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.conflict = conflict
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        header = QLabel(f"{conflict.key_path} ({conflict.lang})")
        header.setStyleSheet("font-weight: bold;")
        layout.addWidget(header)

        cols = QHBoxLayout()
        snap_txt = conflict.snapshot_value if conflict.snapshot_value is not None else "(missing)"
        disk_txt = conflict.disk_value if conflict.disk_value is not None else "(missing on disk)"
        local_txt = (
            "(marked for removal)"
            if conflict.was_deletion_draft
            else (conflict.local_value or "(missing)")
        )
        cols.addWidget(QLabel(f"Snapshot:\n{snap_txt}"), 1)
        cols.addWidget(QLabel(f"Current on disk:\n{disk_txt}"), 1)
        cols.addWidget(QLabel(f"My edit:\n{local_txt}"), 1)
        layout.addLayout(cols)

        controls = QHBoxLayout()
        self.choice_combo = QComboBox()
        self.choice_combo.addItem("Keep my edit", "keep_local")
        self.choice_combo.addItem("Accept from disk", "accept_disk")
        self.choice_combo.addItem("Edit manually", "manual")
        self.choice_combo.currentIndexChanged.connect(self._on_choice_changed)

        self.manual_edit = QLineEdit(conflict.local_value or conflict.disk_value or "")
        self.manual_edit.setEnabled(False)
        controls.addWidget(self.choice_combo)
        controls.addWidget(self.manual_edit, 1)
        layout.addLayout(controls)

    def _on_choice_changed(self) -> None:
        self.manual_edit.setEnabled(self.choice_combo.currentData() == "manual")

    def set_choice(self, choice: ConflictChoice) -> None:
        idx = self.choice_combo.findData(choice)
        if idx >= 0:
            self.choice_combo.setCurrentIndex(idx)

    def resolution(self) -> ConflictResolution:
        choice = self.choice_combo.currentData()
        if choice == "accept_disk":
            return ConflictResolution(
                key_path=self.conflict.key_path,
                lang=self.conflict.lang,
                choice="accept_disk",
                manual_value=self.conflict.disk_value,
            )
        if choice == "manual":
            return ConflictResolution(
                key_path=self.conflict.key_path,
                lang=self.conflict.lang,
                choice="manual",
                manual_value=self.manual_edit.text(),
            )
        return ConflictResolution(
            key_path=self.conflict.key_path,
            lang=self.conflict.lang,
            choice="keep_local",
            manual_value=self.conflict.local_value,
        )


class ConflictResolutionDialog(QDialog):
    """Side-by-side dialog for resolving real 3-way sync conflicts."""

    def __init__(self, conflicts: list[SyncConflict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"External conflicts detected ({len(conflicts)})")
        self.resize(820, 500)
        self._row_widgets: list[_ConflictRowWidget] = []

        layout = QVBoxLayout(self)
        batch_row = QHBoxLayout()
        batch_row.addWidget(QLabel("Batch action:"))
        btn_keep_all = QPushButton("Keep all mine")
        btn_keep_all.clicked.connect(lambda: self._apply_all("keep_local"))
        btn_disk_all = QPushButton("Accept all from disk")
        btn_disk_all.clicked.connect(lambda: self._apply_all("accept_disk"))
        batch_row.addWidget(btn_keep_all)
        batch_row.addWidget(btn_disk_all)
        batch_row.addStretch()
        layout.addLayout(batch_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        for conflict in conflicts:
            row_w = _ConflictRowWidget(conflict, inner)
            self._row_widgets.append(row_w)
            inner_layout.addWidget(row_w)
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_all(self, choice: ConflictChoice) -> None:
        for row_w in self._row_widgets:
            row_w.set_choice(choice)

    def resolutions(self) -> list[ConflictResolution]:
        return [row_w.resolution() for row_w in self._row_widgets]

