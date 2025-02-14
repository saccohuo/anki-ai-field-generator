from aqt import QObject
from aqt.qt import (
    QSettings,
    QLabel,
    QDialog,
    QWidget,
    QVBoxLayout,
    QFont,
    QLineEdit,
    QTextEdit,
    QDialogButtonBox,
    QScrollArea,
    QComboBox,
)
from aqt.qt import Qt
from collections.abc import Callable

from .note_processor import NoteProcessor
from .openai_client import OpenAIClient
from .prompt_config import PromptConfig
from .settings import SettingsNames, get_settings


# I think I should have:
# - something generic that adds menubar things
# - something generic that loads settings
# - ideally something generic-ish that passes information through
# - an action-custom dialog


class ModifyCardsUI(QObject):

    def __init__(self):
        super().__init__()
        self.app_settings = get_settings()

    def show(self, browser):
        self.notes = [
            browser.mw.col.getNote(note_id) for note_id in browser.selectedNotes()
        ]

        dialog = ModifyCardsDialog(
            self.app_settings, self.notes, self.on_submit, browser
        )
        dialog.show()

    def on_submit(self):
        prompt_config = PromptConfig(self.app_settings)
        client = OpenAIClient(prompt_config)
        note_processor = NoteProcessor(prompt_config, self.notes, client)
        note_processor.process(missing_field_is_error=True)


class ModifyCardsDialog(QDialog):

    def __init__(
        self, app_settings: QSettings, notes: list, on_submit: Callable, *args, **kwargs
    ):
        super(ModifyCardsDialog, self).__init__(*args, **kwargs)
        self.app_settings: QSettings = app_settings
        self._on_submit: Callable = on_submit
        self._notes = notes
        self._fields = sorted({field for note in notes for field in note.keys()})

        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle("Anki AI - Modify Cards")
        container_widget = QWidget()
        layout = QVBoxLayout(container_widget)

        # Define fonts
        label_font = QFont()
        label_font.setBold(True)
        label_font.setPointSize(14)

        # Misc
        help_label = QLabel(f"{len(self._notes)} cards selected.")
        help_label.setFont(label_font)
        layout.addWidget(help_label)

        # Single-line text entry
        api_key_label = QLabel("OpenAI API Key:")
        api_key_label.setFont(label_font)
        self.api_key_entry = QLineEdit()
        self.api_key_entry.setText(
            self.app_settings.value(
                SettingsNames.API_KEY_SETTING_NAME, defaultValue="", type=str
            )
        )

        # Multi-line text area
        system_prompt_label = QLabel("System Prompt:")
        system_prompt_label.setFont(label_font)
        system_prompt_description = QLabel(
            (
                "Enter the System Prompt that is the overall system instructions.\n"
                'This is where you should give very specific instructions, examples, and do "prompt engineering".\n'
                "For more examples, see:\n"
                "https://platform.openai.com/docs/guides/prompt-engineering/strategy-write-clear-instructions"
            )
        )
        self.system_prompt_text_edit = QTextEdit()
        self.system_prompt_text_edit.setText(
            self.app_settings.value(
                SettingsNames.SYSTEM_PROMPT_SETTING_NAME, defaultValue="", type=str
            )
        )
        self.system_prompt_text_edit.setPlaceholderText(
            (
                "Example:\n"
                "You are a helpful German teacher.  You will be provided with a series of: a German word delimited by triple quotes, "
                "followed by a German sentence.  For each word and sentence pair, follow the below steps:\n\n"
                "- Give a very slightly modified version of the sentence - for example, use a different subject, "
                "verb, or object - while still using the provided German word.  Only change one or two words in the sentence.\n\n"
                "- Translate the modified sentence into English."
            )
        )

        # Multi-line text area
        user_prompt_label = QLabel("User Prompt:")
        user_prompt_label.setFont(label_font)
        user_prompt_description = QLabel(
            (
                "Enter the prompt that will be created and sent for each card.\n"
                "Use the field name surrounded by braces to substitute in a field from the card."
            )
        )
        self.user_prompt_text_edit = QTextEdit()
        self.user_prompt_text_edit.setText(
            self.app_settings.value(
                SettingsNames.USER_PROMPT_SETTING_NAME, defaultValue="", type=str
            )
        )
        self.user_prompt_text_edit.setPlaceholderText(
            ("Example:\n" '"""{german_word}"""\n\n{german_sentence}\n')
        )
        available_fields_description = QLabel(
            f"Available fields: {', '.join(self._fields)}"
        )

        # Destination Configuration
        destination_label = QLabel("Destination Field:")
        destination_label.setFont(label_font)
        destination_description = QLabel(
            "Select which field the response should be written to."
        )
        destination_fields_dropdown = QComboBox()
        for field in self._fields:
            destination_fields_dropdown.addItem(field, field)

        # Add the label and text entry to the layout
        layout.addWidget(api_key_label)
        layout.addWidget(self.api_key_entry)

        # Add the label and multi-line text area to the layout
        layout.addWidget(system_prompt_label)
        layout.addWidget(system_prompt_description)
        layout.addWidget(self.system_prompt_text_edit)

        layout.addWidget(user_prompt_label)
        layout.addWidget(user_prompt_description)
        layout.addWidget(self.user_prompt_text_edit)
        layout.addWidget(available_fields_description)

        layout.addWidget(destination_label)
        layout.addWidget(destination_description)
        layout.addWidget(destination_fields_dropdown)

        buttons = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttonBox = QDialogButtonBox(buttons)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container_widget)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)

    def accept(self):
        self.app_settings.setValue(
            SettingsNames.API_KEY_SETTING_NAME, self.api_key_entry.text()
        )
        self.app_settings.setValue(
            SettingsNames.SYSTEM_PROMPT_SETTING_NAME,
            self.system_prompt_text_edit.toPlainText(),
        )
        self.app_settings.setValue(
            SettingsNames.USER_PROMPT_SETTING_NAME,
            self.user_prompt_text_edit.toPlainText(),
        )
        self._on_submit()
        super(ModifyCardsDialog, self).accept()

    def reject(self):
        super(ModifyCardsDialog, self).reject()
