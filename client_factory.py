"""Factory that applies configurations and runs note updates."""

from __future__ import annotations

import json
from typing import Callable, Dict, List, Optional

from .claude_client import ClaudeClient
from .config_manager_dialog import ConfigManagerDialog
from .config_store import ConfigStore, LLMConfig
from .custom_client import CustomLLMClient
from .deepseek_client import DeepseekClient
from .gemini_client import GeminiClient
from .gemini_speech_client import GeminiSpeechClient
from .llm_client import LLMClient
from .main_window import MainWindow
from .note_processor import NoteProcessor
from .openai_client import OpenAIClient
from .openai_speech_client import OpenAISpeechClient
from .prompt_config import PromptConfig
from .progress_bar import ProgressDialog
from .settings import SettingsNames, get_settings
from .speech_client import SpeechClient
from .speech_config import SpeechConfig
from .user_base_dialog import UserBaseDialog
from PyQt6.QtWidgets import QMessageBox

_TEXT_CLIENTS: Dict[str, Callable[[PromptConfig], LLMClient]] = {
    "openai": OpenAIClient,
    "claude": ClaudeClient,
    "gemini": GeminiClient,
    "deepseek": DeepseekClient,
    "custom": CustomLLMClient,
}


class ClientFactory:
    """Coordinates configuration selection, UI, and execution."""

    def __init__(self, browser):
        self.browser = browser
        self.app_settings, _ = get_settings()
        self.store = ConfigStore()
        self.notes = [browser.mw.col.get_note(note_id) for note_id in browser.selectedNotes()]
        self._note_type_lookup = self._build_note_type_lookup()
        self.active_config = self._resolve_initial_config()
        self.window: Optional[MainWindow] = None

    # Configuration lifecycle -----------------------------------------

    def list_config_names(self) -> List[str]:
        return [config.name for config in self.store.list_configs()]

    def active_config_name(self) -> str:
        return self.active_config.name if self.active_config else ""

    def set_active_config(self, name: str) -> None:
        config = self.store.find(name)
        if config is None:
            configs = self.store.list_configs()
            if not configs:
                config = LLMConfig(name="Default")
                self.store.upsert(config)
            else:
                config = configs[0]
        self.active_config = config
        self._apply_config_to_settings(config)

    def make_runtime_panel(self) -> UserBaseDialog:
        panel = UserBaseDialog(self.app_settings, self.notes)
        allowed_ids = set(self.active_config.note_type_ids or [])
        selected_ids = {self._note_type_id(note) for note in self.notes}
        allowed_names = [self._note_type_lookup.get(note_id, note_id) for note_id in allowed_ids]
        missing_ids = sorted(selected_ids - allowed_ids) if allowed_ids else []
        missing_names = [self._note_type_lookup.get(note_id, note_id) for note_id in missing_ids]
        panel.update_note_type_status(allowed_names, missing_names)
        if missing_names:
            allowed_text = ", ".join(allowed_names) if allowed_names else "none"
            missing_text = ", ".join(missing_names)
            QMessageBox.warning(
                panel,
                "Note type mismatch",
                (
                    "Selected notes include types not covered by this configuration:\n"
                    f"{missing_text}\n\nConfigured types: {allowed_text}"
                ),
            )
        return panel

    def open_config_manager(self, parent) -> bool:
        dialog = ConfigManagerDialog(parent)
        dialog.exec()
        # Reload store to pick up changes
        self.store = ConfigStore(self.store.config_path)
        configs = self.store.list_configs()
        if not configs:
            default_config = LLMConfig(name="Default")
            self.store.upsert(default_config)
            configs = [default_config]
        name = self.active_config.name if self.active_config else ""
        refreshed = self.store.find(name) or configs[0]
        self.active_config = refreshed
        self._apply_config_to_settings(refreshed)
        return True

    def show(self):
        self.window = MainWindow(self, lambda: self.on_submit(self.browser, self.notes))
        self.window.show()

    # Submission -------------------------------------------------------

    def on_submit(self, browser, notes):
        generate_text = self._get_bool_setting(SettingsNames.ENABLE_TEXT_GENERATION_SETTING_NAME)
        generate_images = self._get_bool_setting(SettingsNames.ENABLE_IMAGE_GENERATION_SETTING_NAME)
        generate_audio = self._get_bool_setting(SettingsNames.ENABLE_AUDIO_GENERATION_SETTING_NAME)

        speech_client = self.get_speech_client() if generate_audio else None
        note_processor = NoteProcessor(
            notes,
            self.get_client(),
            self.app_settings,
            speech_client=speech_client,
            generate_text=generate_text,
            generate_images=generate_images,
            generate_audio=generate_audio,
        )
        success_callback = self.window.close if self.window else (lambda: None)
        dialog = ProgressDialog(note_processor, success_callback=success_callback)
        dialog.exec()
        browser.mw.reset()
        self.window = None

    # Client helpers ---------------------------------------------------

    def get_client(self) -> LLMClient:
        provider = (
            self.app_settings.value(SettingsNames.TEXT_PROVIDER_SETTING_NAME, type=str)
            or "custom"
        ).lower()
        prompt_config = PromptConfig(self.app_settings)
        factory = _TEXT_CLIENTS.get(provider, CustomLLMClient)
        return factory(prompt_config)

    def get_speech_client(self) -> Optional[SpeechClient]:
        audio_mappings = self.app_settings.value(
            SettingsNames.AUDIO_MAPPING_SETTING_NAME, type="QStringList"
        ) or []
        if not any(self._mapping_entry_enabled(entry) for entry in audio_mappings):
            return None
        speech_config = SpeechConfig.from_settings(self.app_settings)
        if not speech_config.has_credentials():
            return None
        provider = (
            self.app_settings.value(SettingsNames.AUDIO_PROVIDER_SETTING_NAME, type=str)
            or ""
        ).lower()
        if provider == "gemini":
            return GeminiSpeechClient(speech_config)
        if provider in {"openai", "custom", ""}:
            return OpenAISpeechClient(speech_config)
        return None

    # Internal helpers -------------------------------------------------

    def _resolve_initial_config(self) -> LLMConfig:
        saved_name = self.app_settings.value(
            SettingsNames.CONFIG_NAME_SETTING_NAME, defaultValue="", type=str
        )
        if saved_name:
            config = self.store.find(saved_name)
            if config is not None:
                self._apply_config_to_settings(config)
                return config
        configs = self.store.list_configs()
        if configs:
            config = configs[0]
        else:
            config = LLMConfig(name="Default")
            self.store.upsert(config)
        self._apply_config_to_settings(config)
        return config

    def _apply_config_to_settings(self, config: LLMConfig) -> None:
        self.app_settings.setValue(SettingsNames.CONFIG_NAME_SETTING_NAME, config.name)
        text_provider = (config.text_provider or "custom").lower()
        text_api_key = config.text_provider_api_keys.get(text_provider, config.api_key)
        self.app_settings.setValue(SettingsNames.API_KEY_SETTING_NAME, text_api_key)
        self.app_settings.setValue(SettingsNames.ENDPOINT_SETTING_NAME, config.endpoint)
        self.app_settings.setValue(SettingsNames.MODEL_SETTING_NAME, config.model)
        self.app_settings.setValue(SettingsNames.SYSTEM_PROMPT_SETTING_NAME, config.system_prompt)
        self.app_settings.setValue(SettingsNames.USER_PROMPT_SETTING_NAME, config.user_prompt)
        self.app_settings.setValue(SettingsNames.RESPONSE_KEYS_SETTING_NAME, config.response_keys)
        self.app_settings.setValue(
            SettingsNames.DESTINATION_FIELD_SETTING_NAME,
            config.destination_fields,
        )
        self.app_settings.setValue(
            SettingsNames.TEXT_MAPPING_ENTRIES_SETTING_NAME,
            json.dumps(config.text_mapping_entries or [], ensure_ascii=False),
        )
        self.app_settings.setValue(
            SettingsNames.ENABLE_TEXT_GENERATION_SETTING_NAME,
            config.enable_text_generation,
        )
        self.app_settings.setValue(
            SettingsNames.ENABLE_IMAGE_GENERATION_SETTING_NAME,
            config.enable_image_generation,
        )
        self.app_settings.setValue(
            SettingsNames.ENABLE_AUDIO_GENERATION_SETTING_NAME,
            config.enable_audio_generation,
        )
        self.app_settings.setValue(SettingsNames.RETRY_LIMIT_SETTING_NAME, config.retry_limit)
        self.app_settings.setValue(SettingsNames.RETRY_DELAY_SETTING_NAME, config.retry_delay)
        self.app_settings.setValue(SettingsNames.IMAGE_MAPPING_SETTING_NAME, config.image_prompt_mappings)
        image_provider = (config.image_provider or "custom").lower()
        image_api_key = config.image_provider_api_keys.get(image_provider, config.image_api_key)
        self.app_settings.setValue(SettingsNames.IMAGE_API_KEY_SETTING_NAME, image_api_key)
        self.app_settings.setValue(SettingsNames.IMAGE_ENDPOINT_SETTING_NAME, config.image_endpoint)
        self.app_settings.setValue(SettingsNames.IMAGE_MODEL_SETTING_NAME, config.image_model)
        self.app_settings.setValue(SettingsNames.AUDIO_MAPPING_SETTING_NAME, config.audio_prompt_mappings)
        audio_provider = (config.audio_provider or "custom").lower()
        audio_api_key = config.audio_provider_api_keys.get(audio_provider, config.audio_api_key)
        self.app_settings.setValue(SettingsNames.AUDIO_API_KEY_SETTING_NAME, audio_api_key)
        self.app_settings.setValue(SettingsNames.AUDIO_ENDPOINT_SETTING_NAME, config.audio_endpoint)
        self.app_settings.setValue(SettingsNames.AUDIO_MODEL_SETTING_NAME, config.audio_model)
        self.app_settings.setValue(SettingsNames.AUDIO_VOICE_SETTING_NAME, config.audio_voice)
        self.app_settings.setValue(SettingsNames.AUDIO_FORMAT_SETTING_NAME, config.audio_format or "wav")
        self.app_settings.setValue(SettingsNames.TEXT_PROVIDER_SETTING_NAME, config.text_provider or "custom")
        self.app_settings.setValue(
            SettingsNames.TEXT_PROVIDER_CUSTOM_VALUE_SETTING_NAME,
            config.text_custom_value or "",
        )
        self.app_settings.setValue(SettingsNames.IMAGE_PROVIDER_SETTING_NAME, config.image_provider or "custom")
        self.app_settings.setValue(SettingsNames.AUDIO_PROVIDER_SETTING_NAME, config.audio_provider or "custom")

    def _build_note_type_lookup(self) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        collection = getattr(self.browser.mw, "col", None)
        if collection and getattr(collection, "models", None):
            try:
                for model in collection.models.all():
                    model_id = str(model.get("id"))
                    lookup[model_id] = str(model.get("name", model_id))
            except Exception:
                lookup = {}
        return lookup

    def _note_type_id(self, note) -> str:
        try:
            return str(note.model()["id"])
        except Exception:
            return ""

    def _get_bool_setting(self, setting_name: str, default: bool = True) -> bool:
        value = self.app_settings.value(setting_name, defaultValue=default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes"}
        return bool(value)

    @staticmethod
    def _mapping_entry_enabled(entry: str) -> bool:
        if not isinstance(entry, str):
            return False
        if "::" in entry:
            _, flag = entry.rsplit("::", 1)
            return flag.strip().lower() not in {"0", "false"}
        return True


__all__ = ["ClientFactory"]
