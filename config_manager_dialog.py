from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLabel,
    QLineEdit,
    QFormLayout,
    QCheckBox,
)

from .config_store import ConfigStore, LLMConfig
from .gemini_client import GeminiClient
from .user_base_dialog import IMAGE_MAPPING_SEPARATOR


class ConfigManagerDialog(QDialog):
    """Dialog allowing users to maintain multiple LLM configurations."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Manage LLM Configurations")
        self.resize(800, 500)
        self.store = ConfigStore()
        self._current_name: Optional[str] = None

        self._build_ui()
        self._load_configs()
        self.prompt_save_if_example(self.store, self)

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # Left: list of configs + buttons
        list_container = QVBoxLayout()
        self.config_list = QListWidget()
        self.config_list.currentItemChanged.connect(self._on_selection_changed)
        list_container.addWidget(self.config_list)

        button_row = QHBoxLayout()
        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(self._on_new)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._on_delete)
        button_row.addWidget(self.new_button)
        button_row.addWidget(self.delete_button)
        button_row.addStretch()
        list_container.addLayout(button_row)

        # Right: config detail form
        form_container = QVBoxLayout()
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)

        self.name_input = QLineEdit()
        form_layout.addRow(QLabel("Configuration Name:"), self.name_input)

        self.endpoint_input = QLineEdit()
        self.endpoint_input.setPlaceholderText("https://api.example.com/v1/chat/completions")
        form_layout.addRow(QLabel("Endpoint URL:"), self.endpoint_input)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-...")
        form_layout.addRow(QLabel("API Key:"), self.api_key_input)

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("model-name")
        form_layout.addRow(QLabel("Model Name:"), self.model_input)

        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setPlaceholderText("Optional system prompt")
        form_layout.addRow(QLabel("System Prompt:"), self.system_prompt_input)

        self.user_prompt_input = QTextEdit()
        self.user_prompt_input.setPlaceholderText("Prompt template supporting {field} substitutions")
        form_layout.addRow(QLabel("User Prompt:"), self.user_prompt_input)

        self.response_keys_input = QLineEdit()
        self.response_keys_input.setPlaceholderText("Comma separated, e.g. exampleSentence, translation")
        form_layout.addRow(QLabel("Response Keys:"), self.response_keys_input)

        self.destination_fields_input = QLineEdit()
        self.destination_fields_input.setPlaceholderText("Comma separated Anki fields")
        form_layout.addRow(QLabel("Destination Fields:"), self.destination_fields_input)

        self.text_generation_checkbox = QCheckBox("Enable text generation")
        self.text_generation_checkbox.setChecked(True)
        form_layout.addRow(QLabel("Text Generation:"), self.text_generation_checkbox)

        self.image_mapping_input = QTextEdit()
        self.image_mapping_input.setPlaceholderText(
            "prompt_field -> image_field (one per line)"
        )
        form_layout.addRow(QLabel("Image Prompt Mappings:"), self.image_mapping_input)

        self.image_generation_checkbox = QCheckBox("Enable image generation")
        self.image_generation_checkbox.setChecked(True)
        form_layout.addRow(QLabel("Image Generation:"), self.image_generation_checkbox)

        self.image_api_key_input = QLineEdit()
        self.image_api_key_input.setPlaceholderText("Override image API key")
        form_layout.addRow(QLabel("Image API Key:"), self.image_api_key_input)

        default_endpoint = "https://generativelanguage.googleapis.com/v1beta/models"
        self.image_endpoint_input = QLineEdit()
        self.image_endpoint_input.setPlaceholderText(
            f"Custom image endpoint (default {default_endpoint})"
        )
        form_layout.addRow(QLabel("Image Endpoint:"), self.image_endpoint_input)

        self.image_model_input = QLineEdit()
        self.image_model_input.setPlaceholderText(
            f"Image model name (default {GeminiClient.IMAGE_MODEL})"
        )
        form_layout.addRow(QLabel("Image Model:"), self.image_model_input)

        self.audio_mapping_input = QTextEdit()
        self.audio_mapping_input.setPlaceholderText(
            "text_field -> audio_field (one per line; stores [sound:...] in the second field)"
        )
        self.audio_mapping_input.setToolTip(
            "Each mapping takes the text from the first field, runs TTS, and writes the resulting [sound:...] tag into the second field."
        )
        form_layout.addRow(QLabel("Speech Field Mappings:"), self.audio_mapping_input)

        self.audio_generation_checkbox = QCheckBox("Enable speech generation")
        self.audio_generation_checkbox.setChecked(True)
        form_layout.addRow(QLabel("Speech Generation:"), self.audio_generation_checkbox)

        self.audio_api_key_input = QLineEdit()
        self.audio_api_key_input.setPlaceholderText("Speech API key (required for audio generation)")
        form_layout.addRow(QLabel("Speech API Key:"), self.audio_api_key_input)

        self.audio_endpoint_input = QLineEdit()
        self.audio_endpoint_input.setPlaceholderText("Custom speech endpoint (optional)")
        form_layout.addRow(QLabel("Speech Endpoint:"), self.audio_endpoint_input)

        self.audio_model_input = QLineEdit()
        self.audio_model_input.setPlaceholderText("Speech model name (e.g. gpt-4o-mini-tts)")
        form_layout.addRow(QLabel("Speech Model:"), self.audio_model_input)

        self.audio_voice_input = QLineEdit()
        self.audio_voice_input.setPlaceholderText("Preferred voice (e.g. alloy)")
        form_layout.addRow(QLabel("Speech Voice:"), self.audio_voice_input)

        self.audio_format_input = QLineEdit()
        self.audio_format_input.setPlaceholderText("Audio format (wav or pcm)")
        self.audio_format_input.setText("wav")
        form_layout.addRow(QLabel("Speech Format:"), self.audio_format_input)

        form_container.addWidget(form_widget)
        form_container.addStretch()

        save_button_row = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._on_save)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        save_button_row.addWidget(self.save_button)
        save_button_row.addStretch()
        save_button_row.addWidget(self.close_button)
        form_container.addLayout(save_button_row)

        main_layout.addLayout(list_container, 1)
        main_layout.addLayout(form_container, 2)

    # Data helpers -----------------------------------------------------

    def _load_configs(self) -> None:
        self.config_list.clear()
        for config in self.store.list_configs():
            item = QListWidgetItem(config.name)
            item.setData(Qt.ItemDataRole.UserRole, config)
            self.config_list.addItem(item)
        if self.config_list.count() > 0:
            self.config_list.setCurrentRow(0)

    def _current_config(self) -> Optional[LLMConfig]:
        item = self.config_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_selection_changed(self, current: Optional[QListWidgetItem], previous):
        if current is None:
            self._clear_form()
            self._current_name = None
            return
        config: LLMConfig = current.data(Qt.ItemDataRole.UserRole)
        self._populate_form(config)
        self._current_name = config.name

    def _populate_form(self, config: LLMConfig) -> None:
        self.name_input.setText(config.name)
        self.endpoint_input.setText(config.endpoint)
        self.api_key_input.setText(config.api_key)
        self.model_input.setText(config.model)
        self.system_prompt_input.setPlainText(config.system_prompt)
        self.user_prompt_input.setPlainText(config.user_prompt)
        self.response_keys_input.setText(
            ", ".join(config.response_keys)
        )
        self.destination_fields_input.setText(
            ", ".join(config.destination_fields)
        )
        if hasattr(self, "text_generation_checkbox"):
            self.text_generation_checkbox.setChecked(config.enable_text_generation)
        if hasattr(self, "image_mapping_input"):
            self.image_mapping_input.setPlainText("\n".join(config.image_prompt_mappings))
        if hasattr(self, "image_api_key_input"):
            self.image_api_key_input.setText(config.image_api_key)
        if hasattr(self, "image_endpoint_input"):
            self.image_endpoint_input.setText(config.image_endpoint)
        if hasattr(self, "image_model_input"):
            self.image_model_input.setText(config.image_model)
        if hasattr(self, "image_generation_checkbox"):
            self.image_generation_checkbox.setChecked(config.enable_image_generation)
        if hasattr(self, "audio_mapping_input"):
            self.audio_mapping_input.setPlainText("\n".join(config.audio_prompt_mappings))
        if hasattr(self, "audio_api_key_input"):
            self.audio_api_key_input.setText(config.audio_api_key)
        if hasattr(self, "audio_endpoint_input"):
            self.audio_endpoint_input.setText(config.audio_endpoint)
        if hasattr(self, "audio_model_input"):
            self.audio_model_input.setText(config.audio_model)
        if hasattr(self, "audio_voice_input"):
            self.audio_voice_input.setText(config.audio_voice)
        if hasattr(self, "audio_format_input"):
            value = config.audio_format or "wav"
            self.audio_format_input.setText(value)
        if hasattr(self, "audio_generation_checkbox"):
            self.audio_generation_checkbox.setChecked(config.enable_audio_generation)

    def _clear_form(self) -> None:
        self.name_input.clear()
        self.endpoint_input.clear()
        self.api_key_input.clear()
        self.model_input.clear()
        self.system_prompt_input.clear()
        self.user_prompt_input.clear()
        self.response_keys_input.clear()
        self.destination_fields_input.clear()
        if hasattr(self, "image_mapping_input"):
            self.image_mapping_input.clear()
        if hasattr(self, "image_api_key_input"):
            self.image_api_key_input.clear()
        if hasattr(self, "image_endpoint_input"):
            self.image_endpoint_input.clear()
        if hasattr(self, "image_model_input"):
            self.image_model_input.clear()
        if hasattr(self, "audio_mapping_input"):
            self.audio_mapping_input.clear()
        if hasattr(self, "audio_api_key_input"):
            self.audio_api_key_input.clear()
        if hasattr(self, "audio_endpoint_input"):
            self.audio_endpoint_input.clear()
        if hasattr(self, "audio_model_input"):
            self.audio_model_input.clear()
        if hasattr(self, "audio_voice_input"):
            self.audio_voice_input.clear()
        if hasattr(self, "audio_format_input"):
            self.audio_format_input.setText("wav")
        if hasattr(self, "text_generation_checkbox"):
            self.text_generation_checkbox.setChecked(True)
        if hasattr(self, "image_generation_checkbox"):
            self.image_generation_checkbox.setChecked(True)
        if hasattr(self, "audio_generation_checkbox"):
            self.audio_generation_checkbox.setChecked(True)

    # Button handlers --------------------------------------------------

    def _on_new(self) -> None:
        name = self.store.ensure_unique_name()
        config = LLMConfig(name=name)
        self.store.upsert(config)
        self._load_configs()
        self._select_by_name(name)

    def _on_delete(self) -> None:
        config = self._current_config()
        if config is None:
            return
        if len(self.store.list_configs()) == 1:
            QMessageBox.warning(
                self,
                "Delete Configuration",
                "At least one configuration must exist.",
            )
            return
        confirm = QMessageBox.question(
            self,
            "Delete Configuration",
            f"Delete configuration '{config.name}'?",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.store.delete(config.name)
            self._load_configs()

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Configuration", "Name is required.")
            return
        endpoint = self.endpoint_input.text().strip()
        api_key = self.api_key_input.text().strip()
        model = self.model_input.text().strip()
        system_prompt = self.system_prompt_input.toPlainText()
        user_prompt = self.user_prompt_input.toPlainText()
        response_keys = self._parse_comma_list(self.response_keys_input.text())
        destination_fields = self._parse_comma_list(
            self.destination_fields_input.text()
        )
        image_mappings = []
        if hasattr(self, "image_mapping_input"):
            image_mappings = [
                line.strip()
                for line in self.image_mapping_input.toPlainText().splitlines()
                if IMAGE_MAPPING_SEPARATOR in line.strip()
            ]
        audio_mappings = []
        if hasattr(self, "audio_mapping_input"):
            audio_mappings = [
                line.strip()
                for line in self.audio_mapping_input.toPlainText().splitlines()
                if IMAGE_MAPPING_SEPARATOR in line.strip()
            ]
        config = LLMConfig(
            name=name,
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_keys=response_keys,
            destination_fields=destination_fields,
            image_prompt_mappings=image_mappings,
            image_api_key=(self.image_api_key_input.text().strip() if hasattr(self, "image_api_key_input") else ""),
            image_endpoint=(self.image_endpoint_input.text().strip() if hasattr(self, "image_endpoint_input") else ""),
            image_model=(self.image_model_input.text().strip() if hasattr(self, "image_model_input") else ""),
            audio_prompt_mappings=audio_mappings,
            audio_api_key=(self.audio_api_key_input.text().strip() if hasattr(self, "audio_api_key_input") else ""),
            audio_endpoint=(self.audio_endpoint_input.text().strip() if hasattr(self, "audio_endpoint_input") else ""),
            audio_model=(self.audio_model_input.text().strip() if hasattr(self, "audio_model_input") else ""),
            audio_voice=(self.audio_voice_input.text().strip() if hasattr(self, "audio_voice_input") else ""),
            audio_format=(
                (self.audio_format_input.text().strip() or "wav")
                if hasattr(self, "audio_format_input")
                else "wav"
            ),
            text_mapping_entries=[
                {
                    "key": key,
                    "field": field,
                    "enabled": True,
                }
                for key, field in zip(response_keys, destination_fields)
            ],
            enable_text_generation=(
                self.text_generation_checkbox.isChecked()
                if hasattr(self, "text_generation_checkbox")
                else True
            ),
            enable_image_generation=(
                self.image_generation_checkbox.isChecked()
                if hasattr(self, "image_generation_checkbox")
                else True
            ),
            enable_audio_generation=(
                self.audio_generation_checkbox.isChecked()
                if hasattr(self, "audio_generation_checkbox")
                else True
            ),
        )
        if self._current_name and self._current_name != name:
            self.store.delete(self._current_name)
        self.store.upsert(config)
        self._load_configs()
        self._select_by_name(name)

    def _select_by_name(self, name: str) -> None:
        for row in range(self.config_list.count()):
            item = self.config_list.item(row)
            if item.text() == name:
                self.config_list.setCurrentRow(row)
                break

    @staticmethod
    def _parse_comma_list(raw_value: str) -> list[str]:
        return [value.strip() for value in raw_value.split(",") if value.strip()]

    @staticmethod
    def prompt_save_if_example(
        store: ConfigStore, parent: Optional[QWidget] = None
    ) -> None:
        if not store.using_example:
            return
        message = (
            "The add-on is currently using the sample configuration file "
            "(config.example.json).\n\n"
            "Do you want to save a copy as config.json so your changes persist?"
        )
        response = QMessageBox.question(
            parent,
            "Create config.json?",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        try:
            store.save_as(store.default_config_path)
        except OSError as exc:
            QMessageBox.warning(
                parent,
                "Unable to Save",
                f"Could not write config.json:\n{exc}",
            )
