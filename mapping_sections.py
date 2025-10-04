"""Shared UI components for retry and generation sections."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ToggleMappingEditor(QWidget):
    """Editable list of mappings with enable checkboxes and summary text."""

    rowsChanged = pyqtSignal()

    def __init__(
        self,
        entries: Optional[list[tuple[str, str, bool]]] = None,
        left_placeholder: str = "",
        right_placeholder: str = "",
    ) -> None:
        super().__init__()
        self._left_placeholder = left_placeholder
        self._right_placeholder = right_placeholder
        self._rows: list[dict[str, object]] = []
        self._global_enabled = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        controls = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(lambda: self._set_all(True))
        controls.addWidget(select_all)
        select_none = QPushButton("Select None")
        select_none.clicked.connect(lambda: self._set_all(False))
        controls.addWidget(select_none)
        invert = QPushButton("Invert")
        invert.clicked.connect(self._invert_all)
        controls.addWidget(invert)
        controls.addStretch()
        self._control_buttons = [select_all, select_none, invert]
        layout.addLayout(controls)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._rows_layout)

        self._add_button = QPushButton("Add Row")
        self._add_button.clicked.connect(lambda: self.add_row())
        layout.addWidget(self._add_button)

        self.set_entries(entries or [])

    def set_entries(self, entries: list[tuple[str, str, bool]]) -> None:
        self._clear_rows()
        for left, right, enabled in entries:
            self.add_row(left, right, enabled)
        self._update_summary()
        self.rowsChanged.emit()

    def add_row(
        self,
        left_value: str = "",
        right_value: str = "",
        enabled: bool = True,
    ) -> None:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.stateChanged.connect(self._on_row_changed)
        row_layout.addWidget(checkbox)

        left_edit = QLineEdit()
        left_edit.setPlaceholderText(self._left_placeholder)
        left_edit.setText(left_value)
        left_edit.setMinimumWidth(140)
        left_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        left_edit.textChanged.connect(self._on_row_changed)
        row_layout.addWidget(left_edit)

        arrow = QLabel("→")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(16)
        row_layout.addWidget(arrow)

        right_edit = QLineEdit()
        right_edit.setPlaceholderText(self._right_placeholder)
        right_edit.setText(right_value)
        right_edit.setMinimumWidth(140)
        right_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        right_edit.textChanged.connect(self._on_row_changed)
        row_layout.addWidget(right_edit)

        row_layout.addStretch(1)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(lambda: self._remove_row(row_widget))
        row_layout.addWidget(remove_button)

        self._rows_layout.addWidget(row_widget)
        self._rows.append(
            {
                "widget": row_widget,
                "checkbox": checkbox,
                "left": left_edit,
                "right": right_edit,
            }
        )
        row_widget.setEnabled(self._global_enabled)
        self._update_summary()
        self.rowsChanged.emit()

    def get_entries(self) -> list[tuple[str, str, bool]]:
        entries: list[tuple[str, str, bool]] = []
        for row in self._rows:
            left_edit: QLineEdit = row["left"]  # type: ignore[assignment]
            right_edit: QLineEdit = row["right"]  # type: ignore[assignment]
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            left = left_edit.text().strip()
            right = right_edit.text().strip()
            if not left and not right:
                continue
            entries.append((left, right, checkbox.isChecked()))
        return entries

    def set_global_enabled(self, enabled: bool) -> None:
        self._global_enabled = enabled
        for row in self._rows:
            widget: QWidget = row["widget"]  # type: ignore[assignment]
            widget.setEnabled(enabled)
        for button in self._control_buttons:
            button.setEnabled(enabled)
        self._add_button.setEnabled(enabled)
        self._update_summary()

    def _set_all(self, value: bool) -> None:
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(value)
        self._update_summary()

    def _invert_all(self) -> None:
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(not checkbox.isChecked())
        self._update_summary()

    def _remove_row(self, widget: QWidget) -> None:
        for index, row in enumerate(self._rows):
            if row["widget"] is widget:
                self._rows.pop(index)
                break
        self._rows_layout.removeWidget(widget)
        widget.deleteLater()
        self._update_summary()
        self.rowsChanged.emit()

    def _clear_rows(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()
        self.rowsChanged.emit()

    def _on_row_changed(self) -> None:
        self._update_summary()
        self.rowsChanged.emit()

    def _update_summary(self) -> None:
        entries = []
        unchecked = []
        incomplete = []
        for row in self._rows:
            left_edit: QLineEdit = row["left"]  # type: ignore[assignment]
            right_edit: QLineEdit = row["right"]  # type: ignore[assignment]
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            left = left_edit.text().strip()
            right = right_edit.text().strip()
            if not left and not right:
                continue
            if left and right:
                entries.append((left, right, checkbox.isChecked()))
                if not checkbox.isChecked():
                    unchecked.append(f"{left} -> {right}")
            else:
                incomplete.append(left or right)

        if not entries and not incomplete:
            summary = "No mappings configured."
        else:
            if entries:
                total = len(entries)
                checked = [f"{left} -> {right}" for left, right, enabled in entries if enabled]
                if self._global_enabled:
                    enabled_count = len(checked)
                    enabled_text = ", ".join(checked) if checked else "none"
                    summary = f"Enabled ({enabled_count}/{total}): {enabled_text}"
                    if unchecked:
                        summary = f"{summary} (disabled: {', '.join(unchecked)})"
                else:
                    configured = ", ".join(f"{left} -> {right}" for left, right, _ in entries)
                    summary = (
                        f"Generation disabled (configured: {configured})"
                        if configured
                        else "Generation disabled."
                    )
            else:
                summary = "Incomplete mappings present."
            if incomplete:
                summary = f"{summary} (incomplete: {', '.join(incomplete)})"

        self._summary_label.setText(summary)
        self.rowsChanged.emit()


class RetrySection(QGroupBox):
    """Group box that hosts retry configuration."""

    def __init__(self, title: str = "Retry strategy", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setTitle("")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_font = QFont(title_label.font())
        title_font.setPointSize(title_font.pointSize() + 2)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header = QHBoxLayout()
        header.addWidget(title_label)
        header.addStretch()
        layout.addLayout(header)

        self.retry_form = QFormLayout()
        self.retry_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.retry_limit_input = QLineEdit()
        self.retry_limit_input.setPlaceholderText("Retry attempts (default 50)")
        self.retry_form.addRow(QLabel("Retry Attempts:"), self.retry_limit_input)
        self.retry_delay_input = QLineEdit()
        self.retry_delay_input.setPlaceholderText("Initial retry delay seconds (default 5)")
        delay_label = QLabel("Initial Retry Delay (s):")
        delay_label.setToolTip(
            "First retry waits this many seconds. Every 10 retries, the wait time doubles."
        )
        self.retry_delay_input.setToolTip(
            "First retry waits this many seconds. Every 10 retries, the wait time doubles."
        )
        self.retry_form.addRow(delay_label, self.retry_delay_input)
        layout.addLayout(self.retry_form)

    def set_values(self, retry_limit: int, retry_delay: float) -> None:
        self.retry_limit_input.setText(str(retry_limit))
        self.retry_delay_input.setText(str(retry_delay))

    def values(self) -> tuple[int, float]:
        try:
            limit = int(self.retry_limit_input.text().strip())
        except ValueError:
            limit = 50
        if limit <= 0:
            limit = 50
        try:
            delay = float(self.retry_delay_input.text().strip())
        except ValueError:
            delay = 5.0
        if delay <= 0:
            delay = 5.0
        return limit, delay


class GenerationSection(QGroupBox):
    """Reusable generation section with title, enable toggle, provider selector, mapping widget."""

    def __init__(
        self,
        title: str,
        enable_label: str,
        mapping_widget: QWidget,
        description: str | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setTitle("")
        self._mapping_widget = mapping_widget
        self._provider_layout: Optional[QFormLayout] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_font = QFont(title_label.font())
        title_font.setPointSize(title_font.pointSize() + 2)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_row = QHBoxLayout()
        title_row.addWidget(title_label)
        title_row.addStretch()
        layout.addLayout(title_row)

        self.enable_checkbox = QCheckBox(enable_label)
        enable_row = QHBoxLayout()
        enable_row.addWidget(self.enable_checkbox)
        enable_row.addStretch()
        layout.addLayout(enable_row)

        if description:
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        layout.addWidget(mapping_widget)

        self.provider_combo: Optional[QComboBox] = None
        self.custom_model_input: Optional[QLineEdit] = None

    def add_provider_selector(
        self,
        providers: list[tuple[str, str]],
        include_custom: bool = True,
        label: str = "Provider",
        *,
        show_custom_input: bool = False,
    ) -> None:
        row = QFormLayout()
        row.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        row.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        provider_combo = QComboBox()
        provider_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        provider_combo.setMinimumWidth(180)
        for value, text in providers:
            provider_combo.addItem(text, value)
        if include_custom and not any(value == "custom" for value, _ in providers):
            provider_combo.addItem("Custom", "custom")
        self.provider_combo = provider_combo
        row.addRow(QLabel(label + ":"), provider_combo)

        if show_custom_input:
            custom_input = QLineEdit()
            custom_input.setPlaceholderText("Custom model or endpoint")
            custom_input.setEnabled(False)
            self.custom_model_input = custom_input
            row.addRow(QLabel("Custom value:"), custom_input)

            provider_combo.currentIndexChanged.connect(
                lambda _: custom_input.setEnabled(provider_combo.currentData() == "custom")
            )
        else:
            self.custom_model_input = None

        # Insert provider selector above mapping widget
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            insert_at = max(layout.count() - 1, 0)
            layout.insertLayout(insert_at, row)
        self._provider_layout = row

    def add_form_layout(self, form_layout: QFormLayout) -> None:
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            insert_at = max(layout.count() - 1, 0)
            layout.insertLayout(insert_at, form_layout)

    def add_provider_reset_button(self, button: QPushButton, label: str = "") -> None:
        if self._provider_layout is None:
            return
        spacer = QLabel(label)
        self._provider_layout.addRow(spacer, button)

    def set_enabled(self, enabled: bool) -> None:
        self.enable_checkbox.setChecked(enabled)
        if hasattr(self._mapping_widget, "set_global_enabled"):
            getattr(self._mapping_widget, "set_global_enabled")(enabled)

    def is_enabled(self) -> bool:
        return self.enable_checkbox.isChecked()

    def provider(self) -> tuple[str, str | None]:
        if not self.provider_combo:
            return "custom", None
        provider_value = self.provider_combo.currentData()
        custom_value = (
            self.custom_model_input.text().strip()
            if self.custom_model_input and self.custom_model_input.isEnabled()
            else ""
        )
        return provider_value, custom_value or None

    def set_provider(self, provider_value: str, custom_value: str | None = None) -> None:
        if not self.provider_combo:
            return
        index = self.provider_combo.findData(provider_value)
        if index == -1:
            index = self.provider_combo.findData("custom")
        self.provider_combo.setCurrentIndex(max(index, 0))
        if self.custom_model_input is not None:
            if provider_value == "custom" and custom_value:
                self.custom_model_input.setText(custom_value)
                self.custom_model_input.setEnabled(True)
            else:
                self.custom_model_input.setText(custom_value or "")
                self.custom_model_input.setEnabled(provider_value == "custom")

    def mapping_widget(self) -> QWidget:
        return self._mapping_widget


__all__ = [
    "ToggleMappingEditor",
    "RetrySection",
    "GenerationSection",
]
