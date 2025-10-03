import json
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
    QCheckBox,
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
        self._text_generation_checkbox: QCheckBox | None = None
        self._image_generation_checkbox: QCheckBox | None = None
        self._audio_generation_checkbox: QCheckBox | None = None

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
        text_rows = self._load_text_rows(card_fields)
        self._text_generation_checkbox = QCheckBox("Generate text fields")
        self._text_generation_checkbox.setChecked(
            self._get_bool_setting(
                SettingsNames.ENABLE_TEXT_GENERATION_SETTING_NAME, default=True
            )
        )
        right_layout.addWidget(self._text_generation_checkbox)

        self.two_col_form = DynamicForm(text_rows, card_fields)
        self._text_generation_checkbox.stateChanged.connect(
            self._on_text_generation_toggled
        )
        self.two_col_form.set_master_override(
            self._text_generation_checkbox.isChecked()
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
        self._image_generation_checkbox = QCheckBox("Generate images")
        self._image_generation_checkbox.setChecked(
            self._get_bool_setting(
                SettingsNames.ENABLE_IMAGE_GENERATION_SETTING_NAME, default=True
            )
        )
        image_mapping_strings = self.app_settings.value(
            SettingsNames.IMAGE_MAPPING_SETTING_NAME,
            type="QStringList",
        ) or []
        image_rows = self._decode_mapping_rows(image_mapping_strings)
        self.image_mapping_form = ImageMappingForm(image_rows, card_fields)
        self._image_generation_checkbox.stateChanged.connect(
            self._on_image_generation_toggled
        )
        self.image_mapping_form.set_master_override(
            self._image_generation_checkbox.isChecked()
        )
        right_layout.addWidget(self._image_generation_checkbox)
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
        self._audio_generation_checkbox = QCheckBox("Generate speech")
        self._audio_generation_checkbox.setChecked(
            self._get_bool_setting(
                SettingsNames.ENABLE_AUDIO_GENERATION_SETTING_NAME, default=True
            )
        )
        audio_mapping_strings = self.app_settings.value(
            SettingsNames.AUDIO_MAPPING_SETTING_NAME,
            type="QStringList",
        ) or []
        audio_rows = self._decode_mapping_rows(audio_mapping_strings)
        self.audio_mapping_form = AudioMappingForm(audio_rows, card_fields)
        self._audio_generation_checkbox.stateChanged.connect(
            self._on_audio_generation_toggled
        )
        self.audio_mapping_form.set_master_override(
            self._audio_generation_checkbox.isChecked()
        )
        right_layout.addWidget(self._audio_generation_checkbox)
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
        all_text_rows = self.two_col_form.get_all_rows()
        filtered_text_entries = [
            row
            for row in all_text_rows
            if row.get("key") or row.get("field")
        ]
        self.app_settings.setValue(
            SettingsNames.TEXT_MAPPING_ENTRIES_SETTING_NAME,
            json.dumps(filtered_text_entries, ensure_ascii=False),
        )
        if self._text_generation_checkbox is not None:
            self.app_settings.setValue(
                SettingsNames.ENABLE_TEXT_GENERATION_SETTING_NAME,
                self._text_generation_checkbox.isChecked(),
            )

        image_mapping_strings: list[str] = []
        if self.image_mapping_form is not None:
            all_image_rows = self.image_mapping_form.get_all_rows()
            image_mapping_strings = [
                self._encode_mapping_entry(prompt, target, enabled)
                for prompt, target, enabled in all_image_rows
                if prompt and target
            ]
        self.app_settings.setValue(
            SettingsNames.IMAGE_MAPPING_SETTING_NAME,
            image_mapping_strings,
        )
        if self._image_generation_checkbox is not None:
            self.app_settings.setValue(
                SettingsNames.ENABLE_IMAGE_GENERATION_SETTING_NAME,
                self._image_generation_checkbox.isChecked(),
            )

        audio_mapping_strings: list[str] = []
        if self.audio_mapping_form is not None:
            all_audio_rows = self.audio_mapping_form.get_all_rows()
            audio_mapping_strings = [
                self._encode_mapping_entry(prompt, target, enabled)
                for prompt, target, enabled in all_audio_rows
                if prompt and target
            ]
        self.app_settings.setValue(
            SettingsNames.AUDIO_MAPPING_SETTING_NAME,
            audio_mapping_strings,
        )
        if self._audio_generation_checkbox is not None:
            self.app_settings.setValue(
                SettingsNames.ENABLE_AUDIO_GENERATION_SETTING_NAME,
                self._audio_generation_checkbox.isChecked(),
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
        text_enabled = (
            self._text_generation_checkbox.isChecked()
            if self._text_generation_checkbox is not None
            else True
        )
        if text_enabled and (
            SettingsNames.USER_PROMPT_SETTING_NAME not in settings
            or not settings[SettingsNames.USER_PROMPT_SETTING_NAME]
        ):
            show_error_message("Please enter a prompt.")
            return False

        keys, fields = self.two_col_form.get_inputs()
        if text_enabled and (len(keys) == 0 or len(fields) == 0):
            show_error_message("You must save at least one AI Output to one Field.")
            return False

        image_enabled = (
            self._image_generation_checkbox.isChecked()
            if self._image_generation_checkbox is not None
            else True
        )
        has_image_mapping = bool(
            image_enabled
            and self.image_mapping_form
            and self.image_mapping_form.get_pairs()
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

        audio_enabled = (
            self._audio_generation_checkbox.isChecked()
            if self._audio_generation_checkbox is not None
            else True
        )
        has_audio_mapping = bool(
            audio_enabled
            and self.audio_mapping_form
            and self.audio_mapping_form.get_pairs()
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

    def _on_text_generation_toggled(self, state: int) -> None:
        if self.two_col_form is not None:
            checked = Qt.CheckState(state) == Qt.CheckState.Checked
            self.two_col_form.set_master_override(checked)

    def _on_image_generation_toggled(self, state: int) -> None:
        if self.image_mapping_form is not None:
            checked = Qt.CheckState(state) == Qt.CheckState.Checked
            self.image_mapping_form.set_master_override(checked)

    def _on_audio_generation_toggled(self, state: int) -> None:
        if self.audio_mapping_form is not None:
            checked = Qt.CheckState(state) == Qt.CheckState.Checked
            self.audio_mapping_form.set_master_override(checked)

    def _get_bool_setting(self, name: str, default: bool = True) -> bool:
        value = self.app_settings.value(name, defaultValue=default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes"}
        return bool(value)

    def _load_text_rows(self, card_fields: list[str]) -> list[tuple[str, str, bool]]:
        raw_entries = self.app_settings.value(
            SettingsNames.TEXT_MAPPING_ENTRIES_SETTING_NAME,
            type=str,
        )
        rows: list[tuple[str, str, bool]] = []
        if raw_entries:
            try:
                data = json.loads(raw_entries)
                for entry in data:
                    if not isinstance(entry, dict):
                        continue
                    key = str(entry.get("key", "")).strip()
                    field = str(entry.get("field", "")).strip()
                    enabled = bool(entry.get("enabled", True))
                    rows.append((key, field, enabled))
            except (json.JSONDecodeError, TypeError):
                rows = []
        if not rows:
            keys = self.app_settings.value(
                SettingsNames.RESPONSE_KEYS_SETTING_NAME, type="QStringList"
            ) or []
            fields = self.app_settings.value(
                SettingsNames.DESTINATION_FIELD_SETTING_NAME, type="QStringList"
            ) or []
            if keys and fields and len(keys) == len(fields):
                rows = [(key, field, True) for key, field in zip(keys, fields)]
        return rows

    def _decode_mapping_rows(
        self, entries: list[str]
    ) -> list[tuple[str, str, bool]]:
        rows: list[tuple[str, str, bool]] = []
        for mapping in entries:
            if not isinstance(mapping, str) or IMAGE_MAPPING_SEPARATOR not in mapping:
                continue
            enabled = True
            base = mapping
            if "::" in mapping:
                base, flag = mapping.rsplit("::", 1)
                enabled = flag.strip() not in {"0", "false", "False"}
            if IMAGE_MAPPING_SEPARATOR not in base:
                continue
            prompt, target = [
                part.strip() for part in base.split(IMAGE_MAPPING_SEPARATOR, 1)
            ]
            if prompt or target:
                rows.append((prompt, target, enabled))
        return rows

    @staticmethod
    def _encode_mapping_entry(prompt: str, target: str, enabled: bool) -> str:
        return (
            f"{prompt}{IMAGE_MAPPING_SEPARATOR}{target}::"
            f"{'1' if enabled else '0'}"
        )


def show_error_message(message: str):
    """Displays a popup with the message"""
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Critical)
    msg_box.setWindowTitle("Error")
    msg_box.setText(message)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()  # Display the message box
