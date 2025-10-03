from functools import partial

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QCheckBox,
    QLabel,
)


class DynamicForm(QWidget):
    """Editable two-column form for text response key → field mapping."""

    def __init__(
        self,
        rows: list[tuple[str, str, bool]],
        card_fields: list[str],
    ) -> None:
        super().__init__()
        self.layout = QVBoxLayout(self)
        base_fields = list(card_fields)
        if "" not in base_fields:
            base_fields = [""] + base_fields
        self._card_fields = base_fields
        self._item_width = 250
        self._rows: list[dict[str, object]] = []
        self._master_override = False
        self._control_buttons: list[QPushButton] = []

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        self.layout.addWidget(self._summary_label)

        control_layout = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(lambda: self._set_all(True))
        select_none = QPushButton("Select None")
        select_none.clicked.connect(lambda: self._set_all(False))
        invert = QPushButton("Invert")
        invert.clicked.connect(self._invert_all)
        control_layout.addWidget(select_all)
        control_layout.addWidget(select_none)
        control_layout.addWidget(invert)
        self._show_enabled_checkbox = QCheckBox("Show enabled only")
        self._show_enabled_checkbox.stateChanged.connect(
            lambda _: self._update_row_visibility()
        )
        control_layout.addWidget(self._show_enabled_checkbox)
        control_layout.addStretch()
        self._control_buttons = [select_all, select_none, invert]
        self.layout.addLayout(control_layout)

        self.add_button = QPushButton("Add Row")
        self.add_button.clicked.connect(partial(self.add_row, key="", field="", enabled=True))

        self._fill_initial_data(rows)
        self.layout.addWidget(self.add_button)
        self.setLayout(self.layout)
        self._update_summary()

    def _fill_initial_data(self, rows: list[tuple[str, str, bool]]) -> None:
        if rows:
            for key, field, enabled in rows:
                self.add_row(key, field, enabled)
        else:
            self.add_row()

    def add_row(self, key: str = "", field: str = "", enabled: bool = True) -> None:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.setEnabled(not self._master_override)
        checkbox.stateChanged.connect(lambda _: self._on_row_updated())
        row_layout.addWidget(checkbox)

        text_box = QLineEdit()
        text_box.setText(key)
        text_box.setMaximumWidth(self._item_width)
        text_box.textChanged.connect(lambda _: self._on_row_updated())
        row_layout.addWidget(text_box)

        combo_box = QComboBox()
        combo_box.setMaximumWidth(self._item_width)
        combo_box.addItems(self._card_fields)
        combo_box.setCurrentText(field)
        combo_box.currentIndexChanged.connect(lambda _: self._on_row_updated())
        row_layout.addWidget(combo_box)

        index = self.layout.count() - 1
        if index < 0:
            self.layout.addWidget(row_widget)
        else:
            self.layout.insertWidget(index, row_widget)

        self._rows.append(
            {
                "widget": row_widget,
                "checkbox": checkbox,
                "key": text_box,
                "field": combo_box,
            }
        )
        self._update_summary()
        self._update_row_visibility()

    def clear_rows(self) -> None:
        for row in self._rows:
            widget = row["widget"]
            self.layout.removeWidget(widget)
            widget.deleteLater()
        self._rows.clear()
        self._update_summary()
        self._update_row_visibility()

    def set_rows(self, rows: list[tuple[str, str, bool]]) -> None:
        self.clear_rows()
        if rows:
            for key, field, enabled in rows:
                self.add_row(key, field, enabled)
        else:
            self.add_row()
        self._update_summary()
        self._update_row_visibility()

    def set_master_override(self, master_checked: bool) -> None:
        self._master_override = master_checked
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setEnabled(not master_checked)
        for button in self._control_buttons:
            button.setEnabled(not master_checked)
        self._update_summary()
        self._update_row_visibility()

    def get_inputs(self) -> tuple[list[str], list[str]]:
        keys: list[str] = []
        fields: list[str] = []
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            text_box: QLineEdit = row["key"]  # type: ignore[assignment]
            combo_box: QComboBox = row["field"]  # type: ignore[assignment]
            key = text_box.text().strip()
            field = combo_box.currentText().strip()
            if not key or not field:
                continue
            if self._master_override or checkbox.isChecked():
                keys.append(key)
                fields.append(field)
        return keys, fields

    def get_all_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            text_box: QLineEdit = row["key"]  # type: ignore[assignment]
            combo_box: QComboBox = row["field"]  # type: ignore[assignment]
            rows.append(
                {
                    "key": text_box.text().strip(),
                    "field": combo_box.currentText().strip(),
                    "enabled": checkbox.isChecked(),
                }
            )
        return rows

    def _set_all(self, value: bool) -> None:
        if self._master_override:
            return
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(value)
        self._update_summary()
        self._update_row_visibility()

    def _invert_all(self) -> None:
        if self._master_override:
            return
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(not checkbox.isChecked())
        self._update_summary()
        self._update_row_visibility()

    def _on_row_updated(self) -> None:
        self._update_summary()
        self._update_row_visibility()

    def _update_summary(self) -> None:
        entries: list[tuple[str, str, bool]] = []
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            text_box: QLineEdit = row["key"]  # type: ignore[assignment]
            combo_box: QComboBox = row["field"]  # type: ignore[assignment]
            key = text_box.text().strip()
            field = combo_box.currentText().strip()
            if not key and not field:
                continue
            enabled = bool(key and field) and (self._master_override or checkbox.isChecked())
            entries.append((key, field, enabled))
        if not entries:
            self._summary_label.setText('Enabled mappings: none configured')
            return
        total = len(entries)
        enabled_entries = [f"{key} -> {field}" for key, field, enabled in entries if enabled]
        enabled_count = len(enabled_entries)
        if enabled_entries:
            summary = f"Enabled ({enabled_count}/{total}): {', '.join(enabled_entries)}"
        else:
            summary = f"Enabled (0/{total}): none"
        disabled_entries = [f"{key} -> {field}" for key, field, enabled in entries if not enabled]
        if disabled_entries:
            summary = f"{summary} (disabled: {', '.join(disabled_entries)})"
        self._summary_label.setText(summary)

    def _update_row_visibility(self) -> None:
        show_enabled_only = self._show_enabled_checkbox.isChecked()
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            widget: QWidget = row["widget"]  # type: ignore[assignment]
            visible = True
            if show_enabled_only and not (self._master_override or checkbox.isChecked()):
                visible = False
            widget.setVisible(visible)


