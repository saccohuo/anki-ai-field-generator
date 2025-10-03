from functools import partial

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
)


class DynamicForm(QWidget):
    def __init__(self, keys: list[str], fields: list[str], card_fields: list[str]):
        super().__init__()
        self.layout = QVBoxLayout(self)  # Main layout
        base_fields = list(card_fields)
        if "" not in base_fields:
            base_fields = [""] + base_fields
        self._card_fields = base_fields
        self._item_width = 250

        # Button to add new row
        self.add_button = QPushButton("Add Row")
        self.add_button.clicked.connect(partial(self.add_row, key="", field=""))
        self._fill_initial_data(keys, fields, card_fields)
        self.layout.addWidget(self.add_button)
        self.setLayout(self.layout)

    def _fill_initial_data(
        self, keys: list[str], fields: list[str], card_fields: list[str]
    ):
        all_fields_valid = (
            all(field in card_fields for field in fields) and len(fields) > 0
        )
        if all_fields_valid:
            for key, field in zip(keys, fields):
                self.add_row(key, field)
        else:
            self.add_row()

    def add_row(self, key="", field=""):
        """
        Add an additional row
        """
        # Create a new horizontal layout for the row
        row_layout = QHBoxLayout()

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

    def clear_rows(self):
        """Remove all current key/field rows."""
        # Leave the add button (last item) intact.
        for index in reversed(range(self.layout.count() - 1)):
            item = self.layout.itemAt(index)
            if isinstance(item, QHBoxLayout):
                while item.count():
                    widget_item = item.takeAt(0)
                    widget = widget_item.widget()
                    if widget is not None:
                        widget.deleteLater()
                self.layout.removeItem(item)

    def set_inputs(self, keys: list[str], fields: list[str]):
        """Replace current rows with the provided key/field pairs."""
        self.clear_rows()
        if keys and fields and len(keys) == len(fields):
            for key, field in zip(keys, fields):
                self.add_row(key, field)
        else:
            self.add_row()

    def get_inputs(self):
        """
        Returns two lists: the fields and the values
        """
        # Iterate through all rows and gather inputs
        keys = []
        fields = []
        for i in range(self.layout.count()):
            item = self.layout.itemAt(i)
            key = ""
            field = ""
            if isinstance(item, QHBoxLayout):
                for j in range(item.count()):
                    widget = item.itemAt(j).widget()
                    if isinstance(widget, QLineEdit):
                        key = widget.text()
                    elif isinstance(widget, QComboBox):
                        field = widget.currentText()
                    if key and field:
                        keys.append(key)
                        fields.append(field)

        return keys, fields


class ImageMappingForm(QWidget):
    def __init__(self, pairs: list[tuple[str, str]], card_fields: list[str]):
        super().__init__()
        base_fields = list(card_fields)
        if "" not in base_fields:
            base_fields = [""] + base_fields
        self._card_fields = base_fields
        self._item_width = 250
        self.layout = QVBoxLayout(self)
        self.add_button = QPushButton("Add Mapping")
        self.add_button.clicked.connect(lambda: self.add_row())
        if pairs:
            for prompt_field, image_field in pairs:
                self.add_row(prompt_field, image_field)
        else:
            self.add_row()
        self.layout.addWidget(self.add_button)
        self.setLayout(self.layout)

    def add_row(self, prompt_field: str = "", image_field: str = "") -> None:
        row_layout = QHBoxLayout()

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

    def clear_rows(self) -> None:
        for index in reversed(range(self.layout.count() - 1)):
            item = self.layout.itemAt(index)
            if isinstance(item, QHBoxLayout):
                while item.count():
                    widget_item = item.takeAt(0)
                    widget = widget_item.widget()
                    if widget is not None:
                        widget.deleteLater()
                self.layout.removeItem(item)

    def set_pairs(self, pairs: list[tuple[str, str]]) -> None:
        self.clear_rows()
        if pairs:
            for prompt_field, image_field in pairs:
                self.add_row(prompt_field, image_field)
        else:
            self.add_row()

    def get_pairs(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for index in range(self.layout.count() - 1):
            item = self.layout.itemAt(index)
            if isinstance(item, QHBoxLayout) and item.count() >= 2:
                prompt_widget = item.itemAt(0).widget()
                image_widget = item.itemAt(1).widget()
                prompt_value = prompt_widget.currentText().strip() if isinstance(prompt_widget, QComboBox) else ""
                image_value = image_widget.currentText().strip() if isinstance(image_widget, QComboBox) else ""
                if prompt_value and image_value:
                    pairs.append((prompt_value, image_value))
        return pairs


class AudioMappingForm(QWidget):
    def __init__(self, pairs: list[tuple[str, str]], card_fields: list[str]):
        super().__init__()
        base_fields = list(card_fields)
        if "" not in base_fields:
            base_fields = [""] + base_fields
        self._card_fields = base_fields
        self._item_width = 250
        self.layout = QVBoxLayout(self)
        self.add_button = QPushButton("Add Mapping")
        self.add_button.clicked.connect(lambda: self.add_row())
        if pairs:
            for prompt_field, audio_field in pairs:
                self.add_row(prompt_field, audio_field)
        else:
            self.add_row()
        self.layout.addWidget(self.add_button)
        self.setLayout(self.layout)

    def add_row(self, prompt_field: str = "", audio_field: str = "") -> None:
        row_layout = QHBoxLayout()

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

    def clear_rows(self) -> None:
        for index in reversed(range(self.layout.count() - 1)):
            item = self.layout.itemAt(index)
            if isinstance(item, QHBoxLayout):
                while item.count():
                    widget_item = item.takeAt(0)
                    widget = widget_item.widget()
                    if widget is not None:
                        widget.deleteLater()
                self.layout.removeItem(item)

    def set_pairs(self, pairs: list[tuple[str, str]]) -> None:
        self.clear_rows()
        if pairs:
            for prompt_field, audio_field in pairs:
                self.add_row(prompt_field, audio_field)
        else:
            self.add_row()

    def get_pairs(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for index in range(self.layout.count() - 1):
            item = self.layout.itemAt(index)
            if isinstance(item, QHBoxLayout) and item.count() >= 2:
                prompt_widget = item.itemAt(0).widget()
                audio_widget = item.itemAt(1).widget()
                prompt_value = prompt_widget.currentText().strip() if isinstance(prompt_widget, QComboBox) else ""
                audio_value = audio_widget.currentText().strip() if isinstance(audio_widget, QComboBox) else ""
                if prompt_value and audio_value:
                    pairs.append((prompt_value, audio_value))
        return pairs
