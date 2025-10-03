"""
Factory that returns the corrent LLM Client configurations.
"""

import json
from typing import Optional

from .claude_client import ClaudeClient
from .claude_dialog import ClaudeDialog
from .config_store import ConfigStore
from .custom_client import CustomLLMClient
from .custom_dialog import CustomDialog
from .deepseek_client import DeepseekClient
from .deepseek_dialog import DeepSeekDialog
from .gemini_client import GeminiClient
from .gemini_dialog import GeminiDialog
from .llm_client import LLMClient
from .main_window import MainWindow
from .note_processor import NoteProcessor
from .openai_client import OpenAIClient
from .openai_dialog import OpenAIDialog
from .prompt_config import PromptConfig
from .progress_bar import ProgressDialog
from .settings import SettingsNames, get_settings, set_new_settings_group
from .speech_client import SpeechClient
from .speech_config import SpeechConfig
from .openai_speech_client import OpenAISpeechClient
from .gemini_speech_client import GeminiSpeechClient
from .user_base_dialog import UserBaseDialog


class ClientFactory:
    """
    Factory that returns the corrent LLM Client configurations.
    """

    valid_clients = ["Claude", "OpenAI", "DeepSeek", "Gemini", "Custom"]

    def __init__(self, browser):
        self.app_settings, self.client_name = get_settings()
        self.browser = browser
        self.notes = [
            browser.mw.col.get_note(note_id) for note_id in browser.selectedNotes()
        ]

    def update_client(self, client_name: str):
        assert (
            client_name in ClientFactory.valid_clients
        ), f"{client_name} is not implemented as a LLM Client."
        self.client_name = client_name
        set_new_settings_group(self.app_settings, self.client_name)

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

    def get_speech_client(self) -> Optional[SpeechClient]:
        """Return a speech client when speech generation is configured."""
        if not self._get_bool_setting(
            SettingsNames.ENABLE_AUDIO_GENERATION_SETTING_NAME, True
        ):
            return None
        audio_mappings = self.app_settings.value(
            SettingsNames.AUDIO_MAPPING_SETTING_NAME, type="QStringList"
        ) or []
        if not any(self._mapping_entry_enabled(entry) for entry in audio_mappings):
            return None
        speech_config = SpeechConfig.from_settings(self.app_settings)
        if not speech_config.has_credentials():
            return None
        endpoint_hint = (speech_config.endpoint or "").lower()
        model_hint = (speech_config.model or "").lower()
        if (
            "generativelanguage" in endpoint_hint
            or "googleapis" in endpoint_hint
            or model_hint.startswith("gemini")
        ):
            return GeminiSpeechClient(speech_config)
        if (
            "openai" in endpoint_hint
            or model_hint.startswith("gpt")
            or model_hint.startswith("o1")
            or not endpoint_hint
        ):
            return OpenAISpeechClient(speech_config)
        return None

    def get_client(self) -> LLMClient:
        """
        Factory method that returns the LLM Client implementation.
        Add an implementation for each Client you add.
        """
        prompt_config = PromptConfig(self.app_settings)
        if self.client_name == "OpenAI":
            llm_client = OpenAIClient(prompt_config)
            return llm_client
        if self.client_name == "DeepSeek":
            llm_client = DeepseekClient(prompt_config)
            return llm_client
        if self.client_name == "Claude":
            llm_client = ClaudeClient(prompt_config)
            return llm_client
        if self.client_name == "Gemini":
            llm_client = GeminiClient(prompt_config)
            return llm_client
        if self.client_name == "Custom":
            store = ConfigStore()
            config_name = prompt_config.config_name or self.app_settings.value(
                SettingsNames.CONFIG_NAME_SETTING_NAME,
                defaultValue="",
                type=str,
            )
            config = None
            if config_name:
                config = store.find(config_name)
            if config is None:
                configs = store.list_configs()
                config = configs[0] if configs else None
            if config:
                self.app_settings.setValue(
                    SettingsNames.CONFIG_NAME_SETTING_NAME, config.name
                )
                self.app_settings.setValue(
                    SettingsNames.API_KEY_SETTING_NAME, config.api_key
                )
                self.app_settings.setValue(
                    SettingsNames.MODEL_SETTING_NAME, config.model
                )
                self.app_settings.setValue(
                    SettingsNames.ENDPOINT_SETTING_NAME, config.endpoint
                )
                self.app_settings.setValue(
                    SettingsNames.SYSTEM_PROMPT_SETTING_NAME, config.system_prompt
                )
                self.app_settings.setValue(
                    SettingsNames.USER_PROMPT_SETTING_NAME, config.user_prompt
                )
                self.app_settings.setValue(
                    SettingsNames.RESPONSE_KEYS_SETTING_NAME, config.response_keys
                )
                self.app_settings.setValue(
                    SettingsNames.DESTINATION_FIELD_SETTING_NAME,
                    config.destination_fields,
                )
                self.app_settings.setValue(
                    SettingsNames.IMAGE_MAPPING_SETTING_NAME, config.image_prompt_mappings
                )
                self.app_settings.setValue(
                    SettingsNames.IMAGE_API_KEY_SETTING_NAME, config.image_api_key
                )
                self.app_settings.setValue(
                    SettingsNames.IMAGE_ENDPOINT_SETTING_NAME, config.image_endpoint
                )
                self.app_settings.setValue(
                    SettingsNames.IMAGE_MODEL_SETTING_NAME, config.image_model
                )
                self.app_settings.setValue(
                    SettingsNames.AUDIO_MAPPING_SETTING_NAME, config.audio_prompt_mappings
                )
                self.app_settings.setValue(
                    SettingsNames.AUDIO_API_KEY_SETTING_NAME, config.audio_api_key
                )
                self.app_settings.setValue(
                    SettingsNames.AUDIO_ENDPOINT_SETTING_NAME, config.audio_endpoint
                )
                self.app_settings.setValue(
                    SettingsNames.AUDIO_MODEL_SETTING_NAME, config.audio_model
                )
                self.app_settings.setValue(
                    SettingsNames.AUDIO_VOICE_SETTING_NAME, config.audio_voice
                )
                self.app_settings.setValue(
                    SettingsNames.AUDIO_FORMAT_SETTING_NAME, config.audio_format or "wav"
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
                prompt_config.refresh()
            llm_client = CustomLLMClient(prompt_config)
            return llm_client
        raise NotImplementedError(f"No LLM client implemented for {self.client_name}")

    def get_dialog(self) -> UserBaseDialog:
        """
        Factory method that returns the settings dialog for the user for each LLM.
        Client. Add an implementation for each Client you add.
        """
        if self.client_name == "OpenAI":
            return OpenAIDialog(self.app_settings, self.notes)
        if self.client_name == "DeepSeek":
            return DeepSeekDialog(self.app_settings, self.notes)
        if self.client_name == "Claude":
            return ClaudeDialog(self.app_settings, self.notes)
        if self.client_name == "Gemini":
            return GeminiDialog(self.app_settings, self.notes)
        if self.client_name == "Custom":
            return CustomDialog(self.app_settings, self.notes)
        raise NotImplementedError(
            f"No user settings dialog implemented for {self.client_name}"
        )

    def show(self):
        """
        Displays the user settings UI.
        """
        # self.get_dialog(self.client_name).show(notes)
        self.mw = MainWindow(
            self, lambda: self.on_submit(browser=self.browser, notes=self.notes)
        )
        self.mw.show()

    def on_submit(self, browser, notes):
        """
        Called once the user confirms the card modifications.
        This also refreshes the settings and the LLM client, as the user may have
        changed them.
        """
        generate_text = self._get_bool_setting(
            SettingsNames.ENABLE_TEXT_GENERATION_SETTING_NAME, True
        )
        generate_images = self._get_bool_setting(
            SettingsNames.ENABLE_IMAGE_GENERATION_SETTING_NAME, True
        )
        generate_audio = self._get_bool_setting(
            SettingsNames.ENABLE_AUDIO_GENERATION_SETTING_NAME, True
        )
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
        dialog = ProgressDialog(note_processor, success_callback=self.mw.close)
        dialog.exec()
        browser.mw.reset()
