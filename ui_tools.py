from aqt.qt import (
    QComboBox,
    QFont,
    QLabel,
    QLineEdit,
    QSettings,
    QTextEdit,
)


class UITools:
    def __init__(self, settings: QSettings, max_width):
        self.label_font = self.get_label_font()
        self.max_width = max_width
        self.settings = settings
        self.widgets = {}

    def get_label_font(self):
        label_font = QFont()
        label_font.setBold(True)
        label_font.setPointSize(14)
        return label_font

    def create_label(self, label_text):
        label = QLabel(label_text)
        label.setFont(self.label_font)
        return label

    def create_descriptive_text(self, text):
        label = QLabel(text)
        label.setMaximumWidth(self.max_width)
        label.setWordWrap(True)
        return label

    def create_dropdown(self, setting_name, items: list[str]):
        combo_box = QComboBox()
        combo_box.setMaximumWidth(self.max_width)
        combo_box.addItems(items)
        setting_value = self.settings.value(setting_name)
        combo_box.setCurrentText(setting_value)
        self.widgets[setting_name] = combo_box
        return combo_box

    def create_text_entry(self, setting_name, placeholder=""):
        setting_value = self.settings.value(setting_name)
        if setting_value is None:
            setting_value = ""
        entry = QLineEdit(setting_value)
        entry.setPlaceholderText(placeholder)
        entry.setMaximumWidth(self.max_width)
        self.widgets[setting_name] = entry
        return entry

    def create_text_edit(self, setting_name, placeholder="", max_height=200):
        text_edit = QTextEdit()
        text_edit.setMinimumSize(self.max_width, max_height)
        setting_value = self.settings.value(setting_name)
        text_edit.setText(setting_value or "")
        text_edit.setPlaceholderText(placeholder)
        self.widgets[setting_name] = text_edit
        return text_edit

    def save_settings(self):
        settings_values = self.get_settings()
        for setting_name, value in settings_values.items():
            self.settings.setValue(setting_name, value)

    def get_settings(self):
        settings = {}
        for setting_name, widget in self.widgets.items():
            if isinstance(widget, QTextEdit):
                settings[setting_name] = widget.toPlainText()
            elif isinstance(widget, QLineEdit):
                settings[setting_name] = widget.text()
            elif isinstance(widget, QComboBox):
                settings[setting_name] = widget.currentText()
        return settings
