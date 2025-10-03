"""Configuration helpers for speech synthesis."""

from dataclasses import dataclass
from typing import Optional

try:
    from aqt.qt import QSettings
except ImportError:  # pragma: no cover - fallback for tests outside Anki
    from .settings import QSettings  # type: ignore

from .settings import SettingsNames


@dataclass
class SpeechConfig:
    """User-configurable options for speech generation."""

    api_key: str
    endpoint: Optional[str]
    model: Optional[str]
    voice: Optional[str]
    audio_format: str

    @classmethod
    def from_settings(cls, settings: QSettings) -> "SpeechConfig":
        override_key = settings.value(
            SettingsNames.AUDIO_API_KEY_SETTING_NAME, defaultValue="", type=str
        )
        api_key = (override_key or "").strip()
        endpoint = settings.value(
            SettingsNames.AUDIO_ENDPOINT_SETTING_NAME, defaultValue="", type=str
        )
        model = settings.value(
            SettingsNames.AUDIO_MODEL_SETTING_NAME, defaultValue="", type=str
        )
        voice = settings.value(
            SettingsNames.AUDIO_VOICE_SETTING_NAME, defaultValue="", type=str
        )
        audio_format = settings.value(
            SettingsNames.AUDIO_FORMAT_SETTING_NAME, defaultValue="wav", type=str
        )
        return cls(
            api_key=api_key,
            endpoint=endpoint.strip() or None,
            model=model.strip() or None,
            voice=voice.strip() or None,
            audio_format=(audio_format or "wav").strip() or "wav",
        )

    def has_credentials(self) -> bool:
        return bool(self.api_key)
