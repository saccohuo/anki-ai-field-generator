from functools import partial

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QCheckBox,
)


class DynamicForm(QWidget):
    def __init__(
        self,
        rows: list[tuple[str, str, bool]],
        card_fields: list[str],
    ):
        super().__init__()
        self.layout = QVBoxLayout(self)  # Main layout
        base_fields = list(card_fields)
        if "" not in base_fields:
            base_fields = [""] + base_fields
        self._card_fields = base_fields
        self._item_width = 250
        self._rows: list[dict[str, object]] = []
        self._control_buttons: list[QPushButton] = []
        self._master_override = False

        # Button to add new row
        self.add_button = QPushButton("Add Row")
        self.add_button.clicked.connect(partial(self.add_row, key="", field="", enabled=True))
        self._fill_initial_data(rows)
        self._create_controls()
        self.layout.addWidget(self.add_button)
        self.setLayout(self.layout)

    def _fill_initial_data(self, rows: list[tuple[str, str, bool]]):
        if rows:
            for key, field, enabled in rows:
                self.add_row(key, field, enabled)
        else:
            self.add_row()

    def add_row(self, key: str = "", field: str = "", enabled: bool = True):
        """
        Add an additional row
        """
        # Create a new horizontal layout for the row
        row_layout = QHBoxLayout()

        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.setEnabled(not self._master_override)
        row_layout.addWidget(checkbox)

        # Add a text box
        text_box = QLineEdit()
        row_layout.addWidget(text_box)
        text_box.setText(key)
        text_box.setMaximumWidth(self._item_width)

        # Add a dropdown
        combo_box = QComboBox()
        combo_box.setMaximumWidth(self._item_width)
        combo_box.addItems(self._card_fields)
        row_layout.addWidget(combo_box)
        combo_box.setCurrentText(field)

        # Add the row to the main layout above the buttons
        index = self.layout.count() - 1
        if index < 0:
            self.layout.addLayout(row_layout)
        else:
            self.layout.insertLayout(index, row_layout)

        self._rows.append(
            {
                "layout": row_layout,
                "checkbox": checkbox,
                "key": text_box,
                "field": combo_box,
            }
        )

    def clear_rows(self):
        """Remove all current key/field rows."""
        for row in self._rows:
            layout = row["layout"]
            if isinstance(layout, QHBoxLayout):
                while layout.count():
                    widget_item = layout.takeAt(0)
                    widget = widget_item.widget()
                    if widget is not None:
                        widget.deleteLater()
                self.layout.removeItem(layout)
        self._rows.clear()

    def set_inputs(self, keys: list[str], fields: list[str]):
        """Replace current rows with the provided key/field pairs."""
        rows = []
        if keys and fields and len(keys) == len(fields):
            rows = [(key, field, True) for key, field in zip(keys, fields)]
        self.set_rows(rows)

    def set_rows(self, rows: list[tuple[str, str, bool]]):
        self.clear_rows()
        if rows:
            for key, field, enabled in rows:
                self.add_row(key, field, enabled)
        else:
            self.add_row()

    def get_inputs(self):
        """
        Returns two lists: the fields and the values
        """
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

    def _create_controls(self) -> None:
        controls = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(lambda: self._set_all(True))
        select_none = QPushButton("Select None")
        select_none.clicked.connect(lambda: self._set_all(False))
        invert = QPushButton("Invert")
        invert.clicked.connect(self._invert_all)
        controls.addWidget(select_all)
        controls.addWidget(select_none)
        controls.addWidget(invert)
        controls.addStretch()
        self._control_buttons = [select_all, select_none, invert]
        self.layout.addLayout(controls)

    def _set_all(self, value: bool) -> None:
        if self._master_override:
            return
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(value)

    def _invert_all(self) -> None:
        if self._master_override:
            return
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(not checkbox.isChecked())

    def set_master_override(self, master_checked: bool) -> None:
        self._master_override = master_checked
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setEnabled(not master_checked)
        for button in self._control_buttons:
            button.setEnabled(not master_checked)


