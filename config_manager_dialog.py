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
)

from .config_store import ConfigStore, LLMConfig


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

    def _clear_form(self) -> None:
        self.name_input.clear()
        self.endpoint_input.clear()
        self.api_key_input.clear()
        self.model_input.clear()
        self.system_prompt_input.clear()
        self.user_prompt_input.clear()
        self.response_keys_input.clear()
        self.destination_fields_input.clear()

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

        config = LLMConfig(
            name=name,
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_keys=response_keys,
            destination_fields=destination_fields,
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
