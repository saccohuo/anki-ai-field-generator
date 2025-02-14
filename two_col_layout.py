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
        self._card_fields = [""] + card_fields if card_fields[0] != "" else card_fields
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
        self.layout.insertLayout(self.layout.count() - 1, row_layout)

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

        # For now, print the gathered data
        print("Collected Data:")
        print(f"Keys: {','.join(keys)}")
        print(f"Fields: {','.join(fields)}")
        return keys, fields
