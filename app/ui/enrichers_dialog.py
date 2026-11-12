from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.validator import CustomEnricherRule


class CustomEnrichersDialog(QDialog):
    """Project-level dialog to manage custom regex enricher rules."""

    def __init__(
        self,
        rules: list[CustomEnricherRule],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Custom Enricher Rules")
        self.resize(540, 360)
        self._rules = list(rules)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Configure optional regex rules (named groups ?P<tech> and ?P<label> supported):"
            )
        )

        self.rule_list = QListWidget()
        layout.addWidget(self.rule_list, 1)

        add_row = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Name (e.g., SystemMacro)")
        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText(r"Regex (e.g., (?P<tech>%[A-Z_]+%))")
        self.btn_add = QPushButton("Add")
        self.btn_add.clicked.connect(self._on_add_clicked)
        self.btn_remove = QPushButton("Remove selected")
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        add_row.addWidget(self.name_input, 1)
        add_row.addWidget(self.pattern_input, 2)
        add_row.addWidget(self.btn_add)
        add_row.addWidget(self.btn_remove)
        layout.addLayout(add_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._reload_list()

    def _reload_list(self) -> None:
        self.rule_list.clear()
        for rule in self._rules:
            self.rule_list.addItem(QListWidgetItem(f"{rule.name}: {rule.pattern}"))

    def _on_add_clicked(self) -> None:
        name = self.name_input.text().strip()
        pattern = self.pattern_input.text().strip()
        if not name or not pattern:
            return
        try:
            re.compile(pattern)
        except re.error as exc:
            QMessageBox.warning(self, "Invalid Regex", f"Invalid regex pattern: {exc}")
            return
        self._rules.append(CustomEnricherRule(name=name, pattern=pattern))
        self.name_input.clear()
        self.pattern_input.clear()
        self._reload_list()

    def _on_remove_clicked(self) -> None:
        row = self.rule_list.currentRow()
        if 0 <= row < len(self._rules):
            self._rules.pop(row)
            self._reload_list()

    def rules(self) -> list[CustomEnricherRule]:
        return list(self._rules)

