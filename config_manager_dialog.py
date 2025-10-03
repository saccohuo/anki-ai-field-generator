from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices, QFont
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
    QSizePolicy,
    QScrollArea,
    QGroupBox,
)

from .config_store import ConfigStore, LLMConfig
from .gemini_client import GeminiClient
from .user_base_dialog import IMAGE_MAPPING_SEPARATOR



class ToggleMappingEditor(QWidget):
    """Editable list of mappings with enable checkboxes and summary text."""

    rowsChanged = pyqtSignal()

    def __init__(
        self,
        entries: list[tuple[str, str, bool]] | None = None,
        left_placeholder: str = "",
        right_placeholder: str = "",
    ) -> None:
        super().__init__()
        self._left_placeholder = left_placeholder
        self._right_placeholder = right_placeholder
        self._rows: list[dict[str, object]] = []
        self._global_enabled = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        controls = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(lambda: self._set_all(True))
        controls.addWidget(select_all)
        select_none = QPushButton("Select None")
        select_none.clicked.connect(lambda: self._set_all(False))
        controls.addWidget(select_none)
        invert = QPushButton("Invert")
        invert.clicked.connect(self._invert_all)
        controls.addWidget(invert)
        controls.addStretch()
        self._control_buttons = [select_all, select_none, invert]
        layout.addLayout(controls)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._rows_layout)

        self._add_button = QPushButton("Add Row")
        self._add_button.clicked.connect(lambda: self.add_row())
        layout.addWidget(self._add_button)

        self.set_entries(entries or [])

    def set_entries(self, entries: list[tuple[str, str, bool]]) -> None:
        self._clear_rows()
        if entries:
            for left, right, enabled in entries:
                self.add_row(left, right, enabled)
        else:
            self._update_summary()

    def add_row(
        self,
        left_value: str = "",
        right_value: str = "",
        enabled: bool = True,
    ) -> None:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.stateChanged.connect(self._on_row_changed)
        row_layout.addWidget(checkbox)

        left_edit = QLineEdit()
        left_edit.setPlaceholderText(self._left_placeholder)
        left_edit.setText(left_value)
        left_edit.setMinimumWidth(140)
        left_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        left_edit.textChanged.connect(self._on_row_changed)
        row_layout.addWidget(left_edit)

        arrow = QLabel("→")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(16)
        row_layout.addWidget(arrow)

        right_edit = QLineEdit()
        right_edit.setPlaceholderText(self._right_placeholder)
        right_edit.setText(right_value)
        right_edit.setMinimumWidth(140)
        right_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        right_edit.textChanged.connect(self._on_row_changed)
        row_layout.addWidget(right_edit)

        row_layout.addStretch(1)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(lambda: self._remove_row(row_widget))
        row_layout.addWidget(remove_button)

        self._rows_layout.addWidget(row_widget)
        self._rows.append(
            {
                "widget": row_widget,
                "checkbox": checkbox,
                "left": left_edit,
                "right": right_edit,
            }
        )
        row_widget.setEnabled(self._global_enabled)
        self._update_summary()

    def get_entries(self) -> list[tuple[str, str, bool]]:
        entries: list[tuple[str, str, bool]] = []
        for row in self._rows:
            left_edit: QLineEdit = row["left"]  # type: ignore[assignment]
            right_edit: QLineEdit = row["right"]  # type: ignore[assignment]
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            left = left_edit.text().strip()
            right = right_edit.text().strip()
            if not left and not right:
                continue
            entries.append((left, right, checkbox.isChecked()))
        return entries

    def set_global_enabled(self, enabled: bool) -> None:
        self._global_enabled = enabled
        for row in self._rows:
            widget: QWidget = row["widget"]  # type: ignore[assignment]
            widget.setEnabled(enabled)
        for button in getattr(self, '_control_buttons', []):
            button.setEnabled(enabled)
        self._add_button.setEnabled(enabled)
        self._update_summary()

    def _set_all(self, value: bool) -> None:
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(value)
        self._update_summary()

    def _invert_all(self) -> None:
        for row in self._rows:
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            checkbox.setChecked(not checkbox.isChecked())
        self._update_summary()

    def _remove_row(self, widget: QWidget) -> None:
        for index, row in enumerate(self._rows):
            if row["widget"] is widget:
                self._rows.pop(index)
                break
        self._rows_layout.removeWidget(widget)
        widget.deleteLater()
        self._update_summary()

    def _clear_rows(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()

    def _on_row_changed(self) -> None:
        self._update_summary()

    def _update_summary(self) -> None:
        entries = []
        unchecked = []
        incomplete = []
        for row in self._rows:
            left_edit: QLineEdit = row["left"]  # type: ignore[assignment]
            right_edit: QLineEdit = row["right"]  # type: ignore[assignment]
            checkbox: QCheckBox = row["checkbox"]  # type: ignore[assignment]
            left = left_edit.text().strip()
            right = right_edit.text().strip()
            if not left and not right:
                continue
            if left and right:
                entries.append((left, right, checkbox.isChecked()))
                if not checkbox.isChecked():
                    unchecked.append(f"{left} -> {right}")
            else:
                incomplete.append(left or right)

        if not entries and not incomplete:
            summary = "No mappings configured."
        else:
            if entries:
                total = len(entries)
                checked = [f"{left} -> {right}" for left, right, enabled in entries if enabled]
                if self._global_enabled:
                    enabled_count = len(checked)
                    enabled_text = ", ".join(checked) if checked else "none"
                    summary = f"Enabled ({enabled_count}/{total}): {enabled_text}"
                    if unchecked:
                        summary = f"{summary} (disabled: {', '.join(unchecked)})"
                else:
                    configured = ", ".join(f"{left} -> {right}" for left, right, _ in entries)
                    summary = (
                        f"Generation disabled (configured: {configured})"
                        if configured
                        else "Generation disabled."
                    )
            else:
                summary = "Incomplete mappings present."
            if incomplete:
                summary = f"{summary} (incomplete: {', '.join(incomplete)})"

        self._summary_label.setText(summary)
        self.rowsChanged.emit()

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

        form_container = QVBoxLayout()

        form_widget = QWidget()
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form_widget.setLayout(form_layout)

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

        self.text_generation_checkbox = QCheckBox("Enable text generation")
        self.text_generation_checkbox.setChecked(True)
        self.text_mapping_editor = ToggleMappingEditor(
            [],
            left_placeholder="response key",
            right_placeholder="destination field",
        )

        retry_group = QGroupBox()
        retry_layout = QVBoxLayout(retry_group)
        retry_layout.setContentsMargins(12, 8, 12, 8)
        retry_layout.setSpacing(8)
        retry_title = QLabel("Retry strategy")
        retry_font = QFont(retry_title.font())
        retry_font.setPointSize(retry_font.pointSize() + 2)
        retry_font.setBold(True)
        retry_title.setFont(retry_font)
        retry_header = QHBoxLayout()
        retry_header.addWidget(retry_title)
        retry_header.addStretch()
        retry_layout.addLayout(retry_header)
        retry_form = QFormLayout()
        retry_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.retry_limit_input = QLineEdit()
        self.retry_limit_input.setPlaceholderText("Retry attempts (default 50)")
        retry_form.addRow(QLabel("Retry Attempts:"), self.retry_limit_input)
        self.retry_delay_input = QLineEdit()
        self.retry_delay_input.setPlaceholderText("Retry delay seconds (default 5)")
        retry_form.addRow(QLabel("Retry Delay (s):"), self.retry_delay_input)
        retry_layout.addLayout(retry_form)
        form_layout.addRow(retry_group)

        text_group = QGroupBox()
        text_layout = QVBoxLayout(text_group)
        text_layout.setContentsMargins(12, 8, 12, 8)
        text_layout.setSpacing(8)
        text_title = QLabel("Text generation")
        text_title_font = QFont(text_title.font())
        text_title_font.setPointSize(text_title_font.pointSize() + 2)
        text_title_font.setBold(True)
        text_title.setFont(text_title_font)
        text_title_row = QHBoxLayout()
        text_title_row.addWidget(text_title)
        text_title_row.addStretch()
        text_layout.addLayout(text_title_row)
        toggle_row = QHBoxLayout()
        toggle_row.addWidget(self.text_generation_checkbox)
        toggle_row.addStretch()
        text_layout.addLayout(toggle_row)
        text_help = QLabel("Map model response keys to the target fields that should receive text updates.")
        text_help.setWordWrap(True)
        text_layout.addWidget(text_help)
        text_layout.addWidget(self.text_mapping_editor)

        form_layout.addRow(text_group)

        self.image_generation_checkbox = QCheckBox("Enable image generation")
        self.image_generation_checkbox.setChecked(True)
        self.image_mapping_editor = ToggleMappingEditor(
            [],
            left_placeholder="prompt field",
            right_placeholder="image field",
        )
        self.image_api_key_input = QLineEdit()
        self.image_api_key_input.setPlaceholderText("Override image API key")
        default_endpoint = "https://generativelanguage.googleapis.com/v1beta/models"
        self.image_endpoint_input = QLineEdit()
        self.image_endpoint_input.setPlaceholderText(f"Custom image endpoint (default {default_endpoint})")
        self.image_model_input = QLineEdit()
        self.image_model_input.setPlaceholderText(f"Image model name (default {GeminiClient.IMAGE_MODEL})")

        image_group = QGroupBox()
        image_layout = QVBoxLayout(image_group)
        image_title_label = QLabel("Image generation")
        image_title_font = QFont(image_title_label.font())
        image_title_font.setPointSize(image_title_font.pointSize() + 2)
        image_title_font.setBold(True)
        image_title_label.setFont(image_title_font)
        image_title_row = QHBoxLayout()
        image_title_row.addWidget(image_title_label)
        image_title_row.addStretch()
        image_layout.addLayout(image_title_row)
        image_layout.setContentsMargins(12, 8, 12, 8)
        image_layout.setSpacing(8)
        image_layout.addWidget(self.image_generation_checkbox)
        image_help = QLabel("Enable when LLM output should trigger image synthesis. Map prompt fields to the image fields that will store results.")
        image_help.setWordWrap(True)
        image_layout.addWidget(image_help)
        image_layout.addWidget(self.image_mapping_editor)
        image_form = QFormLayout()
        image_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        image_form.addRow(QLabel("Image API Key:"), self.image_api_key_input)
        image_form.addRow(QLabel("Image Endpoint:"), self.image_endpoint_input)
        image_form.addRow(QLabel("Image Model:"), self.image_model_input)
        image_layout.addLayout(image_form)
        form_layout.addRow(image_group)

        self.audio_generation_checkbox = QCheckBox("Enable speech generation")
        self.audio_generation_checkbox.setChecked(True)
        self.audio_mapping_editor = ToggleMappingEditor(
            [],
            left_placeholder="text field",
            right_placeholder="audio field",
        )
        self.audio_api_key_input = QLineEdit()
        self.audio_api_key_input.setPlaceholderText("Speech API key (required for audio generation)")
        self.audio_endpoint_input = QLineEdit()
        self.audio_endpoint_input.setPlaceholderText("Custom speech endpoint (optional)")
        self.audio_model_input = QLineEdit()
        self.audio_model_input.setPlaceholderText("Speech model name (e.g. gpt-4o-mini-tts)")
        self.audio_voice_input = QLineEdit()
        self.audio_voice_input.setPlaceholderText("Preferred voice (e.g. alloy)")
        self.audio_format_input = QLineEdit()
        self.audio_format_input.setPlaceholderText("Audio format (wav or pcm)")
        self.audio_format_input.setText("wav")

        audio_group = QGroupBox()
        audio_layout = QVBoxLayout(audio_group)
        audio_title_label = QLabel("Speech generation")
        audio_title_font = QFont(audio_title_label.font())
        audio_title_font.setPointSize(audio_title_font.pointSize() + 2)
        audio_title_font.setBold(True)
        audio_title_label.setFont(audio_title_font)
        audio_title_row = QHBoxLayout()
        audio_title_row.addWidget(audio_title_label)
        audio_title_row.addStretch()
        audio_layout.addLayout(audio_title_row)
        audio_layout.setContentsMargins(12, 8, 12, 8)
        audio_layout.setSpacing(8)
        audio_layout.addWidget(self.audio_generation_checkbox)
        audio_help = QLabel("Enable when text-to-speech output should be generated. Map source text fields to the destination fields that store [sound:] tags.")
        audio_help.setWordWrap(True)
        audio_layout.addWidget(audio_help)
        audio_layout.addWidget(self.audio_mapping_editor)
        audio_form = QFormLayout()
        audio_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        audio_form.addRow(QLabel("Speech API Key:"), self.audio_api_key_input)
        audio_form.addRow(QLabel("Speech Endpoint:"), self.audio_endpoint_input)
        audio_form.addRow(QLabel("Speech Model:"), self.audio_model_input)
        audio_form.addRow(QLabel("Speech Voice:"), self.audio_voice_input)
        audio_form.addRow(QLabel("Speech Format:"), self.audio_format_input)
        audio_layout.addLayout(audio_form)
        form_layout.addRow(audio_group)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidget(form_widget)
        form_container.addWidget(scroll_area)

        save_button_row = QHBoxLayout()
        self.open_config_button = QPushButton("Open config file")
        self.open_config_button.clicked.connect(self._open_config_file)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._on_save)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        save_button_row.addWidget(self.open_config_button)
        save_button_row.addStretch()
        save_button_row.addWidget(self.save_button)
        save_button_row.addWidget(self.close_button)
        form_container.addLayout(save_button_row)

        main_layout.addLayout(list_container, 1)
        main_layout.addLayout(form_container, 2)

        self.text_generation_checkbox.stateChanged.connect(
            lambda state: self.text_mapping_editor.set_global_enabled(
                Qt.CheckState(state) == Qt.CheckState.Checked
            )
        )
        self.image_generation_checkbox.stateChanged.connect(
            lambda state: self.image_mapping_editor.set_global_enabled(
                Qt.CheckState(state) == Qt.CheckState.Checked
            )
        )
        self.audio_generation_checkbox.stateChanged.connect(
            lambda state: self.audio_mapping_editor.set_global_enabled(
                Qt.CheckState(state) == Qt.CheckState.Checked
            )
        )

        self.text_mapping_editor.set_global_enabled(self.text_generation_checkbox.isChecked())
        self.image_mapping_editor.set_global_enabled(self.image_generation_checkbox.isChecked())
        self.audio_mapping_editor.set_global_enabled(self.audio_generation_checkbox.isChecked())

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

        self.text_generation_checkbox.setChecked(config.enable_text_generation)
        text_entries: list[tuple[str, str, bool]] = []
        if config.text_mapping_entries:
            for entry in config.text_mapping_entries:
                if not isinstance(entry, dict):
                    continue
                key = str(entry.get("key", ""))
                field = str(entry.get("field", ""))
                enabled = bool(entry.get("enabled", True))
                text_entries.append((key, field, enabled))
        elif config.response_keys and config.destination_fields:
            for key, field in zip(config.response_keys, config.destination_fields):
                text_entries.append((key, field, True))
        self.text_mapping_editor.set_entries(text_entries)

        self.retry_limit_input.setText(str(config.retry_limit or 50))
        self.retry_delay_input.setText(str(config.retry_delay or 5))

        self.image_generation_checkbox.setChecked(config.enable_image_generation)
        image_entries = self._decode_mapping_strings(config.image_prompt_mappings)
        self.image_mapping_editor.set_entries(image_entries)
        self.image_api_key_input.setText(config.image_api_key)
        self.image_endpoint_input.setText(config.image_endpoint)
        self.image_model_input.setText(config.image_model)

        self.audio_generation_checkbox.setChecked(config.enable_audio_generation)
        audio_entries = self._decode_mapping_strings(config.audio_prompt_mappings)
        self.audio_mapping_editor.set_entries(audio_entries)
        self.audio_api_key_input.setText(config.audio_api_key)
        self.audio_endpoint_input.setText(config.audio_endpoint)
        self.audio_model_input.setText(config.audio_model)
        self.audio_voice_input.setText(config.audio_voice)
        self.audio_format_input.setText(config.audio_format or "wav")

        self.text_mapping_editor.set_global_enabled(self.text_generation_checkbox.isChecked())
        self.image_mapping_editor.set_global_enabled(self.image_generation_checkbox.isChecked())
        self.audio_mapping_editor.set_global_enabled(self.audio_generation_checkbox.isChecked())


    def _clear_form(self) -> None:
        self.name_input.clear()
        self.endpoint_input.clear()
        self.api_key_input.clear()
        self.model_input.clear()
        self.system_prompt_input.clear()
        self.user_prompt_input.clear()

        self.text_generation_checkbox.setChecked(True)
        self.text_mapping_editor.set_entries([])
        self.text_mapping_editor.set_global_enabled(True)

        self.retry_limit_input.setText("50")
        self.retry_delay_input.setText("5")

        self.image_generation_checkbox.setChecked(True)
        self.image_mapping_editor.set_entries([])
        self.image_mapping_editor.set_global_enabled(True)
        self.image_api_key_input.clear()
        self.image_endpoint_input.clear()
        self.image_model_input.clear()

        self.audio_generation_checkbox.setChecked(True)
        self.audio_mapping_editor.set_entries([])
        self.audio_mapping_editor.set_global_enabled(True)
        self.audio_api_key_input.clear()
        self.audio_endpoint_input.clear()
        self.audio_model_input.clear()
        self.audio_voice_input.clear()
        self.audio_format_input.setText("wav")



    def _open_config_file(self) -> None:
        target = self.store.config_path
        if not target.exists():
            try:
                self.store.save()
            except OSError as exc:
                QMessageBox.warning(
                    self,
                    "Unable to Open",
                    f"Could not create config file:\n{exc}",
                )
                return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
            QMessageBox.warning(
                self,
                "Unable to Open",
                "Could not open the configuration file with the default application.",
            )

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

        text_rows = self.text_mapping_editor.get_entries()
        response_keys: list[str] = []
        destination_fields: list[str] = []
        text_mapping_entries = []
        for key, field, enabled in text_rows:
            text_mapping_entries.append({
                "key": key,
                "field": field,
                "enabled": enabled,
            })
            if enabled and key and field:
                response_keys.append(key)
                destination_fields.append(field)

        image_rows = self.image_mapping_editor.get_entries()
        image_mappings = self._encode_mapping_entries(image_rows)

        audio_rows = self.audio_mapping_editor.get_entries()
        audio_mappings = self._encode_mapping_entries(audio_rows)

        retry_limit = 0
        try:
            retry_limit = int(self.retry_limit_input.text().strip() or 0)
        except ValueError:
            retry_limit = 0
        retry_delay = 0.0
        try:
            retry_delay = float(self.retry_delay_input.text().strip() or 0)
        except ValueError:
            retry_delay = 0.0
        retry_limit = retry_limit or 50
        retry_delay = retry_delay or 5.0

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
            image_api_key=self.image_api_key_input.text().strip(),
            image_endpoint=self.image_endpoint_input.text().strip(),
            image_model=self.image_model_input.text().strip(),
            audio_prompt_mappings=audio_mappings,
            audio_api_key=self.audio_api_key_input.text().strip(),
            audio_endpoint=self.audio_endpoint_input.text().strip(),
            audio_model=self.audio_model_input.text().strip(),
            audio_voice=self.audio_voice_input.text().strip(),
            audio_format=self.audio_format_input.text().strip() or "wav",
            text_mapping_entries=text_mapping_entries,
            enable_text_generation=self.text_generation_checkbox.isChecked(),
            enable_image_generation=self.image_generation_checkbox.isChecked(),
            enable_audio_generation=self.audio_generation_checkbox.isChecked(),
            retry_limit=retry_limit,
            retry_delay=retry_delay,
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
    def _decode_mapping_strings(entries: list[str]) -> list[tuple[str, str, bool]]:
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
    def _encode_mapping_entries(entries: list[tuple[str, str, bool]]) -> list[str]:
        encoded: list[str] = []
        for left, right, enabled in entries:
            if not left or not right:
                continue
            flag = "1" if enabled else "0"
            encoded.append(f"{left}{IMAGE_MAPPING_SEPARATOR}{right}::{flag}")
        return encoded

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
