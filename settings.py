from aqt import mw, pyqtSignal, QObject
from aqt.qt import QSettings, QLabel, QDialog, QWidget, QVBoxLayout, QFont, QLineEdit, QTextEdit, QDialogButtonBox, QScrollArea
from aqt.qt import Qt


API_KEY_SETTING_NAME = "api_key"
SYSTEM_PROMPT_SETTING_NAME = "system_prompt"
USER_PROMPT_SETTING_NAME = "user_prompt"
RESPONSE_KEYS_SETTING_NAME = "response_keys"


class Settings(QObject):
    SETTINGS_ORGANIZATION = "github_rroessler1"
    SETTINGS_APPLICATION = "anki-gpt-plugin"
    on_change = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.app_settings = QSettings(self.SETTINGS_ORGANIZATION, self.SETTINGS_APPLICATION)

    def _on_settings_dialog_changed(self):
        self.on_change.emit()

    def show(self, parent):
        # TODO: instead of creating a new object every time I could just reload the settings,
        # it would be cleaner. Currently not a problem though.
        settings_dialog = SettingsDialog(self.app_settings, parent)
        settings_dialog.on_change.connect(self._on_settings_dialog_changed)
        settings_dialog.show()

    def get_setting(self, setting_name):
        return self.app_settings.value(setting_name, defaultValue="", type=str)

    def get_api_key(self):
        return self.get_setting(API_KEY_SETTING_NAME)

    def get_system_prompt(self):
        return self.get_setting(SYSTEM_PROMPT_SETTING_NAME)

    def get_user_prompt(self):
        return self.get_setting(USER_PROMPT_SETTING_NAME)

    def get_response_keys(self):
        return self.get_setting(RESPONSE_KEYS_SETTING_NAME)


class SettingsDialog(QDialog):
    on_change = pyqtSignal()

    def __init__(self, app_settings: QSettings, *args, **kwargs):
        super(SettingsDialog, self).__init__(*args, **kwargs)
        self.app_settings = app_settings

        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle("Anki GPT Settings")
        container_widget = QWidget()
        layout = QVBoxLayout(container_widget)

        # Define fonts
        label_font = QFont()
        label_font.setBold(True)
        label_font.setPointSize(14)

        # Single-line text entry
        api_key_label = QLabel("OpenAI API Key:")
        api_key_label.setFont(label_font)
        self.api_key_entry = QLineEdit()
        self.api_key_entry.setText(self.app_settings.value(API_KEY_SETTING_NAME, defaultValue="", type=str))

        # Multi-line text area
        system_prompt_label = QLabel("System Prompt:")
        system_prompt_label.setFont(label_font)
        system_prompt_description = QLabel(("Enter the System Prompt that is the overall system instructions.\n"
                                   "This is where you should give very specific instructions, examples, and do \"prompt engineering\".\n"
                                   "For more examples, see:\n"
                                   "https://platform.openai.com/docs/guides/prompt-engineering/strategy-write-clear-instructions"))
        self.system_prompt_text_edit = QTextEdit()
        self.system_prompt_text_edit.setText(self.app_settings.value(SYSTEM_PROMPT_SETTING_NAME, defaultValue="", type=str))
        self.system_prompt_text_edit.setPlaceholderText(
            ("Example:\n"
             "You are a helpful German teacher.  You will be provided with a series of: a German word delimited by triple quotes, "
             "followed by a German sentence.  For each word and sentence pair, follow the below steps:\n\n"
             "- Give a very slightly modified version of the sentence - for example, use a different subject, "
             "verb, or object - while still using the provided German word.  Only change one or two words in the sentence.\n\n"
             "- Translate the modified sentence into English."))

        # Multi-line text area
        user_prompt_label = QLabel("User Prompt:")
        user_prompt_label.setFont(label_font)
        user_prompt_description = QLabel(("Enter the prompt that will be created and sent for each card.\n"
                                   "Use the field name surrounded by braces to substitute in a field from the card."))
        self.user_prompt_text_edit = QTextEdit()
        self.user_prompt_text_edit.setText(self.app_settings.value(USER_PROMPT_SETTING_NAME, defaultValue="", type=str))
        self.user_prompt_text_edit.setPlaceholderText(
            ("Example:\n"
             '"""{german_word}"""\n\n{german_sentence}\n'))

        # Response configuration
        response_label = QLabel("Response Fields:")
        response_label.setFont(label_font)
        response_description = QLabel(("Enter a meaningful name for each piece of data you require the model to return, separated by commas.\n"
                                    "This should correspond to the instructions you provided in the System Prompt, and follow the same order.\n"
                                    "For example, in the above example System Prompt, you want this data returned:\n"
                                    "sentence, translation\n"
                                    "Or, if you want the model to generate some example sentences, then maybe you want:\n"
                                    "exampleSentence1, exampleSentence2, exampleSentence3\n"))
        self.response_keys_entry = QLineEdit()
        self.response_keys_entry.setText(self.app_settings.value(RESPONSE_KEYS_SETTING_NAME, defaultValue="", type=str))
        self.response_keys_entry.setPlaceholderText("sentence, translation")

        response_usage_label = QLabel("Using the Response in your Cards:")
        response_usage_label.setFont(label_font)
        response_usage_description = QLabel(("The model's responses will be stored using the data keys you specified above.\n"
                                    "Now, in Anki, you need to customize your Card Templates: (Click on a deck -> Browse -> Cards...).\n"
                                    "Place the name of the data, with a colon, before a field to replace that field.\n"
                                    "Or, add the name of the data, with a colon, to display it in a new place on the card.\n"
                                    "Ex. {Front} {exampleSentence1:} {exampleSentence2:} {exampleSentence3:}\n"
                                    "will put 3 new example sentences on the Front of your card.\n"))

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

        layout.addWidget(response_label)
        layout.addWidget(response_description)
        layout.addWidget(self.response_keys_entry)

        layout.addWidget(response_usage_label)
        layout.addWidget(response_usage_description)

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
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
        self.app_settings.setValue(API_KEY_SETTING_NAME, self.api_key_entry.text())
        self.app_settings.setValue(SYSTEM_PROMPT_SETTING_NAME, self.system_prompt_text_edit.toPlainText())
        self.app_settings.setValue(USER_PROMPT_SETTING_NAME, self.user_prompt_text_edit.toPlainText())
        self.app_settings.setValue(RESPONSE_KEYS_SETTING_NAME, self.response_keys_entry.text())
        self.on_change.emit()
        super(SettingsDialog, self).accept()

    def reject(self):
        super(SettingsDialog, self).reject()
