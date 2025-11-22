"""Unified runtime configuration panel matching the config manager layout."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Sequence, Tuple

from anki.notes import Note as AnkiNote
from aqt.qt import QSettings
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .mapping_sections import GenerationSection, RetrySection, ToggleMappingEditor
from .provider_options import (
    AUDIO_PROVIDERS,
    AUDIO_PROVIDER_DEFAULTS,
    IMAGE_PROVIDERS,
    IMAGE_PROVIDER_DEFAULTS,
    TEXT_PROVIDERS,
    TEXT_PROVIDER_DEFAULTS,
)
from .settings import SettingsNames

IMAGE_MAPPING_SEPARATOR = "->"


class UserBaseDialog(QWidget):
    """Runtime editor that mirrors the configuration manager sections."""

    def __init__(self, app_settings: QSettings, selected_notes: list[AnkiNote]):
        super().__init__()
        self.app_settings = app_settings
        self.selected_notes = selected_notes
        self.card_fields = sorted(
            {field for note in selected_notes for field in note.keys()}
        )
        self._loading = True
        self._dirty = False
        self._initial_state: Dict[str, Any] = {}
        self._provider_indices: Dict[str, int] = {
            "text": -1,
            "image": -1,
            "audio": -1,
        }
        self._build_ui()
        self._install_dirty_watchers()
        self._load_from_settings()
        self._loading = False
        self._reset_dirty_state()

    # UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        self.resize(900, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(16, 12, 16, 12)
        container_layout.setSpacing(12)

        self.selection_label = QLabel(
            f"{len(self.selected_notes)} notes selected." if self.selected_notes else "No notes selected"
        )
        container_layout.addWidget(self.selection_label)

        self.note_type_status = QLabel()
        self.note_type_status.setWordWrap(True)
        self.note_type_status.setStyleSheet("color: #c0392b;")
        self.note_type_status.hide()
        container_layout.addWidget(self.note_type_status)

        self.retry_section = RetrySection()
        container_layout.addWidget(self.retry_section)

        # Text generation section -------------------------------------
        self.text_mapping_editor = ToggleMappingEditor(
            [],
            left_placeholder="response key",
            right_placeholder="destination field",
        )
        self.text_section = GenerationSection(
            "Text generation",
            "Enable text generation",
            self.text_mapping_editor,
            description="Map model response keys to the Anki fields to update.",
        )
        self.text_section.add_provider_selector(TEXT_PROVIDERS)
        if self.text_section.provider_combo:
            self.text_section.provider_combo.setEnabled(False)
        if self.text_section.custom_model_input:
            self.text_section.custom_model_input.setEnabled(False)
        self.text_defaults_button = QPushButton("Restore defaults")
        self.text_defaults_button.clicked.connect(
            lambda: self._apply_text_provider_defaults(force=True)
        )
        self.text_section.add_provider_reset_button(self.text_defaults_button)
        if self.text_section.provider_combo is not None:
            self.text_section.provider_combo.currentIndexChanged.connect(
                lambda index: self._on_provider_combo_changed("text", index)
            )
        self._update_text_reset_button()

        text_creds_form = QFormLayout()
        text_creds_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("API key")
        text_creds_form.addRow(QLabel("API Key:"), self.api_key_input)
        self.endpoint_input = QLineEdit()
        self.endpoint_input.setPlaceholderText("Endpoint (optional)")
        text_creds_form.addRow(QLabel("Endpoint:"), self.endpoint_input)
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("Model name")
        text_creds_form.addRow(QLabel("Model:"), self.model_input)
        self.text_section.add_form_layout(text_creds_form)

        text_prompt_form = QFormLayout()
        text_prompt_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setAcceptRichText(False)
        self.system_prompt_input.setMinimumHeight(80)
        text_prompt_form.addRow(QLabel("System Prompt:"), self.system_prompt_input)
        self.user_prompt_input = QTextEdit()
        self.user_prompt_input.setAcceptRichText(False)
        self.user_prompt_input.setMinimumHeight(120)
        text_prompt_form.addRow(QLabel("User Prompt:"), self.user_prompt_input)
        self.text_section.add_form_layout(text_prompt_form)
        container_layout.addWidget(self.text_section)

        # Image generation section ------------------------------------
        self.image_mapping_editor = ToggleMappingEditor(
            [],
            left_placeholder="prompt field",
            right_placeholder="image field",
        )
        self.image_section = GenerationSection(
            "Image generation",
            "Enable image generation",
            self.image_mapping_editor,
            description="Map prompt fields to the target fields that should receive images.",
        )
        self.image_section.add_provider_selector(IMAGE_PROVIDERS)
        if self.image_section.provider_combo:
            self.image_section.provider_combo.setEnabled(False)
        if self.image_section.custom_model_input:
            self.image_section.custom_model_input.setEnabled(False)
        self.image_defaults_button = QPushButton("Restore defaults")
        self.image_defaults_button.clicked.connect(
            lambda: self._apply_image_provider_defaults(force=True)
        )
        self.image_section.add_provider_reset_button(self.image_defaults_button)
        if self.image_section.provider_combo is not None:
            self.image_section.provider_combo.currentIndexChanged.connect(
                lambda index: self._on_provider_combo_changed("image", index)
            )
        self._update_image_reset_button()

        image_form = QFormLayout()
        image_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.image_api_key_input = QLineEdit()
        self.image_api_key_input.setPlaceholderText("Image API key")
        image_form.addRow(QLabel("Image API Key:"), self.image_api_key_input)
        self.image_endpoint_input = QLineEdit()
        self.image_endpoint_input.setPlaceholderText("Image endpoint")
        image_form.addRow(QLabel("Image Endpoint:"), self.image_endpoint_input)
        self.image_model_input = QLineEdit()
        self.image_model_input.setPlaceholderText("Image model")
        image_form.addRow(QLabel("Image Model:"), self.image_model_input)
        self.image_section.add_form_layout(image_form)
        container_layout.addWidget(self.image_section)

        # Speech generation section -----------------------------------
        self.audio_mapping_editor = ToggleMappingEditor(
            [],
            left_placeholder="text field",
            right_placeholder="audio field",
        )
        self.audio_section = GenerationSection(
            "Speech generation",
            "Enable speech generation",
            self.audio_mapping_editor,
            description="Map text fields to the fields that should receive [sound:] tags.",
        )
        self.audio_section.add_provider_selector(AUDIO_PROVIDERS)
        if self.audio_section.provider_combo:
            self.audio_section.provider_combo.setEnabled(False)
        if self.audio_section.custom_model_input:
            self.audio_section.custom_model_input.setEnabled(False)
        self.audio_defaults_button = QPushButton("Restore defaults")
        self.audio_defaults_button.clicked.connect(
            lambda: self._apply_audio_provider_defaults(force=True)
        )
        self.audio_section.add_provider_reset_button(self.audio_defaults_button)
        if self.audio_section.provider_combo is not None:
            self.audio_section.provider_combo.currentIndexChanged.connect(
                lambda index: self._on_provider_combo_changed("audio", index)
            )
        self._update_audio_reset_button()

        audio_form = QFormLayout()
        audio_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.audio_api_key_input = QLineEdit()
        self.audio_api_key_input.setPlaceholderText("Speech API key")
        audio_form.addRow(QLabel("Speech API Key:"), self.audio_api_key_input)
        self.audio_endpoint_input = QLineEdit()
        self.audio_endpoint_input.setPlaceholderText("Speech endpoint")
        audio_form.addRow(QLabel("Speech Endpoint:"), self.audio_endpoint_input)
        self.audio_model_input = QLineEdit()
        self.audio_model_input.setPlaceholderText("Speech model")
        audio_form.addRow(QLabel("Speech Model:"), self.audio_model_input)
        self.audio_voice_input = QLineEdit()
        self.audio_voice_input.setPlaceholderText("Voice preference")
        audio_form.addRow(QLabel("Speech Voice:"), self.audio_voice_input)
        self.audio_format_input = QLineEdit()
        self.audio_format_input.setPlaceholderText("wav")
        audio_form.addRow(QLabel("Speech Format:"), self.audio_format_input)
        self.audio_section.add_form_layout(audio_form)
        container_layout.addWidget(self.audio_section)

        # YouGlish links -------------------------------------------------
        self.youglish_group = QGroupBox("YouGlish links")
        youglish_form = QFormLayout(self.youglish_group)
        youglish_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.youglish_enable_checkbox = QCheckBox("Enable YouGlish link generation")
        self.youglish_enable_checkbox.stateChanged.connect(
            lambda _: self._update_youglish_enabled_state()
        )
        youglish_form.addRow(self.youglish_enable_checkbox)
        self.youglish_source_input = QLineEdit()
        self.youglish_source_input.setPlaceholderText("_word")
        youglish_form.addRow(QLabel("Source field:"), self.youglish_source_input)
        self.youglish_target_input = QLineEdit()
        self.youglish_target_input.setPlaceholderText("_youglish")
        youglish_form.addRow(QLabel("Target field:"), self.youglish_target_input)
        self.youglish_accent_combo = QComboBox()
        self.youglish_accent_combo.addItem("US", "us")
        self.youglish_accent_combo.addItem("UK", "uk")
        self.youglish_accent_combo.addItem("Australia", "aus")
        youglish_form.addRow(QLabel("Accent:"), self.youglish_accent_combo)
        self.youglish_overwrite_checkbox = QCheckBox("Always overwrite existing value")
        youglish_form.addRow(self.youglish_overwrite_checkbox)
        container_layout.addWidget(self.youglish_group)

        # Ensure mapping editors respond to enable toggles
        self.text_section.enable_checkbox.stateChanged.connect(
            lambda state: self.text_mapping_editor.set_global_enabled(
                Qt.CheckState(state) == Qt.CheckState.Checked
            )
        )
        self.image_section.enable_checkbox.stateChanged.connect(
            lambda state: self.image_mapping_editor.set_global_enabled(
                Qt.CheckState(state) == Qt.CheckState.Checked
            )
        )
        self.audio_section.enable_checkbox.stateChanged.connect(
            lambda state: self.audio_mapping_editor.set_global_enabled(
                Qt.CheckState(state) == Qt.CheckState.Checked
            )
        )

    def _install_dirty_watchers(self) -> None:
        # Retry controls
        self.retry_section.retry_limit_input.textChanged.connect(self._on_field_modified)
        self.retry_section.retry_delay_input.textChanged.connect(self._on_field_modified)

        # Section toggles
        self.text_section.enable_checkbox.stateChanged.connect(self._on_field_modified)
        self.image_section.enable_checkbox.stateChanged.connect(self._on_field_modified)
        self.audio_section.enable_checkbox.stateChanged.connect(self._on_field_modified)

        # Mapping editors
        self.text_mapping_editor.rowsChanged.connect(self._on_field_modified)
        self.image_mapping_editor.rowsChanged.connect(self._on_field_modified)
        self.audio_mapping_editor.rowsChanged.connect(self._on_field_modified)

        # Text provider inputs
        self.api_key_input.textChanged.connect(self._on_field_modified)
        self.endpoint_input.textChanged.connect(self._on_field_modified)
        self.model_input.textChanged.connect(self._on_field_modified)
        self.system_prompt_input.textChanged.connect(self._on_field_modified)
        self.user_prompt_input.textChanged.connect(self._on_field_modified)

        # Image provider inputs
        self.image_api_key_input.textChanged.connect(self._on_field_modified)
        self.image_endpoint_input.textChanged.connect(self._on_field_modified)
        self.image_model_input.textChanged.connect(self._on_field_modified)

        # Audio provider inputs
        self.audio_api_key_input.textChanged.connect(self._on_field_modified)
        self.audio_endpoint_input.textChanged.connect(self._on_field_modified)
        self.audio_model_input.textChanged.connect(self._on_field_modified)
        self.audio_voice_input.textChanged.connect(self._on_field_modified)
        self.audio_format_input.textChanged.connect(self._on_field_modified)
        # YouGlish inputs
        self.youglish_enable_checkbox.stateChanged.connect(self._on_field_modified)
        self.youglish_source_input.textChanged.connect(self._on_field_modified)
        self.youglish_target_input.textChanged.connect(self._on_field_modified)
        self.youglish_accent_combo.currentIndexChanged.connect(self._on_field_modified)
        self.youglish_overwrite_checkbox.stateChanged.connect(self._on_field_modified)

    def _on_field_modified(self, *args: object) -> None:
        if self._loading:
            return
        self._mark_dirty()

    def _reset_dirty_state(self) -> None:
        self._initial_state = self._capture_state()
        self._dirty = False
        self._provider_indices["text"] = (
            self.text_section.provider_combo.currentIndex()
            if self.text_section.provider_combo is not None
            else -1
        )
        self._provider_indices["image"] = (
            self.image_section.provider_combo.currentIndex()
            if self.image_section.provider_combo is not None
            else -1
        )
        self._provider_indices["audio"] = (
            self.audio_section.provider_combo.currentIndex()
            if self.audio_section.provider_combo is not None
            else -1
        )

    def _mark_dirty(self) -> None:
        self._dirty = self._capture_state() != self._initial_state

    def _capture_state(self) -> Dict[str, Any]:
        text_provider = self.text_section.provider()
        image_provider = self.image_section.provider()
        audio_provider = self.audio_section.provider()
        return {
            "retry_limit_text": self.retry_section.retry_limit_input.text().strip(),
            "retry_delay_text": self.retry_section.retry_delay_input.text().strip(),
            "text_enabled": self.text_section.is_enabled(),
            "text_provider": text_provider,
            "text_mappings": tuple(self.text_mapping_editor.get_entries()),
            "text_api_key": self.api_key_input.text().strip(),
            "text_endpoint": self.endpoint_input.text().strip(),
            "text_model": self.model_input.text().strip(),
            "system_prompt": self.system_prompt_input.toPlainText().strip(),
            "user_prompt": self.user_prompt_input.toPlainText().strip(),
            "image_enabled": self.image_section.is_enabled(),
            "image_provider": image_provider,
            "image_mappings": tuple(self.image_mapping_editor.get_entries()),
            "image_api_key": self.image_api_key_input.text().strip(),
            "image_endpoint": self.image_endpoint_input.text().strip(),
            "image_model": self.image_model_input.text().strip(),
            "audio_enabled": self.audio_section.is_enabled(),
            "audio_provider": audio_provider,
            "audio_mappings": tuple(self.audio_mapping_editor.get_entries()),
            "audio_api_key": self.audio_api_key_input.text().strip(),
            "audio_endpoint": self.audio_endpoint_input.text().strip(),
            "audio_model": self.audio_model_input.text().strip(),
            "audio_voice": self.audio_voice_input.text().strip(),
            "audio_format": self.audio_format_input.text().strip(),
            "youglish_enabled": self.youglish_enable_checkbox.isChecked(),
            "youglish_source": self.youglish_source_input.text().strip(),
            "youglish_target": self.youglish_target_input.text().strip(),
            "youglish_accent": self.youglish_accent_combo.currentData(),
            "youglish_overwrite": self.youglish_overwrite_checkbox.isChecked(),
        }

    def _has_unsaved_changes(self) -> bool:
        return False if self._loading else self._dirty

    def _confirm_discard_changes(self, context: str) -> bool:
        if not self._has_unsaved_changes():
            return True
        response = QMessageBox.question(
            self,
            "放弃未保存的修改",
            f"当前设置存在未保存的变更。确定要{context}并放弃这些修改吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return response == QMessageBox.StandardButton.Yes

    def _on_provider_combo_changed(self, kind: str, index: int) -> None:
        if kind == "text":
            combo = self.text_section.provider_combo
            update_button = self._update_text_reset_button
        elif kind == "image":
            combo = self.image_section.provider_combo
            update_button = self._update_image_reset_button
        else:
            combo = self.audio_section.provider_combo
            update_button = self._update_audio_reset_button
        if combo is None:
            return
        previous_index = self._provider_indices.get(kind, -1)
        if self._loading:
            self._provider_indices[kind] = index
            update_button()
            return
        if previous_index == index:
            update_button()
            return
        if self._dirty and not self._confirm_discard_changes("切换提供者"):
            self._loading = True
            combo.setCurrentIndex(previous_index)
            self._loading = False
            update_button()
            return
        self._provider_indices[kind] = index
        update_button()
        self._mark_dirty()

    # Data loading -----------------------------------------------------

    def _load_from_settings(self) -> None:
        retry_limit = int(
            self.app_settings.value(
                SettingsNames.RETRY_LIMIT_SETTING_NAME, defaultValue=50
            )
            or 50
        )
        retry_delay = float(
            self.app_settings.value(
                SettingsNames.RETRY_DELAY_SETTING_NAME, defaultValue=5.0
            )
            or 5.0
        )
        self.retry_section.set_values(retry_limit, retry_delay)

        enable_text = self._get_bool_setting(
            SettingsNames.ENABLE_TEXT_GENERATION_SETTING_NAME, True
        )
        self.text_section.set_enabled(enable_text)
        self.text_mapping_editor.set_global_enabled(enable_text)
        text_rows = self._load_text_rows()
        self.text_mapping_editor.set_entries(text_rows)

        self.api_key_input.setText(
            self.app_settings.value(SettingsNames.API_KEY_SETTING_NAME, type=str) or ""
        )
        self.endpoint_input.setText(
            self.app_settings.value(SettingsNames.ENDPOINT_SETTING_NAME, type=str) or ""
        )
        self.model_input.setText(
            self.app_settings.value(SettingsNames.MODEL_SETTING_NAME, type=str) or ""
        )
        self.system_prompt_input.setPlainText(
            self.app_settings.value(SettingsNames.SYSTEM_PROMPT_SETTING_NAME, type=str)
            or ""
        )
        self.user_prompt_input.setPlainText(
            self.app_settings.value(SettingsNames.USER_PROMPT_SETTING_NAME, type=str)
            or ""
        )
        text_provider = (
            self.app_settings.value(SettingsNames.TEXT_PROVIDER_SETTING_NAME, type=str)
            or "custom"
        )
        text_custom_value = (
            self.app_settings.value(
                SettingsNames.TEXT_PROVIDER_CUSTOM_VALUE_SETTING_NAME,
                defaultValue="",
                type=str,
            )
            or ""
        )
        self.text_section.set_provider(text_provider, text_custom_value)

        enable_image = self._get_bool_setting(
            SettingsNames.ENABLE_IMAGE_GENERATION_SETTING_NAME, True
        )
        self.image_section.set_enabled(enable_image)
        self.image_mapping_editor.set_global_enabled(enable_image)
        image_rows = self._decode_mapping_rows(
            self.app_settings.value(
                SettingsNames.IMAGE_MAPPING_SETTING_NAME, type="QStringList"
            )
            or []
        )
        self.image_mapping_editor.set_entries(image_rows)
        self.image_api_key_input.setText(
            self.app_settings.value(SettingsNames.IMAGE_API_KEY_SETTING_NAME, type=str)
            or ""
        )
        self.image_endpoint_input.setText(
            self.app_settings.value(SettingsNames.IMAGE_ENDPOINT_SETTING_NAME, type=str)
            or ""
        )
        self.image_model_input.setText(
            self.app_settings.value(SettingsNames.IMAGE_MODEL_SETTING_NAME, type=str)
            or ""
        )
        image_provider = (
            self.app_settings.value(SettingsNames.IMAGE_PROVIDER_SETTING_NAME, type=str)
            or "custom"
        )
        self.image_section.set_provider(image_provider)

        enable_audio = self._get_bool_setting(
            SettingsNames.ENABLE_AUDIO_GENERATION_SETTING_NAME, True
        )
        self.audio_section.set_enabled(enable_audio)
        self.audio_mapping_editor.set_global_enabled(enable_audio)
        audio_rows = self._decode_mapping_rows(
            self.app_settings.value(
                SettingsNames.AUDIO_MAPPING_SETTING_NAME, type="QStringList"
            )
            or []
        )
        self.audio_mapping_editor.set_entries(audio_rows)
        self.audio_api_key_input.setText(
            self.app_settings.value(SettingsNames.AUDIO_API_KEY_SETTING_NAME, type=str)
            or ""
        )
        self.audio_endpoint_input.setText(
            self.app_settings.value(SettingsNames.AUDIO_ENDPOINT_SETTING_NAME, type=str)
            or ""
        )
        self.audio_model_input.setText(
            self.app_settings.value(SettingsNames.AUDIO_MODEL_SETTING_NAME, type=str)
            or ""
        )
        self.audio_voice_input.setText(
            self.app_settings.value(SettingsNames.AUDIO_VOICE_SETTING_NAME, type=str)
            or ""
        )
        self.audio_format_input.setText(
            self.app_settings.value(SettingsNames.AUDIO_FORMAT_SETTING_NAME, type=str)
            or "wav"
        )
        audio_provider = (
            self.app_settings.value(SettingsNames.AUDIO_PROVIDER_SETTING_NAME, type=str)
            or "custom"
        )
        self.audio_section.set_provider(audio_provider)

        youglish_enabled = self._get_bool_setting(
            SettingsNames.YOUGLISH_ENABLED_SETTING_NAME, True
        )
        self.youglish_enable_checkbox.setChecked(youglish_enabled)
        self.youglish_source_input.setText(
            self.app_settings.value(
                SettingsNames.YOUGLISH_SOURCE_FIELD_SETTING_NAME,
                defaultValue="_word",
                type=str,
            )
            or "_word"
        )
        self.youglish_target_input.setText(
            self.app_settings.value(
                SettingsNames.YOUGLISH_TARGET_FIELD_SETTING_NAME,
                defaultValue="_youglish",
                type=str,
            )
            or "_youglish"
        )
        self._select_youglish_accent(
            self.app_settings.value(
                SettingsNames.YOUGLISH_ACCENT_SETTING_NAME,
                defaultValue="us",
                type=str,
            )
            or "us"
        )
        self.youglish_overwrite_checkbox.setChecked(
            self._get_bool_setting(SettingsNames.YOUGLISH_OVERWRITE_SETTING_NAME, False)
        )
        self._update_youglish_enabled_state()

        self._update_text_reset_button()
        self._update_image_reset_button()
        self._update_audio_reset_button()

    # Public helpers ---------------------------------------------------

    def update_note_type_status(
        self,
        allowed_note_types: Sequence[str],
        missing_note_types: Sequence[str],
    ) -> None:
        """Show a warning when selected notes are outside the config scope."""
        if not missing_note_types:
            self.note_type_status.hide()
            return
        allowed_text = ", ".join(allowed_note_types) if allowed_note_types else "none"
        missing_text = ", ".join(missing_note_types)
        self.note_type_status.setText(
            (
                "Selected notes include types not covered by this configuration: "
                f"{missing_text}.\n"
                f"Configured types: {allowed_text}"
            )
        )
        self.note_type_status.show()

    # Acceptance -------------------------------------------------------

    def accept(self) -> bool:
        if not self._validate():
            return False
        self._persist()
        self._reset_dirty_state()
        return True

    # Internal helpers -------------------------------------------------

    def _validate(self) -> bool:
        text_enabled = self.text_section.is_enabled()
        image_enabled = self.image_section.is_enabled()
        audio_enabled = self.audio_section.is_enabled()

        if text_enabled and not self.api_key_input.text().strip():
            self._show_error("Enter the API key before running the plugin.")
            return False
        if text_enabled and not self.user_prompt_input.toPlainText().strip():
            self._show_error("Enter a user prompt before running the plugin.")
            return False

        text_rows = self.text_mapping_editor.get_entries()
        has_text_mapping = any(key and field and enabled for key, field, enabled in text_rows)
        if text_enabled and not has_text_mapping:
            self._show_error("Configure at least one text mapping before running the plugin.")
            return False

        image_rows = self.image_mapping_editor.get_entries()
        has_image_mapping = any(enabled and prompt and target for prompt, target, enabled in image_rows)
        if image_enabled and has_image_mapping and not self.image_api_key_input.text().strip():
            self._show_error("Enter the image API key before generating images.")
            return False

        audio_rows = self.audio_mapping_editor.get_entries()
        has_audio_mapping = any(enabled and source and dest for source, dest, enabled in audio_rows)
        if audio_enabled and has_audio_mapping and not self.audio_api_key_input.text().strip():
            self._show_error("Enter the speech API key before generating audio.")
            return False
        if self.youglish_enable_checkbox.isChecked():
            if not self.youglish_source_input.text().strip() or not self.youglish_target_input.text().strip():
                self._show_error("Enter both source and target fields for YouGlish links.")
                return False

        retry_limit, retry_delay = self.retry_section.values()
        if retry_limit <= 0:
            self._show_error("Retry attempts must be greater than zero.")
            return False
        if retry_delay <= 0:
            self._show_error("Retry delay must be greater than zero.")
            return False
        return True

    def _persist(self) -> None:
        retry_limit, retry_delay = self.retry_section.values()
        self.app_settings.setValue(SettingsNames.RETRY_LIMIT_SETTING_NAME, retry_limit)
        self.app_settings.setValue(SettingsNames.RETRY_DELAY_SETTING_NAME, retry_delay)

        self.app_settings.setValue(
            SettingsNames.API_KEY_SETTING_NAME, self.api_key_input.text().strip()
        )
        self.app_settings.setValue(
            SettingsNames.ENDPOINT_SETTING_NAME, self.endpoint_input.text().strip()
        )
        self.app_settings.setValue(
            SettingsNames.MODEL_SETTING_NAME, self.model_input.text().strip()
        )
        self.app_settings.setValue(
            SettingsNames.SYSTEM_PROMPT_SETTING_NAME,
            self.system_prompt_input.toPlainText().strip(),
        )
        self.app_settings.setValue(
            SettingsNames.USER_PROMPT_SETTING_NAME,
            self.user_prompt_input.toPlainText().strip(),
        )

        text_rows = self.text_mapping_editor.get_entries()
        text_entries = [
            {"key": key, "field": field, "enabled": enabled}
            for key, field, enabled in text_rows
            if key or field
        ]
        response_keys = [key for key, field, enabled in text_rows if enabled and key and field]
        destination_fields = [field for key, field, enabled in text_rows if enabled and key and field]
        self.app_settings.setValue(
            SettingsNames.TEXT_MAPPING_ENTRIES_SETTING_NAME,
            json.dumps(text_entries, ensure_ascii=False),
        )
        self.app_settings.setValue(
            SettingsNames.RESPONSE_KEYS_SETTING_NAME,
            response_keys,
        )
        self.app_settings.setValue(
            SettingsNames.DESTINATION_FIELD_SETTING_NAME,
            destination_fields,
        )
        self.app_settings.setValue(
            SettingsNames.ENABLE_TEXT_GENERATION_SETTING_NAME,
            self.text_section.is_enabled(),
        )

        self.app_settings.setValue(
            SettingsNames.IMAGE_MAPPING_SETTING_NAME,
            self._encode_mapping_entries(self.image_mapping_editor.get_entries()),
        )
        self.app_settings.setValue(
            SettingsNames.IMAGE_API_KEY_SETTING_NAME,
            self.image_api_key_input.text().strip(),
        )
        self.app_settings.setValue(
            SettingsNames.IMAGE_ENDPOINT_SETTING_NAME,
            self.image_endpoint_input.text().strip(),
        )
        self.app_settings.setValue(
            SettingsNames.IMAGE_MODEL_SETTING_NAME,
            self.image_model_input.text().strip(),
        )
        self.app_settings.setValue(
            SettingsNames.ENABLE_IMAGE_GENERATION_SETTING_NAME,
            self.image_section.is_enabled(),
        )

        self.app_settings.setValue(
            SettingsNames.AUDIO_MAPPING_SETTING_NAME,
            self._encode_mapping_entries(self.audio_mapping_editor.get_entries()),
        )
        self.app_settings.setValue(
            SettingsNames.AUDIO_API_KEY_SETTING_NAME,
            self.audio_api_key_input.text().strip(),
        )
        self.app_settings.setValue(
            SettingsNames.AUDIO_ENDPOINT_SETTING_NAME,
            self.audio_endpoint_input.text().strip(),
        )
        self.app_settings.setValue(
            SettingsNames.AUDIO_MODEL_SETTING_NAME,
            self.audio_model_input.text().strip(),
        )
        self.app_settings.setValue(
            SettingsNames.AUDIO_VOICE_SETTING_NAME,
            self.audio_voice_input.text().strip(),
        )
        self.app_settings.setValue(
            SettingsNames.AUDIO_FORMAT_SETTING_NAME,
            self.audio_format_input.text().strip() or "wav",
        )
        self.app_settings.setValue(
            SettingsNames.ENABLE_AUDIO_GENERATION_SETTING_NAME,
            self.audio_section.is_enabled(),
        )
        self.app_settings.setValue(
            SettingsNames.YOUGLISH_ENABLED_SETTING_NAME,
            self.youglish_enable_checkbox.isChecked(),
        )
        self.app_settings.setValue(
            SettingsNames.YOUGLISH_SOURCE_FIELD_SETTING_NAME,
            self.youglish_source_input.text().strip() or "_word",
        )
        self.app_settings.setValue(
            SettingsNames.YOUGLISH_TARGET_FIELD_SETTING_NAME,
            self.youglish_target_input.text().strip() or "_youglish",
        )
        self.app_settings.setValue(
            SettingsNames.YOUGLISH_ACCENT_SETTING_NAME,
            str(self.youglish_accent_combo.currentData() or "us"),
        )
        self.app_settings.setValue(
            SettingsNames.YOUGLISH_OVERWRITE_SETTING_NAME,
            self.youglish_overwrite_checkbox.isChecked(),
        )

    def _load_text_rows(self) -> list[tuple[str, str, bool]]:
        raw_entries = self.app_settings.value(
            SettingsNames.TEXT_MAPPING_ENTRIES_SETTING_NAME,
            type=str,
        )
        if not raw_entries:
            keys = self.app_settings.value(
                SettingsNames.RESPONSE_KEYS_SETTING_NAME, type="QStringList"
            ) or []
            fields = self.app_settings.value(
                SettingsNames.DESTINATION_FIELD_SETTING_NAME, type="QStringList"
            ) or []
            if keys and fields and len(keys) == len(fields):
                return [(str(k), str(f), True) for k, f in zip(keys, fields)]
            return []
        try:
            data = json.loads(raw_entries)
        except (json.JSONDecodeError, TypeError):
            return []
        entries: list[tuple[str, str, bool]] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("key", "")).strip()
            field = str(entry.get("field", "")).strip()
            enabled = bool(entry.get("enabled", True))
            entries.append((key, field, enabled))
        return entries

    def _apply_text_provider_defaults(self, *, force: bool = False) -> None:
        combo = self.text_section.provider_combo
        if combo is None:
            return
        provider = combo.currentData()
        if provider is None:
            return
        provider_key = str(provider).lower()
        defaults = TEXT_PROVIDER_DEFAULTS.get(provider_key)
        if not defaults:
            return
        endpoint_default = defaults.get("endpoint", "")
        model_default = defaults.get("model", "")
        if endpoint_default and (force or not self.endpoint_input.text().strip()):
            self.endpoint_input.setText(endpoint_default)
        if model_default and (force or not self.model_input.text().strip()):
            self.model_input.setText(model_default)
        self._update_text_reset_button()

    def _apply_image_provider_defaults(self, *, force: bool = False) -> None:
        combo = self.image_section.provider_combo
        if combo is None:
            return
        provider = combo.currentData()
        if provider is None:
            return
        provider_key = str(provider).lower()
        defaults = IMAGE_PROVIDER_DEFAULTS.get(provider_key)
        if not defaults:
            return
        endpoint_default = defaults.get("endpoint", "")
        model_default = defaults.get("model", "")
        if endpoint_default and (force or not self.image_endpoint_input.text().strip()):
            self.image_endpoint_input.setText(endpoint_default)
        if model_default and (force or not self.image_model_input.text().strip()):
            self.image_model_input.setText(model_default)
        self._update_image_reset_button()

    def _apply_audio_provider_defaults(self, *, force: bool = False) -> None:
        combo = self.audio_section.provider_combo
        if combo is None:
            return
        provider = combo.currentData()
        if provider is None:
            return
        provider_key = str(provider).lower()
        defaults = AUDIO_PROVIDER_DEFAULTS.get(provider_key)
        if not defaults:
            return
        endpoint_default = defaults.get("endpoint", "")
        model_default = defaults.get("model", "")
        if endpoint_default and (force or not self.audio_endpoint_input.text().strip()):
            self.audio_endpoint_input.setText(endpoint_default)
        if model_default and (force or not self.audio_model_input.text().strip()):
            self.audio_model_input.setText(model_default)
        self._update_audio_reset_button()

    def _update_text_reset_button(self) -> None:
        enabled = False
        if self.text_section.provider_combo is not None:
            provider = self.text_section.provider_combo.currentData()
            if provider is not None:
                enabled = str(provider).lower() in TEXT_PROVIDER_DEFAULTS
        self.text_defaults_button.setEnabled(enabled)

    def _update_image_reset_button(self) -> None:
        enabled = False
        if self.image_section.provider_combo is not None:
            provider = self.image_section.provider_combo.currentData()
            if provider is not None:
                enabled = str(provider).lower() in IMAGE_PROVIDER_DEFAULTS
        self.image_defaults_button.setEnabled(enabled)

    def _update_audio_reset_button(self) -> None:
        enabled = False
        if self.audio_section.provider_combo is not None:
            provider = self.audio_section.provider_combo.currentData()
            if provider is not None:
                enabled = str(provider).lower() in AUDIO_PROVIDER_DEFAULTS
        self.audio_defaults_button.setEnabled(enabled)

    def _select_youglish_accent(self, accent: str) -> None:
        normalized = (accent or "us").lower()
        index = self.youglish_accent_combo.findData(normalized)
        if index == -1:
            normalized = "us"
            index = self.youglish_accent_combo.findData(normalized)
        blocked = self.youglish_accent_combo.blockSignals(True)
        if index != -1:
            self.youglish_accent_combo.setCurrentIndex(index)
        self.youglish_accent_combo.blockSignals(blocked)

    def _update_youglish_enabled_state(self) -> None:
        enabled = self.youglish_enable_checkbox.isChecked()
        for widget in (
            self.youglish_source_input,
            self.youglish_target_input,
            self.youglish_accent_combo,
            self.youglish_overwrite_checkbox,
        ):
            widget.setEnabled(enabled)

    def _decode_mapping_rows(
        self, entries: Iterable[str]
    ) -> list[tuple[str, str, bool]]:
        decoded: list[tuple[str, str, bool]] = []
        for mapping in entries:
            if not isinstance(mapping, str) or IMAGE_MAPPING_SEPARATOR not in mapping:
                continue
            base = mapping
            enabled = True
            if "::" in mapping:
                base, flag = mapping.rsplit("::", 1)
                enabled = flag.strip().lower() not in {"0", "false", "no"}
            if IMAGE_MAPPING_SEPARATOR not in base:
                continue
            left, right = [part.strip() for part in base.split(IMAGE_MAPPING_SEPARATOR, 1)]
            if left or right:
                decoded.append((left, right, enabled))
        return decoded

    def _encode_mapping_entries(
        self, entries: Iterable[tuple[str, str, bool]]
    ) -> list[str]:
        encoded: list[str] = []
        for left, right, enabled in entries:
            if not left or not right:
                continue
            flag = "1" if enabled else "0"
            encoded.append(f"{left}{IMAGE_MAPPING_SEPARATOR}{right}::{flag}")
        return encoded

    def _get_bool_setting(self, name: str, default: bool) -> bool:
        value = self.app_settings.value(name, defaultValue=default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes"}
        return bool(value)

    @staticmethod
    def _show_error(message: str) -> None:
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Configuration error")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()


__all__ = [
    "UserBaseDialog",
    "IMAGE_MAPPING_SEPARATOR",
]
