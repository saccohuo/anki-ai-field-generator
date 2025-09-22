from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QTextEdit,
)

from .config_manager_dialog import ConfigManagerDialog
from .config_store import ConfigStore, LLMConfig
from .settings import SettingsNames
from .user_base_dialog import UserBaseDialog, show_error_message


class CustomDialog(UserBaseDialog):
    """Dialog allowing users to configure a custom LLM endpoint."""

    def __init__(self, app_settings, selected_notes):
        super().__init__(app_settings, selected_notes)
        self.store = ConfigStore()
        self.config_selector: Optional[QComboBox] = None
        self.config_name_entry = None
        self._active_config_name: Optional[str] = None
        self._warned_example = False

    @property
    def service_name(self) -> str:
        return "Custom"

    @property
    def models(self) -> list[str]:
        # The model name is a free-form field for custom endpoints.
        return []

    @property
    def system_prompt_description(self) -> str:
        return (
            "Optional instructions sent as a system-level message before each query."
            " Leave blank if your endpoint does not use system prompts."
        )

    @property
    def system_prompt_placeholder(self) -> str:
        return "You are a helpful tutor..."

    @property
    def user_prompt_description(self) -> str:
        return (
            "Prompt generated per card. Use {field_name} syntax to inject Anki fields."
        )

    @property
    def user_prompt_placeholder(self) -> str:
        return "Example:\n{front}"

    def show(self):
        widget = super().show()
        self._refresh_configs()
        self._maybe_warn_example()
        return widget

    def add_models_dropdown(self, layout):
        header_row = QHBoxLayout()
        header_row.addWidget(self.ui_tools.create_label("Configuration:"))
        self.config_selector = QComboBox()
        self.config_selector.currentIndexChanged.connect(self._on_config_selected)
        self.config_selector.setMinimumWidth(220)
        header_row.addWidget(self.config_selector)
        manage_button = QPushButton("Manage...")
        manage_button.clicked.connect(self._open_manager)
        header_row.addWidget(manage_button)
        header_row.addStretch()
        layout.addLayout(header_row)

        layout.addWidget(self.ui_tools.create_label("Configuration Name:"))
        self.config_name_entry = self.ui_tools.create_text_entry(
            SettingsNames.CONFIG_NAME_SETTING_NAME,
            "My Custom Config",
        )

        layout.addWidget(self.ui_tools.create_label("Endpoint URL:"))
        layout.addWidget(
            self.ui_tools.create_text_entry(
                SettingsNames.ENDPOINT_SETTING_NAME,
                "https://api.example.com/v1/chat/completions",
            )
        )
        layout.addWidget(self.ui_tools.create_label("Model Name:"))
        layout.addWidget(
            self.ui_tools.create_text_entry(
                SettingsNames.MODEL_SETTING_NAME,
                "my-model",
            )
        )

    def are_settings_valid(self) -> bool:
        if not super().are_settings_valid():
            return False
        settings = self.ui_tools.get_settings()
        config_name = settings.get(SettingsNames.CONFIG_NAME_SETTING_NAME, "").strip()
        if not config_name:
            show_error_message("Please enter a configuration name.")
            return False
        endpoint = settings.get(SettingsNames.ENDPOINT_SETTING_NAME, "").strip()
        if not endpoint:
            show_error_message("Please enter an endpoint URL.")
            return False
        return True

    def accept(self) -> bool:
        if not super().accept():
            return False
        self._persist_current_config()
        return True

    # Helper methods ---------------------------------------------------

    def _refresh_configs(self, select_name: Optional[str] = None) -> None:
        if self.config_selector is None:
            return
        configs = self.store.list_configs()
        if not configs:
            configs = [LLMConfig(name="Default")]
        self.config_selector.blockSignals(True)
        self.config_selector.clear()
        for config in configs:
            self.config_selector.addItem(config.name)
        self.config_selector.blockSignals(False)

        desired = (
            select_name
            or self.app_settings.value(
                SettingsNames.CONFIG_NAME_SETTING_NAME, defaultValue="", type=str
            )
        )
        if desired:
            index = self.config_selector.findText(desired)
            if index != -1:
                self.config_selector.setCurrentIndex(index)
        if self.config_selector.count() > 0:
            if self.config_selector.currentIndex() < 0:
                self.config_selector.setCurrentIndex(0)
            self._apply_config(self._get_selected_config())
        self._maybe_warn_example()

    def _get_selected_config(self) -> LLMConfig:
        name = self.config_selector.currentText() if self.config_selector else ""
        config = self.store.find(name)
        if config is None:
            config = LLMConfig(name=name or "Default")
        return config

    def _apply_config(self, config: LLMConfig) -> None:
        if self.config_name_entry:
            self.config_name_entry.setText(config.name)
        self._set_setting(SettingsNames.CONFIG_NAME_SETTING_NAME, config.name)
        self._set_setting(SettingsNames.ENDPOINT_SETTING_NAME, config.endpoint)
        self._set_setting(SettingsNames.MODEL_SETTING_NAME, config.model)
        self._set_setting(SettingsNames.API_KEY_SETTING_NAME, config.api_key)
        self._set_setting(SettingsNames.SYSTEM_PROMPT_SETTING_NAME, config.system_prompt)
        self._set_setting(SettingsNames.USER_PROMPT_SETTING_NAME, config.user_prompt)
        if hasattr(self, "two_col_form") and self.two_col_form:
            self.two_col_form.set_inputs(
                config.response_keys,
                config.destination_fields,
            )
        self.app_settings.setValue(SettingsNames.CONFIG_NAME_SETTING_NAME, config.name)
        self._active_config_name = config.name

    def _set_setting(self, setting_name: str, value: str) -> None:
        widget = self.ui_tools.widgets.get(setting_name)
        if widget is None:
            return
        if isinstance(widget, QLineEdit):
            widget.setText(value or "")
        elif isinstance(widget, QTextEdit):
            widget.setPlainText(value or "")
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(value or "")

    def _persist_current_config(self) -> None:
        settings = self.ui_tools.get_settings()
        response_keys, destination_fields = self.two_col_form.get_inputs()
        config = LLMConfig(
            name=settings.get(SettingsNames.CONFIG_NAME_SETTING_NAME, "").strip(),
            endpoint=settings.get(SettingsNames.ENDPOINT_SETTING_NAME, "").strip(),
            api_key=settings.get(SettingsNames.API_KEY_SETTING_NAME, "").strip(),
            model=settings.get(SettingsNames.MODEL_SETTING_NAME, "").strip(),
            system_prompt=settings.get(SettingsNames.SYSTEM_PROMPT_SETTING_NAME, ""),
            user_prompt=settings.get(SettingsNames.USER_PROMPT_SETTING_NAME, ""),
            response_keys=response_keys,
            destination_fields=destination_fields,
        )
        if self._active_config_name and self._active_config_name != config.name:
            self.store.delete(self._active_config_name)
        self.store.upsert(config)
        self.app_settings.setValue(SettingsNames.CONFIG_NAME_SETTING_NAME, config.name)
        self._refresh_configs(select_name=config.name)

    def _on_config_selected(self, index: int) -> None:
        config = self._get_selected_config()
        self._apply_config(config)
        self._maybe_warn_example()

    def _open_manager(self) -> None:
        dialog = ConfigManagerDialog(self)
        dialog.exec()
        self.store.load()
        self._refresh_configs()
        self._warned_example = False
        self._maybe_warn_example(force=True)

    def _maybe_warn_example(self, force: bool = False) -> None:
        if self._warned_example and not force:
            return
        ConfigManagerDialog.prompt_save_if_example(self.store, self)
        self._warned_example = True
