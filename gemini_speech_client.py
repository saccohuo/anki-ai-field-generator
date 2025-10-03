"""Text-to-speech client for Google Gemini."""

from __future__ import annotations

import base64
import io
import wave
from typing import Optional

import requests

from .exceptions import ErrorCode, ExternalException
from .speech_client import SpeechClient
from .speech_config import SpeechConfig


class GeminiSpeechClient(SpeechClient):
    """Generate speech using Gemini's `generateContent` endpoint."""

    DEFAULT_BASE_ENDPOINT = (
        "https://generativelanguage.googleapis.com/v1beta/models"
    )
    DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"
    DEFAULT_VOICE = "Kore"
    DEFAULT_TIMEOUT = 60
    DEFAULT_AUDIO_FORMAT = "wav"
    PCM_SAMPLE_RATE = 24_000
    PCM_SAMPLE_WIDTH = 2
    PCM_CHANNELS = 1

    def __init__(self, config: SpeechConfig):
        self._config = config
        self._last_format: Optional[str] = self.DEFAULT_AUDIO_FORMAT

    def generate_speech(
        self,
        text: str,
        *,
        model: Optional[str] = None,
        voice: Optional[str] = None,
        audio_format: Optional[str] = None,
    ) -> bytes:
        if not text.strip():
            raise ExternalException(
                "Cannot synthesize empty text.", code=ErrorCode.INVALID_INPUT
            )
        api_key = (self._config.api_key or "").strip()
        if not api_key:
            raise ExternalException(
                "Set the speech API key before generating audio.",
                code=ErrorCode.MISSING_CREDENTIALS,
            )

        resolved_model = (model or self._config.model or self.DEFAULT_MODEL).strip()
        if not resolved_model:
            raise ExternalException(
                "Gemini speech model is required.",
                code=ErrorCode.INVALID_INPUT,
            )
        resolved_format = self._normalize_format(
            audio_format or self._config.audio_format or self.DEFAULT_AUDIO_FORMAT
        )
        resolved_voice = (voice or self._config.voice or self.DEFAULT_VOICE).strip()

        url = self._resolve_endpoint(resolved_model)
        params = {"key": api_key}
        headers = {"Content-Type": "application/json"}

        generation_config: dict[str, object] = {"responseModalities": ["AUDIO"]}
        speech_config: dict[str, object] = {}
        if resolved_voice:
            speech_config["voiceConfig"] = {
                "prebuiltVoiceConfig": {"voiceName": resolved_voice}
            }
        if speech_config:
            generation_config["speechConfig"] = speech_config

        payload = {
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": generation_config,
        }

        try:
            response = requests.post(
                url,
                params=params,
                headers=headers,
                json=payload,
                timeout=self.DEFAULT_TIMEOUT,
            )
        except requests.exceptions.ConnectionError as exc:
            raise ExternalException(
                "ConnectionError, could not access the Google Gemini speech service.",
                code=ErrorCode.CONNECTION,
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise ExternalException(
                "Timed out while waiting for the Gemini speech response.",
                code=ErrorCode.CONNECTION,
            ) from exc

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            status = response.status_code
            if status == 401:
                raise ExternalException(
                    'Received an "Unauthorized" response; your speech API key is probably invalid.',
                    code=ErrorCode.UNAUTHORIZED,
                ) from exc
            if status == 429:
                raise ExternalException(
                    'Received a "429 Too Many Requests" response from the Gemini speech endpoint.',
                    code=ErrorCode.RATE_LIMIT,
                ) from exc
            if status == 400:
                raise ExternalException(
                    'Request rejected by the Gemini speech endpoint. Adjust the model, voice, or input text.'
                    f"\nGemini response: {response.text}",
                    code=ErrorCode.BAD_REQUEST,
                ) from exc
            raise ExternalException(
                f"Speech request failed: {status} {response.reason}\n{response.text}",
                code=ErrorCode.GENERIC,
            ) from exc

        try:
            payload_json = response.json()
        except ValueError as exc:
            raise ExternalException(
                "Gemini speech response was not valid JSON.",
                code=ErrorCode.GENERIC,
            ) from exc

        try:
            parts = payload_json["candidates"][0]["content"].get("parts", [])
        except (KeyError, IndexError, AttributeError) as exc:
            raise ExternalException(
                "Gemini speech response is missing audio content.",
                code=ErrorCode.AUDIO_MISSING_DATA,
            ) from exc

        for part in parts:
            inline_data = part.get("inlineData") if isinstance(part, dict) else None
            if not inline_data:
                continue
            encoded = inline_data.get("data")
            if not encoded:
                continue
            try:
                raw_bytes = base64.b64decode(encoded)
            except (base64.binascii.Error, ValueError) as exc:
                raise ExternalException(
                    "Failed to decode Gemini audio data.",
                    code=ErrorCode.AUDIO_MISSING_DATA,
                ) from exc
            mime_type = str(inline_data.get("mimeType", "")).lower()
            audio_bytes, detected_format = self._finalize_audio_bytes(
                raw_bytes, mime_type, resolved_format
            )
            self._last_format = detected_format
            return audio_bytes

        raise ExternalException(
            "Gemini speech response did not include inline audio data.",
            code=ErrorCode.AUDIO_MISSING_DATA,
        )

    def _resolve_endpoint(self, model: str) -> str:
        override = (self._config.endpoint or "").strip()
        if override:
            if override.endswith(":generateContent"):
                return override
            base = override.rstrip("/")
            return f"{base}/{model}:generateContent"
        return f"{self.DEFAULT_BASE_ENDPOINT}/{model}:generateContent"

    @staticmethod
    def _normalize_format(fmt: Optional[str]) -> str:
        if not fmt:
            return GeminiSpeechClient.DEFAULT_AUDIO_FORMAT
        normalized = fmt.strip().lower()
        if normalized.startswith("audio/"):
            normalized = normalized.split("/", 1)[-1]
        if normalized.startswith("."):
            normalized = normalized[1:]
        return normalized or GeminiSpeechClient.DEFAULT_AUDIO_FORMAT

    @classmethod
    def _wrap_pcm_as_wav(cls, pcm_bytes: bytes) -> bytes:
        if not pcm_bytes:
            return pcm_bytes
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(cls.PCM_CHANNELS)
            wav_file.setsampwidth(cls.PCM_SAMPLE_WIDTH)
            wav_file.setframerate(cls.PCM_SAMPLE_RATE)
            wav_file.writeframes(pcm_bytes)
        return buffer.getvalue()

    @staticmethod
    def _looks_like_wav(data: bytes) -> bool:
        return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WAVE"

    def _finalize_audio_bytes(
        self, raw_bytes: bytes, mime_type: str, requested_format: str
    ) -> tuple[bytes, str]:
        """Normalize Gemini audio into a playable container and report its format."""

        inferred_format = self._infer_format(mime_type, raw_bytes)

        if inferred_format in {"wav", "wave"} or self._looks_like_wav(raw_bytes):
            return raw_bytes, "wav"

        if inferred_format in {"pcm", "linear16"}:
            wrapped = self._wrap_pcm_as_wav(raw_bytes)
            return wrapped, "wav"

        if inferred_format in {"mp3", "mpeg"}:
            return raw_bytes, "mp3"

        if inferred_format in {"ogg", "opus", "ogg_opus"}:
            return raw_bytes, "ogg"

        if inferred_format == "aac":
            return raw_bytes, "aac"

        if requested_format in {"pcm", "linear16"}:
            wrapped = self._wrap_pcm_as_wav(raw_bytes)
            return wrapped, "wav"

        # Fallback: default to WAV by wrapping the PCM payload.
        wrapped = self._wrap_pcm_as_wav(raw_bytes)
        return wrapped, "wav"

    @staticmethod
    def _infer_format(mime_type: str, raw_bytes: bytes) -> Optional[str]:
        normalized = mime_type.lower().strip()
        if not normalized:
            if GeminiSpeechClient._looks_like_wav(raw_bytes):
                return "wav"
            return None
        if "wav" in normalized or "wave" in normalized:
            return "wav"
        if "ogg" in normalized:
            return "ogg"
        if "opus" in normalized:
            return "ogg"
        if "mp3" in normalized or "mpeg" in normalized:
            return "mp3"
        if "aac" in normalized:
            return "aac"
        if "pcm" in normalized or "linear16" in normalized or "s16" in normalized:
            return "pcm"
        return None

    def get_last_audio_format(self) -> Optional[str]:
        return self._last_format
