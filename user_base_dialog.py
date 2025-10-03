from abc import ABCMeta, abstractmethod
from anki.notes import Note as AnkiNote
from aqt.qt import (
    QSettings,
    QWidget,
    QHBoxLayout,
    QMessageBox,
    QVBoxLayout,
    Qt,
    QScrollArea,
)
from PyQt6 import QtCore
from .settings import SettingsNames
from .two_col_layout import DynamicForm, ImageMappingForm, AudioMappingForm
from .ui_tools import UITools
from .gemini_client import GeminiClient


# I think I should have:
# - something generic that adds menubar things
# - something generic that loads settings
# - ideally something generic-ish that passes information through
# - an action-custom dialog


class MyMeta(ABCMeta, type(QtCore.QObject)):
    pass


IMAGE_MAPPING_SEPARATOR = "->"


class UserBaseDialog(QWidget, metaclass=MyMeta):
    def __init__(self, app_settings: QSettings, selected_notes: list[AnkiNote]):
        super().__init__()
        self._width = 500
        self.app_settings: QSettings = app_settings
        self.selected_notes = selected_notes
        self.ui_tools: UITools = UITools(app_settings, self._width)
        self.image_mapping_form: ImageMappingForm | None = None
        self.audio_mapping_form: AudioMappingForm | None = None
        self._audio_api_key_entry = None
        self._audio_endpoint_entry = None
        self._audio_model_entry = None
        self._audio_voice_entry = None
        self._audio_format_entry = None

    def show(self):
        if self.layout() is not None:
            QWidget().setLayout(self.layout())  # Clears any existing layout
        card_fields = sorted(
            {field for note in self.selected_notes for field in note.keys()}
        )

        self.resize(self._width * 2 + 20, 750)
        container_widget = QWidget()
        main_layout = QHBoxLayout(container_widget)

        left_container = QWidget()
        left_container.setMaximumWidth(self._width)
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_container.setLayout(left_layout)

        self.add_models_dropdown(left_layout)
        self.add_api_key(left_layout)
        self.add_system_prompt(
            left_layout, self.system_prompt_description, self.system_prompt_placeholder
        )
        left_layout.addStretch()

        # Right Column
        right_container = QWidget()
        right_container.setMaximumWidth(self._width)
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_container.setLayout(right_layout)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # User Prompt
        self.add_user_prompt(
            right_layout, self.user_prompt_description, self.user_prompt_placeholder
        )
        # Available Fields
        right_layout.addWidget(
            self.ui_tools.create_descriptive_text(
                f"Available fields: {', '.join(card_fields)}"
            )
        )

        # Destination Configuration
        right_layout.addWidget(
            self.ui_tools.create_label("Save the AI output to the Anki fields:")
        )
        right_layout.addWidget(
            self.ui_tools.create_descriptive_text(self.mapping_instruction_text)
        )
        self.two_col_form = DynamicForm(
            self.app_settings.value(
                SettingsNames.RESPONSE_KEYS_SETTING_NAME, type="QStringList"
            ),
            self.app_settings.value(
                SettingsNames.DESTINATION_FIELD_SETTING_NAME, type="QStringList"
            ),
            card_fields,
        )
        right_layout.addWidget(self.two_col_form)

        # Image Generation Mapping
        right_layout.addWidget(
            self.ui_tools.create_label("Image Generation Mapping:")
        )
        right_layout.addWidget(
            self.ui_tools.create_descriptive_text(
                "Map a prompt field to the field that should receive the generated image. When the prompt field contains text, the configured image model will be invoked and the resulting image will be saved into the mapped field."
            )
        )
        image_mapping_strings = self.app_settings.value(
            SettingsNames.IMAGE_MAPPING_SETTING_NAME, type="QStringList"
        ) or []
        pairs = [
            tuple(part.strip() for part in mapping.split(IMAGE_MAPPING_SEPARATOR, 1))
            for mapping in image_mapping_strings
            if IMAGE_MAPPING_SEPARATOR in mapping
        ]
        self.image_mapping_form = ImageMappingForm(pairs, card_fields)
        right_layout.addWidget(self.image_mapping_form)

        right_layout.addWidget(
            self.ui_tools.create_label("Image Generation (optional):")
        )
        image_key_entry = self.ui_tools.create_text_entry(
            SettingsNames.IMAGE_API_KEY_SETTING_NAME,
            "Override Gemini API key for image generation"
        )
        right_layout.addWidget(image_key_entry)
        self._image_api_key_entry = image_key_entry
        default_endpoint = "https://generativelanguage.googleapis.com/v1beta/models"
        image_endpoint_entry = self.ui_tools.create_text_entry(
            SettingsNames.IMAGE_ENDPOINT_SETTING_NAME,
            f"Custom image endpoint (default {default_endpoint})"
        )
        right_layout.addWidget(image_endpoint_entry)
        image_model_entry = self.ui_tools.create_text_entry(
            SettingsNames.IMAGE_MODEL_SETTING_NAME,
            f"Image model name (default {GeminiClient.IMAGE_MODEL})"
        )
        if not image_model_entry.text().strip():
            image_model_entry.setText(GeminiClient.IMAGE_MODEL)
        right_layout.addWidget(image_model_entry)

        right_layout.addWidget(
            self.ui_tools.create_label("Speech Generation Mapping:")
        )
        right_layout.addWidget(
            self.ui_tools.create_descriptive_text(
                "Map the text field that should be spoken to the field that should receive the audio tag. The plugin reads the text from the first field, synthesizes speech, and writes only a [sound:] tag into the second field."
            )
        )
        audio_mapping_strings = self.app_settings.value(
            SettingsNames.AUDIO_MAPPING_SETTING_NAME, type="QStringList"
        ) or []
        audio_pairs = [
            tuple(part.strip() for part in mapping.split(IMAGE_MAPPING_SEPARATOR, 1))
            for mapping in audio_mapping_strings
            if IMAGE_MAPPING_SEPARATOR in mapping
        ]
        self.audio_mapping_form = AudioMappingForm(audio_pairs, card_fields)
        right_layout.addWidget(self.audio_mapping_form)

        right_layout.addWidget(
            self.ui_tools.create_label("Speech Generation (optional):")
        )
        audio_key_entry = self.ui_tools.create_text_entry(
            SettingsNames.AUDIO_API_KEY_SETTING_NAME,
            "Speech API key (required for audio generation)"
        )
        right_layout.addWidget(audio_key_entry)
        self._audio_api_key_entry = audio_key_entry

        audio_endpoint_entry = self.ui_tools.create_text_entry(
            SettingsNames.AUDIO_ENDPOINT_SETTING_NAME,
            "Custom speech endpoint (optional)"
        )
        right_layout.addWidget(audio_endpoint_entry)
        self._audio_endpoint_entry = audio_endpoint_entry

        audio_model_entry = self.ui_tools.create_text_entry(
            SettingsNames.AUDIO_MODEL_SETTING_NAME,
            "Speech model name (optional)"
        )
        right_layout.addWidget(audio_model_entry)
        self._audio_model_entry = audio_model_entry

        audio_voice_entry = self.ui_tools.create_text_entry(
            SettingsNames.AUDIO_VOICE_SETTING_NAME,
            "Preferred voice or speaker id"
        )
        right_layout.addWidget(audio_voice_entry)
        self._audio_voice_entry = audio_voice_entry

        audio_format_entry = self.ui_tools.create_text_entry(
            SettingsNames.AUDIO_FORMAT_SETTING_NAME,
            "Audio format (wav or pcm)"
        )
        if not audio_format_entry.text().strip():
            audio_format_entry.setText("wav")
        right_layout.addWidget(audio_format_entry)
        self._audio_format_entry = audio_format_entry

        # Misc
        right_layout.addWidget(
            self.ui_tools.create_label(
                f"{len(self.selected_notes)} cards selected. Modify cards?"
            )
        )

        main_layout.addWidget(left_container)
        main_layout.addWidget(right_container)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container_widget)

        final_layout = QVBoxLayout(self)
        final_layout.addWidget(scroll_area)
        self.setLayout(final_layout)
        return self

    @property
    @abstractmethod
    def service_name(self):
        """User friendly name of the service, e.g. 'OpenAI'"""

    @property
    @abstractmethod
    def models(self) -> list[str]:
        """Array of the names of the available models"""

    @property
    @abstractmethod
    def system_prompt_description(self):
        """User friendly description for the system prompt"""

    @property
    @abstractmethod
    def system_prompt_placeholder(self):
        """Optional placeholder text for the system prompt"""

    @property
    @abstractmethod
    def user_prompt_description(self):
        """User friendly description for the user prompt"""

    @property
    @abstractmethod
    def user_prompt_placeholder(self):
        """Optional placeholder text for the user prompt"""

    @property
    def mapping_instruction_text(self):
        """User friendly description for the JSON key to Note field mapping instructions"""
        return """
        For each piece of information you told the AI to give you in the System Prompt, enter it here, and select the Field on your Card where you want to save it.<br><br>
        <b>Example:</b> If you asked the AI for a German sentence and its translation, and your Anki Fields are <code>de_sentence</code> and <code>en_sentence</code>, enter:
        <pre>exampleSentence de_sentence<br>translation en_sentence</pre>
        """

    def add_models_dropdown(self, layout):
        layout.addWidget(self.ui_tools.create_label("Model Name:"))
        layout.addWidget(
            self.ui_tools.create_dropdown(SettingsNames.MODEL_SETTING_NAME, self.models)
        )

    def add_api_key(self, layout):
        layout.addWidget(self.ui_tools.create_label(f"{self.service_name} API Key:"))
        layout.addWidget(
            self.ui_tools.create_text_entry(SettingsNames.API_KEY_SETTING_NAME)
        )

    def add_system_prompt(
        self, layout, system_prompt_description, system_prompt_placeholder
    ):
        layout.addWidget(self.ui_tools.create_label("System Prompt:"))
        layout.addWidget(
            self.ui_tools.create_descriptive_text(system_prompt_description)
        )
        layout.addWidget(
            self.ui_tools.create_text_edit(
                SettingsNames.SYSTEM_PROMPT_SETTING_NAME,
                system_prompt_placeholder,
                max_height=350,
            )
        )

    def add_user_prompt(self, layout, user_prompt_description, user_prompt_placeholder):
        layout.addWidget(self.ui_tools.create_label("User Prompt:"))
        layout.addWidget(self.ui_tools.create_descriptive_text(user_prompt_description))
        layout.addWidget(
            self.ui_tools.create_text_edit(
                SettingsNames.USER_PROMPT_SETTING_NAME,
                user_prompt_placeholder,
                max_height=200,
            )
        )

    def accept(self) -> bool:
        """
        Saves settings when user accepts. Returns False if invalid.
        """
        if not self.are_settings_valid():
            return False
        self.ui_tools.save_settings()
        keys, fields = self.two_col_form.get_inputs()
        self.app_settings.setValue(SettingsNames.RESPONSE_KEYS_SETTING_NAME, keys)
        self.app_settings.setValue(
            SettingsNames.DESTINATION_FIELD_SETTING_NAME,
            fields,
        )
        image_mapping_strings: list[str] = []
        if self.image_mapping_form is not None:
            image_pairs = self.image_mapping_form.get_pairs()
            image_mapping_strings = [
                f"{prompt}{IMAGE_MAPPING_SEPARATOR}{image}" for prompt, image in image_pairs
            ]
        self.app_settings.setValue(
            SettingsNames.IMAGE_MAPPING_SETTING_NAME, image_mapping_strings
        )

        audio_mapping_strings: list[str] = []
        if self.audio_mapping_form is not None:
            audio_pairs = self.audio_mapping_form.get_pairs()
            audio_mapping_strings = [
                f"{prompt}{IMAGE_MAPPING_SEPARATOR}{audio}" for prompt, audio in audio_pairs
            ]
        self.app_settings.setValue(
            SettingsNames.AUDIO_MAPPING_SETTING_NAME, audio_mapping_strings
        )
        return True

    def are_settings_valid(self) -> bool:
        """
        Returns True if all required settings are present, False otherwise.
        Displays an error dialog if some are missing.
        """
        settings = self.ui_tools.get_settings()
        if (
            SettingsNames.API_KEY_SETTING_NAME not in settings
            or not settings[SettingsNames.API_KEY_SETTING_NAME]
        ):
            show_error_message("Please enter an API key.")
            return False
        if (
            SettingsNames.USER_PROMPT_SETTING_NAME not in settings
            or not settings[SettingsNames.USER_PROMPT_SETTING_NAME]
        ):
            show_error_message("Please enter a prompt.")
            return False

        keys, fields = self.two_col_form.get_inputs()
        if len(keys) == 0 or len(fields) == 0:
            show_error_message("You must save at least one AI Output to one Field.")
            return False

        has_image_mapping = bool(
            self.image_mapping_form and self.image_mapping_form.get_pairs()
        )
        if has_image_mapping:
            api_key = ""
            if self._image_api_key_entry is not None:
                api_key = self._image_api_key_entry.text().strip()
            if not api_key:
                show_error_message(
                    "Enter the image generation API key before running the plugin."
                )
                return False

        has_audio_mapping = bool(
            self.audio_mapping_form and self.audio_mapping_form.get_pairs()
        )
        if has_audio_mapping:
            audio_key = ""
            if self._audio_api_key_entry is not None:
                audio_key = self._audio_api_key_entry.text().strip()
            if not audio_key:
                show_error_message(
                    "Enter the speech generation API key before running the plugin."
                )
                return False

        return True


def show_error_message(message: str):
    """Displays a popup with the message"""
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Critical)
    msg_box.setWindowTitle("Error")
    msg_box.setText(message)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()  # Display the message box
