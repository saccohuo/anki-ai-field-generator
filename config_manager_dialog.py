from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Sequence

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from aqt import mw  # type: ignore
except Exception:  # pragma: no cover - tests without Anki
    mw = None  # type: ignore

from .config_store import ConfigStore, LLMConfig
from .mapping_sections import GenerationSection, RetrySection, ToggleMappingEditor
from .provider_options import (
    AUDIO_PROVIDERS,
    AUDIO_PROVIDER_DEFAULTS,
    IMAGE_PROVIDERS,
    IMAGE_PROVIDER_DEFAULTS,
    TEXT_PROVIDERS,
    TEXT_PROVIDER_DEFAULTS,
)
from .user_base_dialog import IMAGE_MAPPING_SEPARATOR


class NoteTypeSelector(QGroupBox):
    """Checklist for binding a configuration to multiple note types."""

    def __init__(
        self,
        note_types: Sequence[tuple[str, str]],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__("Applicable note types", parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        description = QLabel(
            "Select the note types that should use this configuration."
            " Leave empty to allow any note type."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.list_widget)

        button_row = QHBoxLayout()
        self.select_all_button = QPushButton("Select All")
        self.select_all_button.clicked.connect(self._select_all)
        button_row.addWidget(self.select_all_button)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear_selection)
        button_row.addWidget(self.clear_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.set_note_types(note_types)

    def set_note_types(self, note_types: Sequence[tuple[str, str]]):
        self.list_widget.clear()
        for note_type_id, name in note_types:
            item = QListWidgetItem(name or str(note_type_id))
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemNeverHasChildren
            )
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, str(note_type_id))
            self.list_widget.addItem(item)

    def set_selected_ids(self, selected_ids: Iterable[str]) -> None:
        normalized = {str(note_id) for note_id in selected_ids}
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            item_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
            item.setCheckState(
                Qt.CheckState.Checked
                if item_id in normalized
                else Qt.CheckState.Unchecked
            )

    def selected_ids(self) -> list[str]:
        ids: list[str] = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                item_id = item.data(Qt.ItemDataRole.UserRole)
                if item_id is not None:
                    ids.append(str(item_id))
        return ids

    def _select_all(self) -> None:
        for index in range(self.list_widget.count()):
            self.list_widget.item(index).setCheckState(Qt.CheckState.Checked)

    def _clear_selection(self) -> None:
        for index in range(self.list_widget.count()):
            self.list_widget.item(index).setCheckState(Qt.CheckState.Unchecked)


