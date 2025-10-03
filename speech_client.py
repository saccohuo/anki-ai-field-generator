"""Interface for speech synthesis clients."""

from abc import ABC, abstractmethod
from typing import Optional


class SpeechClient(ABC):
    """Generic interface for a speech synthesis provider."""

    @abstractmethod
    def generate_speech(
        self,
        text: str,
        *,
        model: Optional[str] = None,
        voice: Optional[str] = None,
        audio_format: Optional[str] = None,
    ) -> bytes:
        """Return audio bytes for the provided text."""

    def get_last_audio_format(self) -> Optional[str]:
        """Return the most recent audio format/extension, if known."""
        return None
