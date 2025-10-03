"""OpenAI text-to-speech client."""

from typing import Optional

import requests

from .exceptions import ErrorCode, ExternalException
from .speech_client import SpeechClient
from .speech_config import SpeechConfig


class OpenAISpeechClient(SpeechClient):
    """Generate speech using OpenAI's text-to-speech endpoint."""

    DEFAULT_ENDPOINT = "https://api.openai.com/v1/audio/speech"
    DEFAULT_MODEL = "gpt-4o-mini-tts"
    DEFAULT_VOICE = "alloy"
    TIMEOUT_SECONDS = 60

    def __init__(self, config: SpeechConfig):
        self._config = config
        self._last_format: Optional[str] = None

    def generate_speech(
        self,
        text: str,
        *,
        model=None,
        voice=None,
        audio_format=None,
    ) -> bytes:
        if not text.strip():
            raise ExternalException(
                "Cannot synthesize empty text.", code=ErrorCode.INVALID_INPUT
            )
        if not self._config.api_key:
            raise ExternalException(
                "Set the speech API key before generating audio.",
                code=ErrorCode.MISSING_CREDENTIALS,
            )
        resolved_model = (model or self._config.model or self.DEFAULT_MODEL).strip()
        resolved_voice = (voice or self._config.voice or self.DEFAULT_VOICE).strip()
        resolved_format = (audio_format or self._config.audio_format or "mp3").strip().lower()
        self._last_format = resolved_format or "mp3"
        endpoint = self._config.endpoint or self.DEFAULT_ENDPOINT
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": resolved_model,
            "input": text,
            "voice": resolved_voice,
            "format": resolved_format or "mp3",
        }
        try:
            response = requests.post(
                endpoint, headers=headers, json=payload, timeout=self.TIMEOUT_SECONDS
            )
        except requests.exceptions.ConnectionError as exc:
            raise ExternalException(
                "ConnectionError, could not access the OpenAI speech service.",
                code=ErrorCode.CONNECTION,
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise ExternalException(
                "Timed out while waiting for the speech response.",
                code=ErrorCode.CONNECTION,
            ) from exc
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            if response.status_code == 401:
                raise ExternalException(
                    'Received an "Unauthorized" response; your speech API key is probably invalid.',
                    code=ErrorCode.UNAUTHORIZED,
                ) from exc
            if response.status_code == 429:
                raise ExternalException(
                    'Received a "429 Too Many Requests" response from the speech endpoint.',
                    code=ErrorCode.RATE_LIMIT,
                ) from exc
            if response.status_code == 400:
                raise ExternalException(
                    'Request rejected by speech endpoint. Adjust the model, voice, or input text.',
                    code=ErrorCode.BAD_REQUEST,
                ) from exc
            raise ExternalException(
                f"Speech request failed: {response.status_code} {response.reason}\n{response.text}",
                code=ErrorCode.GENERIC,
            ) from exc
        if not response.content:
            raise ExternalException(
                "Speech provider returned no audio data.",
                code=ErrorCode.AUDIO_MISSING_DATA,
            )
        return response.content

    def get_last_audio_format(self) -> Optional[str]:
        return self._last_format