class ImageMappingForm(QWidget):
    """Mapping editor for image generation prompts."""

    def __init__(self, rows: list[tuple[str, str, bool]], card_fields: list[str]):
        super().__init__()
        base_fields = list(card_fields)
        if "" not in base_fields:
            base_fields = [""] + base_fields
        self._card_fields = base_fields
        self._item_width = 250
        self.layout = QVBoxLayout(self)
        self._rows: list[dict[str, object]] = []
        self._control_buttons: list[QPushButton] = []
        self._master_override = False

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        self.layout.addWidget(self._summary_label)

        control_layout = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(lambda: self._set_all(True))
        select_none = QPushButton("Select None")
        select_none.clicked.connect(lambda: self._set_all(False))
        invert = QPushButton("Invert")
        invert.clicked.connect(self._invert_all)
        control_layout.addWidget(select_all)
        control_layout.addWidget(select_none)
        control_layout.addWidget(invert)
        self._show_enabled_checkbox = QCheckBox("Show enabled only")
        self._show_enabled_checkbox.stateChanged.connect(
            lambda _: self._update_row_visibility()
        )
        control_layout.addWidget(self._show_enabled_checkbox)
        control_layout.addStretch()
        self._control_buttons = [select_all, select_none, invert]
        self.layout.addLayout(control_layout)

        self.add_button = QPushButton("Add Mapping")
        self.add_button.clicked.connect(lambda: self.add_row())

        if rows:
            for prompt_field, image_field, enabled in rows:
                self.add_row(prompt_field, image_field, enabled)
        else:
            self.add_row()

        self.layout.addWidget(self.add_button)
        self.setLayout(self.layout)
        self._update_summary()
        self._update_row_visibility()

    def add_row(
        self,
        prompt_field: str = "",
        image_field: str = "",
        enabled: bool = True,
    ) -> None:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.setEnabled(not self._master_override)
        checkbox.stateChanged.connect(lambda _: self._on_row_updated())
        row_layout.addWidget(checkbox)

        prompt_combo = QComboBox()
        prompt_combo.setMaximumWidth(self._item_width)
        prompt_combo.addItems(self._card_fields)
        prompt_combo.setCurrentText(prompt_field)
        prompt_combo.currentIndexChanged.connect(lambda _: self._on_row_updated())
        row_layout.addWidget(prompt_combo)

        image_combo = QComboBox()
        image_combo.setMaximumWidth(self._item_width)
        image_combo.addItems(self._card_fields)
        image_combo.setCurrentText(image_field)
        image_combo.currentIndexChanged.connect(lambda _: self._on_row_updated())
        row_layout.addWidget(image_combo)

        index = self.layout.count() - 1
        if index < 0:
            self.layout.addWidget(row_widget)
        else:
            self.layout.insertWidget(index, row_widget)

        self._rows.append(
            {
                "widget": row_widget,
                "checkbox": checkbox,
                "prompt": prompt_combo,
                "target": image_combo,
            }
        )
        self._update_summary()
        self._update_row_visibility()

    def clear_rows(self) -> None:
        for row in self._rows:
            widget = row["widget"]
            self.layout.removeWidget(widget)
            widget.deleteLater()
        self._rows.clear()
        self._update_summary()
        self._update_row_visibility()

    def set_pairs(self, pairs: list[tuple[str, str, bool]]) -> None:
        self.clear_rows()
        if pairs:
            for prompt_field, image_field, enabled in pairs:
                self.add_row(prompt_field, image_field, enabled)
        else:
            self.add_row()
        self._update_summary()
        self._update_row_visibility()

    def set_master_override(self, master_checked: bool) -> None:
        self._master_override = master_checked
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setEnabled(not master_checked)
        for button in self._control_buttons:
            button.setEnabled(not master_checked)
        self._update_summary()
        self._update_row_visibility()

    def get_pairs(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            prompt_widget: QComboBox = row["prompt"]  # type: ignore[assignment]
            image_widget: QComboBox = row["target"]  # type: ignore[assignment]
            prompt_value = prompt_widget.currentText().strip()
            image_value = image_widget.currentText().strip()
            if not prompt_value or not image_value:
                continue
            if self._master_override or checkbox.isChecked():
                pairs.append((prompt_value, image_value))
        return pairs

    def get_all_rows(self) -> list[tuple[str, str, bool]]:
        rows: list[tuple[str, str, bool]] = []
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            prompt_widget: QComboBox = row["prompt"]  # type: ignore[assignment]
            image_widget: QComboBox = row["target"]  # type: ignore[assignment]
            rows.append(
                (
                    prompt_widget.currentText().strip(),
                    image_widget.currentText().strip(),
                    checkbox.isChecked(),
                )
            )
        return rows

    def _set_all(self, value: bool) -> None:
        if self._master_override:
            return
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(value)
        self._update_summary()
        self._update_row_visibility()

    def _invert_all(self) -> None:
        if self._master_override:
            return
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(not checkbox.isChecked())
        self._update_summary()
        self._update_row_visibility()

    def _on_row_updated(self) -> None:
        self._update_summary()
        self._update_row_visibility()

    def _update_summary(self) -> None:
        entries: list[tuple[str, str, bool]] = []
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            prompt_widget: QComboBox = row["prompt"]  # type: ignore[assignment]
            target_widget: QComboBox = row["target"]  # type: ignore[assignment]
            prompt = prompt_widget.currentText().strip()
            target = target_widget.currentText().strip()
            if not prompt and not target:
                continue
            enabled = bool(prompt and target) and (self._master_override or checkbox.isChecked())
            entries.append((prompt, target, enabled))
        if not entries:
            self._summary_label.setText('Enabled mappings: none configured')
            return
        total = len(entries)
        enabled_entries = [f"{prompt} -> {target}" for prompt, target, enabled in entries if enabled]
        enabled_count = len(enabled_entries)
        if enabled_entries:
            summary = f"Enabled ({enabled_count}/{total}): {', '.join(enabled_entries)}"
        else:
            summary = f"Enabled (0/{total}): none"
        disabled_entries = [f"{prompt} -> {target}" for prompt, target, enabled in entries if not enabled]
        if disabled_entries:
            summary = f"{summary} (disabled: {', '.join(disabled_entries)})"
        self._summary_label.setText(summary)

    def _update_row_visibility(self) -> None:
        show_enabled_only = self._show_enabled_checkbox.isChecked()
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            widget: QWidget = row["widget"]  # type: ignore[assignment]
            visible = True
            if show_enabled_only and not (self._master_override or checkbox.isChecked()):
                visible = False
            widget.setVisible(visible)


class AudioMappingForm(ImageMappingForm):
    """Mapping editor for speech synthesis prompts."""

    def add_row(
        self,
        prompt_field: str = "",
        audio_field: str = "",
        enabled: bool = True,
    ) -> None:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.setEnabled(not self._master_override)
        checkbox.stateChanged.connect(lambda _: self._on_row_updated())
        row_layout.addWidget(checkbox)

        prompt_combo = QComboBox()
        prompt_combo.setMaximumWidth(self._item_width)
        prompt_combo.addItems(self._card_fields)
        prompt_combo.setCurrentText(prompt_field)
        prompt_combo.currentIndexChanged.connect(lambda _: self._on_row_updated())
        row_layout.addWidget(prompt_combo)

        audio_combo = QComboBox()
        audio_combo.setMaximumWidth(self._item_width)
        audio_combo.addItems(self._card_fields)
        audio_combo.setCurrentText(audio_field)
        audio_combo.currentIndexChanged.connect(lambda _: self._on_row_updated())
        row_layout.addWidget(audio_combo)

        index = self.layout.count() - 1
        if index < 0:
            self.layout.addWidget(row_widget)
        else:
            self.layout.insertWidget(index, row_widget)

        self._rows.append(
            {
                "widget": row_widget,
                "checkbox": checkbox,
                "prompt": prompt_combo,
                "target": audio_combo,
            }
        )
        self._update_summary()
        self._update_row_visibility()