class ConfigManagerDialog(QDialog):
    """Dialog allowing users to maintain multiple LLM configurations."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Manage LLM Configurations")
        self.resize(900, 560)
        self.store = ConfigStore()
        self._current_name: Optional[str] = None
        self._note_types = self._load_note_types()
        self._current_text_provider: str = ""
        self._current_image_provider: str = ""
        self._current_audio_provider: str = ""
        self._text_api_keys: dict[str, str] = {}
        self._image_api_keys: dict[str, str] = {}
        self._audio_api_keys: dict[str, str] = {}
        self._loading = True
        self._dirty = False
        self._form_snapshot: Dict[str, Any] = {}

        self._build_ui()
        self._install_dirty_watchers()
        self._load_configs()
        self._loading = False
        self._reset_dirty_state()
        self.prompt_save_if_example(self.store, self)

    # UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # Left column: list of saved configurations
        list_column = QVBoxLayout()
        self.config_list = QListWidget()
        self.config_list.currentItemChanged.connect(self._on_selection_changed)
        list_column.addWidget(self.config_list)

        list_buttons = QHBoxLayout()
        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(self._on_new)
        list_buttons.addWidget(self.new_button)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._on_delete)
        list_buttons.addWidget(self.delete_button)
        list_buttons.addStretch()
        list_column.addLayout(list_buttons)

        main_layout.addLayout(list_column, 1)

        # Right column: scrollable editor + fixed footer
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(12, 8, 12, 8)
        editor_layout.setSpacing(12)

        name_form = QFormLayout()
        name_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Custom configuration name")
        name_form.addRow(QLabel("Configuration Name:"), self.name_input)
        editor_layout.addLayout(name_form)

        self.note_type_selector = NoteTypeSelector(self._note_types)
        editor_layout.addWidget(self.note_type_selector)

        self.retry_section = RetrySection()
        editor_layout.addWidget(self.retry_section)

        # Text generation section
        self.text_mapping_editor = ToggleMappingEditor(
            [],
            left_placeholder="response key",
            right_placeholder="destination field",
        )
        self.text_section = GenerationSection(
            "Text generation",
            "Enable text generation",
            self.text_mapping_editor,
            description="Map model response keys to Anki fields.",
        )
        self.text_section.add_provider_selector(TEXT_PROVIDERS)
        self.text_defaults_button = QPushButton("Restore defaults")
        self.text_defaults_button.clicked.connect(
            lambda: self._apply_text_provider_defaults(force=True)
        )
        self.text_section.add_provider_reset_button(self.text_defaults_button)
        if self.text_section.provider_combo is not None:
            self._current_text_provider = str(
                self.text_section.provider_combo.currentData() or ""
            )
            self.text_section.provider_combo.currentIndexChanged.connect(
                lambda _: self._on_text_provider_changed()
            )
        self._update_text_provider_state()

        text_creds_form = QFormLayout()
        text_creds_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-...")
        text_creds_form.addRow(QLabel("API Key:"), self.api_key_input)
        self.api_key_input.textChanged.connect(self._on_text_api_key_changed)
        self.endpoint_input = QLineEdit()
        self.endpoint_input.setPlaceholderText(
            "https://api.example.com/v1/chat/completions"
        )
        text_creds_form.addRow(QLabel("Endpoint:"), self.endpoint_input)
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("gpt-4o-mini")
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
        editor_layout.addWidget(self.text_section)

        # Image generation section
        self.image_mapping_editor = ToggleMappingEditor(
            [],
            left_placeholder="prompt field",
            right_placeholder="image field",
        )
        self.image_section = GenerationSection(
            "Image generation",
            "Enable image generation",
            self.image_mapping_editor,
            description="Generate images based on mapped prompt fields.",
        )
        self.image_section.add_provider_selector(IMAGE_PROVIDERS)
        self.image_defaults_button = QPushButton("Restore defaults")
        self.image_defaults_button.clicked.connect(
            lambda: self._apply_image_provider_defaults(force=True)
        )
        self.image_section.add_provider_reset_button(self.image_defaults_button)
        if self.image_section.provider_combo is not None:
            self._current_image_provider = str(
                self.image_section.provider_combo.currentData() or ""
            )
            self.image_section.provider_combo.currentIndexChanged.connect(
                lambda _: self._on_image_provider_changed()
            )
        self._update_image_provider_state()

        image_form = QFormLayout()
        image_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.image_api_key_input = QLineEdit()
        self.image_api_key_input.setPlaceholderText("Override image API key")
        image_form.addRow(QLabel("Image API Key:"), self.image_api_key_input)
        self.image_api_key_input.textChanged.connect(self._on_image_api_key_changed)
        self.image_endpoint_input = QLineEdit()
        self.image_endpoint_input.setPlaceholderText(
            "https://generativelanguage.googleapis.com/v1beta/models"
        )
        image_form.addRow(QLabel("Image Endpoint:"), self.image_endpoint_input)
        self.image_model_input = QLineEdit()
        self.image_model_input.setPlaceholderText("gemini-pro-vision")
        image_form.addRow(QLabel("Image Model:"), self.image_model_input)
        self.image_section.add_form_layout(image_form)
        editor_layout.addWidget(self.image_section)

        # Speech generation section
        self.audio_mapping_editor = ToggleMappingEditor(
            [],
            left_placeholder="text field",
            right_placeholder="audio field",
        )
        self.audio_section = GenerationSection(
            "Speech generation",
            "Enable speech generation",
            self.audio_mapping_editor,
            description="Convert mapped text fields into audio clips.",
        )
        self.audio_section.add_provider_selector(AUDIO_PROVIDERS)
        self.audio_defaults_button = QPushButton("Restore defaults")
        self.audio_defaults_button.clicked.connect(
            lambda: self._apply_audio_provider_defaults(force=True)
        )
        self.audio_section.add_provider_reset_button(self.audio_defaults_button)
        if self.audio_section.provider_combo is not None:
            self._current_audio_provider = str(
                self.audio_section.provider_combo.currentData() or ""
            )
            self.audio_section.provider_combo.currentIndexChanged.connect(
                lambda _: self._on_audio_provider_changed()
            )
        self._update_audio_provider_state()

        audio_form = QFormLayout()
        audio_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.audio_api_key_input = QLineEdit()
        self.audio_api_key_input.setPlaceholderText("Speech API key")
        audio_form.addRow(QLabel("Speech API Key:"), self.audio_api_key_input)
        self.audio_api_key_input.textChanged.connect(self._on_audio_api_key_changed)
        self.audio_endpoint_input = QLineEdit()
        self.audio_endpoint_input.setPlaceholderText("Custom speech endpoint")
        audio_form.addRow(QLabel("Speech Endpoint:"), self.audio_endpoint_input)
        self.audio_model_input = QLineEdit()
        self.audio_model_input.setPlaceholderText("gpt-4o-mini-tts")
        audio_form.addRow(QLabel("Speech Model:"), self.audio_model_input)
        self.audio_voice_input = QLineEdit()
        self.audio_voice_input.setPlaceholderText("Preferred voice (e.g. alloy)")
        audio_form.addRow(QLabel("Speech Voice:"), self.audio_voice_input)
        self.audio_format_input = QLineEdit()
        self.audio_format_input.setPlaceholderText("wav")
        audio_form.addRow(QLabel("Speech Format:"), self.audio_format_input)
        self.audio_section.add_form_layout(audio_form)
        editor_layout.addWidget(self.audio_section)

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

        self.text_mapping_editor.set_global_enabled(self.text_section.is_enabled())
        self.image_mapping_editor.set_global_enabled(self.image_section.is_enabled())
        self.audio_mapping_editor.set_global_enabled(self.audio_section.is_enabled())

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(editor_container)

        right_column = QVBoxLayout()
        right_column.addWidget(scroll_area, 1)

        footer_widget = QWidget()
        footer = QHBoxLayout(footer_widget)
        self.open_config_button = QPushButton("Open config file")
        self.open_config_button.clicked.connect(self._open_config_file)
        footer.addWidget(self.open_config_button)
        footer.addStretch()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._on_save)
        footer.addWidget(self.save_button)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        footer.addWidget(self.close_button)
        right_column.addWidget(footer_widget, 0)

        main_layout.addLayout(right_column, 2)

    def _install_dirty_watchers(self) -> None:
        self.name_input.textChanged.connect(self._on_form_modified)
        self.note_type_selector.list_widget.itemChanged.connect(self._on_form_modified)

        self.retry_section.retry_limit_input.textChanged.connect(self._on_form_modified)
        self.retry_section.retry_delay_input.textChanged.connect(self._on_form_modified)

        self.text_section.enable_checkbox.stateChanged.connect(self._on_form_modified)
        self.image_section.enable_checkbox.stateChanged.connect(self._on_form_modified)
        self.audio_section.enable_checkbox.stateChanged.connect(self._on_form_modified)

        self.text_mapping_editor.rowsChanged.connect(self._on_form_modified)
        self.image_mapping_editor.rowsChanged.connect(self._on_form_modified)
        self.audio_mapping_editor.rowsChanged.connect(self._on_form_modified)

        self.endpoint_input.textChanged.connect(self._on_form_modified)
        self.model_input.textChanged.connect(self._on_form_modified)
        self.system_prompt_input.textChanged.connect(self._on_form_modified)
        self.user_prompt_input.textChanged.connect(self._on_form_modified)

        self.image_endpoint_input.textChanged.connect(self._on_form_modified)
        self.image_model_input.textChanged.connect(self._on_form_modified)

        self.audio_endpoint_input.textChanged.connect(self._on_form_modified)
        self.audio_model_input.textChanged.connect(self._on_form_modified)
        self.audio_voice_input.textChanged.connect(self._on_form_modified)
        self.audio_format_input.textChanged.connect(self._on_form_modified)

    # Data helpers -----------------------------------------------------

    def _load_note_types(self) -> list[tuple[str, str]]:
        if mw is None or getattr(mw, "col", None) is None:
            return []
        try:
            models = mw.col.models.all()  # type: ignore[union-attr]
        except Exception:
            return []
        note_types: list[tuple[str, str]] = []
        for model in models:
            model_id = model.get("id")
            name = model.get("name", "")
            if model_id is None:
                continue
            note_types.append((str(model_id), str(name)))
        note_types.sort(key=lambda item: item[1].lower())
        return note_types

    def _load_configs(self) -> None:
        was_loading = self._loading
        self._loading = True
        self.config_list.clear()
        for config in self.store.list_configs():
            item = QListWidgetItem(config.name)
            item.setData(Qt.ItemDataRole.UserRole, config)
            self.config_list.addItem(item)
        if self.config_list.count():
            self.config_list.setCurrentRow(0)
        else:
            self._current_name = None
            self._reset_dirty_state()
        self._loading = was_loading

    def _on_form_modified(self, *args: object) -> None:
        if self._loading:
            return
        self._mark_dirty()

    def _mark_dirty(self) -> None:
        self._dirty = self._capture_form_state() != self._form_snapshot
        self._update_dirty_ui()

    def _reset_dirty_state(self) -> None:
        self._form_snapshot = self._capture_form_state()
        self._dirty = False
        self._update_dirty_ui()

    def _update_dirty_ui(self) -> None:
        self.save_button.setEnabled(self._dirty)

    def _capture_form_state(self) -> Dict[str, Any]:
        text_provider = self.text_section.provider()
        image_provider = self.image_section.provider()
        audio_provider = self.audio_section.provider()
        text_keys = dict(self._text_api_keys)
        image_keys = dict(self._image_api_keys)
        audio_keys = dict(self._audio_api_keys)
        text_keys[text_provider[0]] = self.api_key_input.text().strip()
        image_keys[image_provider[0]] = self.image_api_key_input.text().strip()
        audio_keys[audio_provider[0]] = self.audio_api_key_input.text().strip()
        return {
            "name": self.name_input.text().strip(),
            "note_types": tuple(sorted(self.note_type_selector.selected_ids())),
            "retry_limit_text": self.retry_section.retry_limit_input.text().strip(),
            "retry_delay_text": self.retry_section.retry_delay_input.text().strip(),
            "text_enabled": self.text_section.is_enabled(),
            "text_provider": text_provider,
            "text_mappings": tuple(self.text_mapping_editor.get_entries()),
            "text_api_keys": tuple(sorted(text_keys.items())),
            "text_endpoint": self.endpoint_input.text().strip(),
            "text_model": self.model_input.text().strip(),
            "system_prompt": self.system_prompt_input.toPlainText().strip(),
            "user_prompt": self.user_prompt_input.toPlainText().strip(),
            "image_enabled": self.image_section.is_enabled(),
            "image_provider": image_provider,
            "image_mappings": tuple(self.image_mapping_editor.get_entries()),
            "image_api_keys": tuple(sorted(image_keys.items())),
            "image_endpoint": self.image_endpoint_input.text().strip(),
            "image_model": self.image_model_input.text().strip(),
            "audio_enabled": self.audio_section.is_enabled(),
            "audio_provider": audio_provider,
            "audio_mappings": tuple(self.audio_mapping_editor.get_entries()),
            "audio_api_keys": tuple(sorted(audio_keys.items())),
            "audio_endpoint": self.audio_endpoint_input.text().strip(),
            "audio_model": self.audio_model_input.text().strip(),
            "audio_voice": self.audio_voice_input.text().strip(),
            "audio_format": self.audio_format_input.text().strip(),
        }

    def _has_unsaved_changes(self) -> bool:
        return False if self._loading else self._dirty

    def _confirm_discard_changes(self, context: str) -> bool:
        if not self._has_unsaved_changes():
            return True
        response = QMessageBox.question(
            self,
            "放弃未保存的修改",
            f"当前配置存在未保存的变更。确定要{context}并放弃这些修改吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return response == QMessageBox.StandardButton.Yes

    def _on_selection_changed(
        self,
        current: Optional[QListWidgetItem],
        _previous: Optional[QListWidgetItem],
    ) -> None:
        previous = _previous
        if self._loading:
            if current is None:
                self._current_name = None
                return
            config: LLMConfig = current.data(Qt.ItemDataRole.UserRole)
            self._current_name = config.name
            self._populate_form(config)
            self._reset_dirty_state()
            return
        if previous is not None and self._has_unsaved_changes():
            if not self._confirm_discard_changes("切换配置"):
                self.config_list.blockSignals(True)
                self.config_list.setCurrentItem(previous)
                self.config_list.blockSignals(False)
                return
        if current is None:
            self._current_name = None
            self._reset_dirty_state()
            return
        config: LLMConfig = current.data(Qt.ItemDataRole.UserRole)
        self._current_name = config.name
        self._loading = True
        self._populate_form(config)
        self._loading = False
        self._reset_dirty_state()

    def _populate_form(self, config: LLMConfig) -> None:
        self.name_input.setText(config.name)
        self.note_type_selector.set_selected_ids(config.note_type_ids)
        self.retry_section.set_values(config.retry_limit or 50, config.retry_delay or 5.0)

        self.text_section.set_enabled(config.enable_text_generation)
        self.text_mapping_editor.set_entries(self._decode_text_entries(config.text_mapping_entries))
        self.text_mapping_editor.set_global_enabled(config.enable_text_generation)
        combo = self.text_section.provider_combo
        if combo is not None:
            combo.blockSignals(True)
        self.text_section.set_provider(config.text_provider or "custom", config.text_custom_value)
        if combo is not None:
            combo.blockSignals(False)
        self._text_api_keys = dict(config.text_provider_api_keys or {})
        active_text_provider = config.text_provider or "custom"
        if (config.api_key or "") and active_text_provider not in self._text_api_keys:
            self._text_api_keys[active_text_provider] = config.api_key
        self._load_text_api_key_for_current_provider()
        self.endpoint_input.setText(config.endpoint or "")
        self.model_input.setText(config.model or "")
        self.system_prompt_input.setPlainText(config.system_prompt or "")
        self.user_prompt_input.setPlainText(config.user_prompt or "")
        self._update_text_provider_state()

        self.image_section.set_enabled(config.enable_image_generation)
        self.image_mapping_editor.set_entries(
            self._decode_mapping_strings(config.image_prompt_mappings)
        )
        self.image_mapping_editor.set_global_enabled(config.enable_image_generation)
        image_combo = self.image_section.provider_combo
        if image_combo is not None:
            image_combo.blockSignals(True)
        self.image_section.set_provider(config.image_provider or "custom")
        if image_combo is not None:
            image_combo.blockSignals(False)
        self._image_api_keys = dict(config.image_provider_api_keys or {})
        active_image_provider = config.image_provider or "custom"
        if (config.image_api_key or "") and active_image_provider not in self._image_api_keys:
            self._image_api_keys[active_image_provider] = config.image_api_key
        self._load_image_api_key_for_current_provider()
        self.image_endpoint_input.setText(config.image_endpoint or "")
        self.image_model_input.setText(config.image_model or "")
        self._update_image_provider_state()

        self.audio_section.set_enabled(config.enable_audio_generation)
        self.audio_mapping_editor.set_entries(
            self._decode_mapping_strings(config.audio_prompt_mappings)
        )
        self.audio_mapping_editor.set_global_enabled(config.enable_audio_generation)
        audio_combo = self.audio_section.provider_combo
        if audio_combo is not None:
            audio_combo.blockSignals(True)
        self.audio_section.set_provider(config.audio_provider or "custom")
        if audio_combo is not None:
            audio_combo.blockSignals(False)
        self._audio_api_keys = dict(config.audio_provider_api_keys or {})
        active_audio_provider = config.audio_provider or "custom"
        if (config.audio_api_key or "") and active_audio_provider not in self._audio_api_keys:
            self._audio_api_keys[active_audio_provider] = config.audio_api_key
        self._load_audio_api_key_for_current_provider()
        self.audio_endpoint_input.setText(config.audio_endpoint or "")
        self.audio_model_input.setText(config.audio_model or "")
        self.audio_voice_input.setText(config.audio_voice or "")
        self.audio_format_input.setText(config.audio_format or "wav")
        self._update_audio_provider_state()

    def _decode_text_entries(
        self, entries: Sequence[dict[str, object]] | None
    ) -> list[tuple[str, str, bool]]:
        decoded: list[tuple[str, str, bool]] = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("key", "")).strip()
            field = str(entry.get("field", "")).strip()
            enabled = bool(entry.get("enabled", True))
            decoded.append((key, field, enabled))
        return decoded

    def _collect_form(self) -> Optional[LLMConfig]:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Enter a configuration name.")
            return None

        text_rows = self.text_mapping_editor.get_entries()
        text_entries: list[dict[str, object]] = []
        response_keys: list[str] = []
        destination_fields: list[str] = []
        for key, field, enabled in text_rows:
            text_entries.append({"key": key, "field": field, "enabled": enabled})
            if enabled and key and field:
                response_keys.append(key)
                destination_fields.append(field)

        image_rows = self.image_mapping_editor.get_entries()
        audio_rows = self.audio_mapping_editor.get_entries()

        retry_limit, retry_delay = self.retry_section.values()

        text_provider, text_custom = self.text_section.provider()
        image_provider, image_custom = self.image_section.provider()
        audio_provider, audio_custom = self.audio_section.provider()
        current_text_key = self.api_key_input.text().strip()
        self._text_api_keys[text_provider] = current_text_key
        active_text_key = current_text_key
        current_image_key = self.image_api_key_input.text().strip()
        self._image_api_keys[image_provider] = current_image_key
        active_image_key = current_image_key
        current_audio_key = self.audio_api_key_input.text().strip()
        self._audio_api_keys[audio_provider] = current_audio_key
        active_audio_key = current_audio_key

        config = LLMConfig(
            name=name,
            note_type_ids=self.note_type_selector.selected_ids(),
            text_provider=text_provider,
            text_custom_value=text_custom or "",
            endpoint=self.endpoint_input.text().strip(),
            api_key=active_text_key,
            model=self.model_input.text().strip(),
            system_prompt=self.system_prompt_input.toPlainText().strip(),
            user_prompt=self.user_prompt_input.toPlainText().strip(),
            response_keys=response_keys,
            destination_fields=destination_fields,
            text_mapping_entries=text_entries,
            text_provider_api_keys=dict(self._text_api_keys),
            enable_text_generation=self.text_section.is_enabled(),
            image_provider=image_provider,
            image_prompt_mappings=self._encode_mapping_entries(image_rows),
            image_api_key=active_image_key,
            image_provider_api_keys=dict(self._image_api_keys),
            image_endpoint=self.image_endpoint_input.text().strip(),
            image_model=self.image_model_input.text().strip() or image_custom or "",
            enable_image_generation=self.image_section.is_enabled(),
            audio_provider=audio_provider,
            audio_prompt_mappings=self._encode_mapping_entries(audio_rows),
            audio_api_key=active_audio_key,
            audio_provider_api_keys=dict(self._audio_api_keys),
            audio_endpoint=self.audio_endpoint_input.text().strip(),
            audio_model=self.audio_model_input.text().strip() or audio_custom or "",
            audio_voice=self.audio_voice_input.text().strip(),
            audio_format=self.audio_format_input.text().strip() or "wav",
            enable_audio_generation=self.audio_section.is_enabled(),
            retry_limit=retry_limit,
            retry_delay=retry_delay,
        )
        return config

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

    def _update_text_reset_button(self) -> None:
        enabled = False
        if self.text_section.provider_combo is not None:
            provider = self.text_section.provider_combo.currentData()
            if provider is not None:
                enabled = str(provider).lower() in TEXT_PROVIDER_DEFAULTS
        self.text_defaults_button.setEnabled(enabled)

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

    def _update_image_reset_button(self) -> None:
        enabled = False
        if self.image_section.provider_combo is not None:
            provider = self.image_section.provider_combo.currentData()
            if provider is not None:
                enabled = str(provider).lower() in IMAGE_PROVIDER_DEFAULTS
        self.image_defaults_button.setEnabled(enabled)

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

    def _load_text_api_key_for_current_provider(self) -> None:
        provider = ""
        if self.text_section.provider_combo is not None:
            provider = str(self.text_section.provider_combo.currentData() or "")
        value = self._text_api_keys.get(provider, "")
        self._set_line_edit_text(self.api_key_input, value)

    def _load_image_api_key_for_current_provider(self) -> None:
        provider = ""
        if self.image_section.provider_combo is not None:
            provider = str(self.image_section.provider_combo.currentData() or "")
        value = self._image_api_keys.get(provider, "")
        self._set_line_edit_text(self.image_api_key_input, value)

    def _load_audio_api_key_for_current_provider(self) -> None:
        provider = ""
        if self.audio_section.provider_combo is not None:
            provider = str(self.audio_section.provider_combo.currentData() or "")
        value = self._audio_api_keys.get(provider, "")
        self._set_line_edit_text(self.audio_api_key_input, value)

    def _update_audio_reset_button(self) -> None:
        enabled = False
        if self.audio_section.provider_combo is not None:
            provider = self.audio_section.provider_combo.currentData()
            if provider is not None:
                enabled = str(provider).lower() in AUDIO_PROVIDER_DEFAULTS
        self.audio_defaults_button.setEnabled(enabled)

    def _on_text_provider_changed(self) -> None:
        combo = self.text_section.provider_combo
        if combo is None:
            return
        provider = str(combo.currentData() or "")
        if self._loading:
            self._current_text_provider = provider
            self._update_text_reset_button()
            return
        if provider == self._current_text_provider:
            self._update_text_reset_button()
            return
        if self._dirty and not self._confirm_discard_changes("切换文本提供者"):
            self._loading = True
            revert_index = combo.findData(self._current_text_provider)
            if revert_index != -1:
                combo.setCurrentIndex(revert_index)
            self._loading = False
            self._update_text_reset_button()
            return
        self._current_text_provider = provider
        defaults = TEXT_PROVIDER_DEFAULTS.get(provider.lower())
        if defaults is not None:
            self._apply_text_provider_defaults(force=True)
        self._load_text_api_key_for_current_provider()
        self._update_text_reset_button()
        self._mark_dirty()

    def _on_image_provider_changed(self) -> None:
        combo = self.image_section.provider_combo
        if combo is None:
            return
        provider = str(combo.currentData() or "")
        if self._loading:
            self._current_image_provider = provider
            self._update_image_reset_button()
            return
        if provider == self._current_image_provider:
            self._update_image_reset_button()
            return
        if self._dirty and not self._confirm_discard_changes("切换图像提供者"):
            self._loading = True
            revert_index = combo.findData(self._current_image_provider)
            if revert_index != -1:
                combo.setCurrentIndex(revert_index)
            self._loading = False
            self._update_image_reset_button()
            return
        self._current_image_provider = provider
        defaults = IMAGE_PROVIDER_DEFAULTS.get(provider.lower())
        if defaults is not None:
            self._apply_image_provider_defaults(force=True)
        self._load_image_api_key_for_current_provider()
        self._update_image_reset_button()
        self._mark_dirty()

    def _on_audio_provider_changed(self) -> None:
        combo = self.audio_section.provider_combo
        if combo is None:
            return
        provider = str(combo.currentData() or "")
        if self._loading:
            self._current_audio_provider = provider
            self._update_audio_reset_button()
            return
        if provider == self._current_audio_provider:
            self._update_audio_reset_button()
            return
        if self._dirty and not self._confirm_discard_changes("切换语音提供者"):
            self._loading = True
            revert_index = combo.findData(self._current_audio_provider)
            if revert_index != -1:
                combo.setCurrentIndex(revert_index)
            self._loading = False
            self._update_audio_reset_button()
            return
        self._current_audio_provider = provider
        provider_key = provider.lower()
        if provider_key in AUDIO_PROVIDER_DEFAULTS:
            self._apply_audio_provider_defaults(force=True)
            defaults = AUDIO_PROVIDER_DEFAULTS[provider_key]
            voice_default = defaults.get("voice")
            if voice_default is not None:
                self.audio_voice_input.setText(voice_default)
            format_default = defaults.get("format")
            if format_default is not None:
                self.audio_format_input.setText(format_default)
        self._load_audio_api_key_for_current_provider()
        self._update_audio_reset_button()
        self._mark_dirty()

    def _update_text_provider_state(self) -> None:
        combo = self.text_section.provider_combo
        self._current_text_provider = (
            str(combo.currentData() or "") if combo is not None else ""
        )
        self._update_text_reset_button()

    def _update_image_provider_state(self) -> None:
        combo = self.image_section.provider_combo
        self._current_image_provider = (
            str(combo.currentData() or "") if combo is not None else ""
        )
        self._update_image_reset_button()

    def _update_audio_provider_state(self) -> None:
        combo = self.audio_section.provider_combo
        self._current_audio_provider = (
            str(combo.currentData() or "") if combo is not None else ""
        )
        self._update_audio_reset_button()

    def _on_text_api_key_changed(self, value: str) -> None:
        if self.text_section.provider_combo is None:
            return
        provider = str(self.text_section.provider_combo.currentData() or "")
        self._text_api_keys[provider] = value.strip()
        self._on_form_modified()

    def _on_image_api_key_changed(self, value: str) -> None:
        if self.image_section.provider_combo is None:
            return
        provider = str(self.image_section.provider_combo.currentData() or "")
        self._image_api_keys[provider] = value.strip()
        self._on_form_modified()

    def _on_audio_api_key_changed(self, value: str) -> None:
        if self.audio_section.provider_combo is None:
            return
        provider = str(self.audio_section.provider_combo.currentData() or "")
        self._audio_api_keys[provider] = value.strip()
        self._on_form_modified()

    @staticmethod
    def _set_line_edit_text(line_edit: QLineEdit, value: str) -> None:
        if line_edit.text() == value:
            return
        blocked = line_edit.blockSignals(True)
        line_edit.setText(value)
        line_edit.blockSignals(blocked)

    # Actions ----------------------------------------------------------

    def _on_new(self) -> None:
        if self._has_unsaved_changes() and not self._confirm_discard_changes("创建新配置"):
            return
        unique_name = self.store.ensure_unique_name("Config")
        new_config = LLMConfig(name=unique_name)
        self.store.upsert(new_config)
        self._load_configs()
        self._select_by_name(unique_name)

    def _on_delete(self) -> None:
        if not self._current_name:
            return
        if self._has_unsaved_changes() and not self._confirm_discard_changes("删除配置"):
            return
        confirm = QMessageBox.question(
            self,
            "Delete configuration",
            f"Delete '{self._current_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.store.delete(self._current_name)
        self._load_configs()

    def _on_save(self) -> None:
        config = self._collect_form()
        if config is None:
            return
        if self._current_name and self._current_name != config.name:
            self.store.delete(self._current_name)
        self.store.upsert(config)
        self._load_configs()
        self._select_by_name(config.name)
        self._reset_dirty_state()

    def _open_config_file(self) -> None:
        target_path = self.store.config_path
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_path)))

    def _select_by_name(self, name: str) -> None:
        for row in range(self.config_list.count()):
            item = self.config_list.item(row)
            if item.text() == name:
                self.config_list.setCurrentRow(row)
                break

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._has_unsaved_changes() and not self._confirm_discard_changes("关闭配置管理窗口"):
            event.ignore()
            return
        super().closeEvent(event)

    # Mapping helpers --------------------------------------------------

    @staticmethod
    def _decode_mapping_strings(entries: Iterable[str]) -> list[tuple[str, str, bool]]:
        decoded: list[tuple[str, str, bool]] = []
        for mapping in entries or []:
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

    @staticmethod
    def _encode_mapping_entries(entries: Iterable[tuple[str, str, bool]]) -> list[str]:
        encoded: list[str] = []
        for left, right, enabled in entries:
            if not left or not right:
                continue
            flag = "1" if enabled else "0"
            encoded.append(f"{left}{IMAGE_MAPPING_SEPARATOR}{right}::{flag}")
        return encoded

    # Misc -------------------------------------------------------------

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
