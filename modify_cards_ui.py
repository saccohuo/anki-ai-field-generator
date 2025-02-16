from collections.abc import Callable
from aqt import QObject
from aqt.qt import (
    QSettings,
    QLabel,
    QDialog,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFont,
    QLineEdit,
    Qt,
    QTextEdit,
    QDialogButtonBox,
    QScrollArea,
)

from .note_processor import NoteProcessor
from .openai_client import OpenAIClient
from .progress_bar import ProgressDialog
from .prompt_config import PromptConfig
from .settings import SettingsNames, get_settings
from .two_col_layout import DynamicForm


# I think I should have:
# - something generic that adds menubar things
# - something generic that loads settings
# - ideally something generic-ish that passes information through
# - an action-custom dialog


class ModifyCardsUI(QObject):

    def __init__(self):
        super().__init__()
        self.app_settings = get_settings()
        self.notes = []

    def show(self, browser):
        self.notes = [
            browser.mw.col.get_note(note_id) for note_id in browser.selectedNotes()
        ]

        self.dialog = ModifyCardsDialog(
            self.app_settings,
            self.notes,
            lambda: self.on_submit(browser=browser),
            browser,
        )
        self.dialog.show()

    def on_submit(self, browser):
        prompt_config = PromptConfig(self.app_settings)
        client = OpenAIClient(prompt_config)
        note_processor = NoteProcessor(
            prompt_config, self.notes, client, self.app_settings
        )
        dialog = ProgressDialog(note_processor)
        dialog.exec()
        browser.mw.reset()


class ModifyCardsDialog(QDialog):

    def __init__(
        self, app_settings: QSettings, notes: list, on_submit: Callable, *args, **kwargs
    ):
        super(ModifyCardsDialog, self).__init__(*args, **kwargs)
        self.app_settings: QSettings = app_settings
        self._on_submit: Callable = on_submit
        self._notes = notes
        self._card_fields = sorted({field for note in notes for field in note.keys()})
        self._width = 500
        self._height = 300

        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle("Anki AI - Modify Cards")
        self.resize(self._width * 2 + 20, 750)
        container_widget = QWidget()
        main_layout = QHBoxLayout(container_widget)

        left_container = QWidget()
        left_container.setMaximumWidth(self._width)
        left_layout = QVBoxLayout()
        left_container.setLayout(left_layout)

        # Define fonts
        label_font = QFont()
        label_font.setBold(True)
        label_font.setPointSize(14)

        # Single-line text entry
        api_key_label = QLabel("OpenAI API Key:")
        api_key_label.setFont(label_font)
        self.api_key_entry = QLineEdit(
            self.app_settings.value(
                SettingsNames.API_KEY_SETTING_NAME, defaultValue="", type=str
            )
        )
        self.api_key_entry.setMaximumWidth(self._width)
        left_layout.addWidget(api_key_label)
        left_layout.addWidget(self.api_key_entry)

        # Multi-line text area
        system_prompt_label = QLabel("System Prompt:")
        system_prompt_label.setFont(label_font)
        system_prompt_description = QLabel(
            (
                "Enter the System Prompt that is the overall system instructions.\n"
                'This is where you should give very specific instructions, examples, and do "prompt engineering". '
                "For more examples, see:\n"
                "https://platform.openai.com/docs/guides/prompt-engineering/strategy-write-clear-instructions"
            )
        )
        system_prompt_description.setMaximumWidth(self._width)
        system_prompt_description.setWordWrap(True)
        self.system_prompt_text_edit = QTextEdit()
        self.system_prompt_text_edit.setMaximumSize(self._width, self._height)
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
        left_layout.addWidget(system_prompt_label)
        left_layout.addWidget(system_prompt_description)
        left_layout.addWidget(self.system_prompt_text_edit)
        left_layout.addStretch()

        # Right Column
        right_container = QWidget()
        right_container.setMaximumWidth(self._width)
        right_layout = QVBoxLayout()
        right_container.setLayout(right_layout)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Multi-line text area
        user_prompt_label = QLabel("User Prompt:")
        user_prompt_label.setFont(label_font)
        user_prompt_description = QLabel(
            (
                "Enter the prompt that will be created and sent for each card.\n"
                "Use the field name surrounded by braces to substitute in a field from the card."
            )
        )
        user_prompt_description.setWordWrap(True)
        self.user_prompt_text_edit = QTextEdit()
        self.user_prompt_text_edit.setMaximumSize(self._width, self._height)
        self.user_prompt_text_edit.setText(
            self.app_settings.value(
                SettingsNames.USER_PROMPT_SETTING_NAME, defaultValue="", type=str
            )
        )
        self.user_prompt_text_edit.setPlaceholderText(
            ("Example:\n" '"""{german_word}"""\n\n{german_sentence}\n')
        )
        right_layout.addWidget(user_prompt_label)
        right_layout.addWidget(user_prompt_description)
        right_layout.addWidget(self.user_prompt_text_edit)

        available_fields_description = QLabel(
            f"Available fields: {', '.join(self._card_fields)}"
        )
        available_fields_description.setWordWrap(True)
        right_layout.addWidget(available_fields_description)

        # Destination Configuration
        destination_label = QLabel("Save the AI output to the Anki fields:")
        destination_label.setFont(label_font)

        mapping_instruction_text = """
        For each piece of information the AI gives you, type its label from the AI and select the Anki field where you want to save it.<br><br>
        <b>Example:</b> If you asked the AI for a German sentence and its translation, and your Anki fields are <code>de_sentence</code> and <code>en_sentence</code>, enter:
        <pre>exampleSentence de_sentence<br>translation en_sentence</pre>
        """

        destination_description = QLabel(mapping_instruction_text)
        destination_description.setWordWrap(True)

        self.two_col_form = DynamicForm(
            self.app_settings.value(
                SettingsNames.RESPONSE_KEYS_SETTING_NAME, type="QStringList"
            ),
            self.app_settings.value(
                SettingsNames.DESTINATION_FIELD_SETTING_NAME, type="QStringList"
            ),
            self._card_fields,
        )
        right_layout.addWidget(destination_label)
        right_layout.addWidget(destination_description)
        right_layout.addWidget(self.two_col_form)

        # Misc
        help_label = QLabel(f"{len(self._notes)} cards selected. Modify cards?")
        right_layout.addWidget(help_label)

        buttons = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box = QDialogButtonBox(buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        right_layout.addWidget(self.button_box)

        main_layout.addWidget(left_container)
        main_layout.addWidget(right_container)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container_widget)

        final_layout = QVBoxLayout(self)
        final_layout.addWidget(scroll_area)
        self.setLayout(final_layout)

    def accept(self):
        """
        Saves settings when user accepts.
        """
        self.app_settings.setValue(
            SettingsNames.API_KEY_SETTING_NAME, self.api_key_entry.text()
        )
        keys, fields = self.two_col_form.get_inputs()
        self.app_settings.setValue(SettingsNames.RESPONSE_KEYS_SETTING_NAME, keys)
        self.app_settings.setValue(
            SettingsNames.DESTINATION_FIELD_SETTING_NAME,
            fields,
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