class ImageMappingForm(QWidget):
    def __init__(self, pairs: list[tuple[str, str]], card_fields: list[str]):
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
        self.add_button = QPushButton("Add Mapping")
        self.add_button.clicked.connect(lambda: self.add_row())
        if pairs:
            for entry in pairs:
                if isinstance(entry, (tuple, list)):
                    if len(entry) == 3:
                        prompt_field, image_field, enabled = entry  # type: ignore[misc]
                    elif len(entry) >= 2:
                        prompt_field, image_field = entry[:2]
                        enabled = True
                    else:
                        continue
                    self.add_row(prompt_field, image_field, bool(enabled))
                else:
                    self.add_row(str(entry), "")
        else:
            self.add_row()
        self._create_controls()
        self.layout.addWidget(self.add_button)
        self.setLayout(self.layout)

    def add_row(
        self,
        prompt_field: str = "",
        image_field: str = "",
        enabled: bool = True,
    ) -> None:
        row_layout = QHBoxLayout()

        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.setEnabled(not self._master_override)
        row_layout.addWidget(checkbox)

        prompt_combo = QComboBox()
        prompt_combo.setMaximumWidth(self._item_width)
        prompt_combo.addItems(self._card_fields)
        prompt_combo.setCurrentText(prompt_field)
        row_layout.addWidget(prompt_combo)

        image_combo = QComboBox()
        image_combo.setMaximumWidth(self._item_width)
        image_combo.addItems(self._card_fields)
        image_combo.setCurrentText(image_field)
        row_layout.addWidget(image_combo)

        index = self.layout.count() - 1
        if index < 0:
            self.layout.addLayout(row_layout)
        else:
            self.layout.insertLayout(index, row_layout)

        self._rows.append(
            {
                "layout": row_layout,
                "checkbox": checkbox,
                "prompt": prompt_combo,
                "target": image_combo,
            }
        )

    def clear_rows(self) -> None:
        for row in self._rows:
            layout = row["layout"]
            if isinstance(layout, QHBoxLayout):
                while layout.count():
                    widget_item = layout.takeAt(0)
                    widget = widget_item.widget()
                    if widget is not None:
                        widget.deleteLater()
                self.layout.removeItem(layout)
        self._rows.clear()

    def set_pairs(self, pairs: list[tuple[str, str]]) -> None:
        self.clear_rows()
        if pairs:
            for entry in pairs:
                enabled = True
                if len(entry) == 3:
                    prompt_field, image_field, enabled = entry  # type: ignore[misc]
                else:
                    prompt_field, image_field = entry
                self.add_row(prompt_field, image_field, bool(enabled))
        else:
            self.add_row()

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

    def _create_controls(self) -> None:
        controls = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(lambda: self._set_all(True))
        select_none = QPushButton("Select None")
        select_none.clicked.connect(lambda: self._set_all(False))
        invert = QPushButton("Invert")
        invert.clicked.connect(self._invert_all)
        controls.addWidget(select_all)
        controls.addWidget(select_none)
        controls.addWidget(invert)
        controls.addStretch()
        self._control_buttons = [select_all, select_none, invert]
        self.layout.addLayout(controls)

    def _set_all(self, value: bool) -> None:
        if self._master_override:
            return
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(value)

    def _invert_all(self) -> None:
        if self._master_override:
            return
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(not checkbox.isChecked())

    def set_master_override(self, master_checked: bool) -> None:
        self._master_override = master_checked
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setEnabled(not master_checked)
        for button in self._control_buttons:
            button.setEnabled(not master_checked)

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


class AudioMappingForm(QWidget):
    def __init__(self, pairs: list[tuple[str, str]], card_fields: list[str]):
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
        self.add_button = QPushButton("Add Mapping")
        self.add_button.clicked.connect(lambda: self.add_row())
        if pairs:
            for entry in pairs:
                if isinstance(entry, (tuple, list)):
                    if len(entry) == 3:
                        prompt_field, audio_field, enabled = entry  # type: ignore[misc]
                    elif len(entry) >= 2:
                        prompt_field, audio_field = entry[:2]
                        enabled = True
                    else:
                        continue
                    self.add_row(prompt_field, audio_field, bool(enabled))
                else:
                    self.add_row(str(entry), "")
        else:
            self.add_row()
        self._create_controls()
        self.layout.addWidget(self.add_button)
        self.setLayout(self.layout)

    def add_row(
        self,
        prompt_field: str = "",
        audio_field: str = "",
        enabled: bool = True,
    ) -> None:
        row_layout = QHBoxLayout()

        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.setEnabled(not self._master_override)
        row_layout.addWidget(checkbox)

        prompt_combo = QComboBox()
        prompt_combo.setMaximumWidth(self._item_width)
        prompt_combo.addItems(self._card_fields)
        prompt_combo.setCurrentText(prompt_field)
        row_layout.addWidget(prompt_combo)

        audio_combo = QComboBox()
        audio_combo.setMaximumWidth(self._item_width)
        audio_combo.addItems(self._card_fields)
        audio_combo.setCurrentText(audio_field)
        row_layout.addWidget(audio_combo)

        index = self.layout.count() - 1
        if index < 0:
            self.layout.addLayout(row_layout)
        else:
            self.layout.insertLayout(index, row_layout)

        self._rows.append(
            {
                "layout": row_layout,
                "checkbox": checkbox,
                "prompt": prompt_combo,
                "target": audio_combo,
            }
        )

    def clear_rows(self) -> None:
        for row in self._rows:
            layout = row["layout"]
            if isinstance(layout, QHBoxLayout):
                while layout.count():
                    widget_item = layout.takeAt(0)
                    widget = widget_item.widget()
                    if widget is not None:
                        widget.deleteLater()
                self.layout.removeItem(layout)
        self._rows.clear()

    def set_pairs(self, pairs: list[tuple[str, str]]) -> None:
        self.clear_rows()
        if pairs:
            for entry in pairs:
                if isinstance(entry, (tuple, list)):
                    if len(entry) == 3:
                        prompt_field, audio_field, enabled = entry  # type: ignore[misc]
                    elif len(entry) >= 2:
                        prompt_field, audio_field = entry[:2]
                        enabled = True
                    else:
                        continue
                    self.add_row(prompt_field, audio_field, bool(enabled))
                else:
                    self.add_row(str(entry), "")
        else:
            self.add_row()

    def get_pairs(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            prompt_widget: QComboBox = row["prompt"]  # type: ignore[assignment]
            audio_widget: QComboBox = row["target"]  # type: ignore[assignment]
            prompt_value = prompt_widget.currentText().strip()
            audio_value = audio_widget.currentText().strip()
            if not prompt_value or not audio_value:
                continue
            if self._master_override or checkbox.isChecked():
                pairs.append((prompt_value, audio_value))
        return pairs

    def get_all_rows(self) -> list[tuple[str, str, bool]]:
        rows: list[tuple[str, str, bool]] = []
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            prompt_widget: QComboBox = row["prompt"]  # type: ignore[assignment]
            audio_widget: QComboBox = row["target"]  # type: ignore[assignment]
            rows.append(
                (
                    prompt_widget.currentText().strip(),
                    audio_widget.currentText().strip(),
                    checkbox.isChecked(),
                )
            )
        return rows

    def _create_controls(self) -> None:
        controls = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(lambda: self._set_all(True))
        select_none = QPushButton("Select None")
        select_none.clicked.connect(lambda: self._set_all(False))
        invert = QPushButton("Invert")
        invert.clicked.connect(self._invert_all)
        controls.addWidget(select_all)
        controls.addWidget(select_none)
        controls.addWidget(invert)
        controls.addStretch()
        self._control_buttons = [select_all, select_none, invert]
        self.layout.addLayout(controls)

    def _set_all(self, value: bool) -> None:
        if self._master_override:
            return
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(value)

    def _invert_all(self) -> None:
        if self._master_override:
            return
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(not checkbox.isChecked())

    def set_master_override(self, master_checked: bool) -> None:
        self._master_override = master_checked
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setEnabled(not master_checked)
        for button in self._control_buttons:
            button.setEnabled(not master_checked)
