
from dataclasses import dataclass
from typing import Any, Callable, Optional

import html
import re

from anki.notes import Note as AnkiNote
from aqt.qt import QSettings
from PyQt6.QtCore import QThread, pyqtSignal

import uuid

from .exceptions import ErrorCode, ExternalException
from .llm_client import LLMClient
from .speech_client import SpeechClient
from .prompt_config import PromptConfig
from .settings import SettingsNames
from .gemini_client import GeminiClient

IMAGE_MAPPING_SEPARATOR = "->"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    wait_seconds: float


class NoteProcessor(QThread):
    """Processes notes via the configured LLM plus optional image and speech pipelines."""

    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        notes: list[AnkiNote],
        client: LLMClient,
        settings: QSettings,
        speech_client: Optional[SpeechClient] = None,
        missing_field_is_error: bool = False,
    ) -> None:
        super().__init__()
        self.notes = notes
        self.total_items = len(notes)
        self.client = client
        self.settings = settings
        self.note_fields = settings.value(
            SettingsNames.DESTINATION_FIELD_SETTING_NAME, type="QStringList"
        )
        self.response_keys = settings.value(
            SettingsNames.RESPONSE_KEYS_SETTING_NAME, type="QStringList"
        )
        self._speech_client = speech_client
        audio_mappings = settings.value(
            SettingsNames.AUDIO_MAPPING_SETTING_NAME, type="QStringList"
        ) or []
        self.audio_field_mappings: list[tuple[str, str]] = []
        for mapping in audio_mappings:
            if IMAGE_MAPPING_SEPARATOR in mapping:
                prompt, audio = [
                    part.strip() for part in mapping.split(IMAGE_MAPPING_SEPARATOR, 1)
                ]
                if prompt and audio:
                    self.audio_field_mappings.append((prompt, audio))
        self._audio_model = (
            settings.value(
                SettingsNames.AUDIO_MODEL_SETTING_NAME, defaultValue="", type=str
            )
            or None
        )
        self._audio_voice = (
            settings.value(
                SettingsNames.AUDIO_VOICE_SETTING_NAME, defaultValue="", type=str
            )
            or None
        )
        raw_audio_format = settings.value(
            SettingsNames.AUDIO_FORMAT_SETTING_NAME, defaultValue="wav", type=str
        )
        self._audio_format = (raw_audio_format or "wav").strip().lower() or "wav"
        mappings = settings.value(
            SettingsNames.IMAGE_MAPPING_SETTING_NAME, type="QStringList"
        ) or []
        self.image_field_mappings: list[tuple[str, str]] = []
        for mapping in mappings:
            if IMAGE_MAPPING_SEPARATOR in mapping:
                prompt, image = [
                    part.strip() for part in mapping.split(IMAGE_MAPPING_SEPARATOR, 1)
                ]
                if prompt and image:
                    self.image_field_mappings.append((prompt, image))
        self.missing_field_is_error = missing_field_is_error
        self.current_index = 0
        self._gemini_image_client: Optional[GeminiClient] = None
        self._retry_policies: dict[ErrorCode, RetryPolicy] = {
            ErrorCode.CONNECTION: RetryPolicy(max_attempts=3, wait_seconds=5),
            ErrorCode.RATE_LIMIT: RetryPolicy(max_attempts=4, wait_seconds=10),
            ErrorCode.IMAGE_MISSING_DATA: RetryPolicy(max_attempts=3, wait_seconds=3),
            ErrorCode.AUDIO_MISSING_DATA: RetryPolicy(max_attempts=3, wait_seconds=3),
        }

    def run(self) -> None:
        for i in range(self.current_index, self.total_items):
            note = self.notes[self.current_index]
            prompt = self.client.get_user_prompt(note, self.missing_field_is_error)
            base_progress = (i / self.total_items) * 100 if self.total_items else 0
            per_card = 100 / self.total_items if self.total_items else 100

            self.progress_updated.emit(
                int(base_progress),
                f"Processing: {prompt}",
            )

            try:
                response = self._run_with_retry(
                    lambda: self.client.call([prompt]),
                    "Text generation",
                    progress_value=int(base_progress),
                )
            except ExternalException as exc:
                self.error.emit(self._format_error_message("Text generation", exc))
                return

            for note_field, response_key in zip(self.note_fields, self.response_keys):
                note[note_field] = response[response_key]

            needs_image = bool(
                self.image_field_mappings
                and any(
                    prompt_field in note and str(note[prompt_field]).strip()
                    for prompt_field, _ in self.image_field_mappings
                )
            )

            if needs_image:
                interim_progress = int(min(99, base_progress + per_card / 2))
                self.progress_updated.emit(interim_progress, "Generating image...")
                try:
                    self._apply_image_generation(
                        note,
                        base_progress=base_progress,
                        per_card=per_card,
                    )
                except ExternalException as exc:
                    self.error.emit(self._format_error_message("Image generation", exc))
                    return

            needs_speech = bool(
                self._speech_client
                and self.audio_field_mappings
                and any(
                    prompt_field in note and str(note[prompt_field]).strip()
                    for prompt_field, _ in self.audio_field_mappings
                )
            )

            if needs_speech:
                speech_progress = int(min(99, base_progress + (per_card * 0.75)))
                self.progress_updated.emit(speech_progress, "Generating audio...")
                try:
                    self._apply_speech_generation(
                        note,
                        base_progress=base_progress,
                        per_card=per_card,
                    )
                except ExternalException as exc:
                    self.error.emit(self._format_error_message("Speech generation", exc))
                    return

            self.progress_updated.emit(
                min(100, int(base_progress + per_card)),
                f"Completed {i + 1}/{self.total_items}",
            )
            note.col.update_note(note)
            self.current_index += 1

        if self.total_items == 1:
            self.progress_updated.emit(100, "Completed")

        self.finished.emit()

    def _apply_speech_generation(
        self,
        note: AnkiNote,
        *,
        base_progress: float,
        per_card: float,
    ) -> None:
        if not self._speech_client or not self.audio_field_mappings:
            return

        pending: list[tuple[str, str, str]] = []
        for prompt_field, audio_field in self.audio_field_mappings:
            if prompt_field not in note or audio_field not in note:
                continue
            prompt_raw = str(note[prompt_field])
            prompt_value = self._prepare_speech_text(prompt_raw)
            if not prompt_value:
                continue
            pending.append((prompt_field, audio_field, prompt_value))

        if not pending:
            return

        retry_progress = int(min(99, base_progress + (per_card * 0.75)))

        for prompt_field, audio_field, prompt_value in pending:
            existing_audio_files = self._extract_audio_filenames(
                str(note[audio_field])
            )
            def synthesize(value: str = prompt_value) -> bytes:
                return self._speech_client.generate_speech(
                    value,
                    model=self._audio_model,
                    voice=self._audio_voice,
                    audio_format=self._audio_format,
                )

            audio_bytes = self._run_with_retry(
                synthesize,
                f"Speech generation ({prompt_field}->{audio_field})",
                progress_value=retry_progress,
            )
            detected_format = None
            format_getter = getattr(self._speech_client, "get_last_audio_format", None)
            if callable(format_getter):
                detected_format = format_getter() or None
            filename = self._write_audio_to_media(
                note,
                audio_bytes,
                audio_field,
                detected_format=detected_format,
            )
            audio_tag = f"[sound:{filename}]"
            note[audio_field] = audio_tag
            if existing_audio_files:
                self._trash_audio_files(note, existing_audio_files)

    def _apply_image_generation(
        self,
        note: AnkiNote,
        *,
        base_progress: float,
        per_card: float,
    ) -> None:
        if not self.image_field_mappings:
            return

        image_client = self._get_image_client()
        configured_model = getattr(image_client.prompt_config, "model", "") or None

        pending: list[tuple[str, str, str]] = []
        for prompt_field, image_field in self.image_field_mappings:
            if prompt_field not in note or image_field not in note:
                continue
            prompt_value = str(note[prompt_field]).strip()
            if not prompt_value:
                continue
            pending.append((prompt_field, image_field, prompt_value))

        if not pending:
            return

        retry_progress = int(min(99, base_progress + per_card / 2))

        for prompt_field, image_field, prompt_value in pending:
            def generate(value: str = prompt_value) -> bytes:
                return image_client.generate_image(value, model=configured_model)

            image_bytes = self._run_with_retry(
                generate,
                f"Image generation ({prompt_field}->{image_field})",
                progress_value=retry_progress,
            )
            filename = self._write_image_to_media(note, image_bytes, image_field)
            note[image_field] = f'<img src="{filename}">'

    def _write_audio_to_media(
        self,
        note: AnkiNote,
        audio_bytes: bytes,
        audio_field: str,
        *,
        detected_format: Optional[str] = None,
    ) -> str:
        if not audio_bytes:
            raise ExternalException(
                "Speech provider returned empty audio data.",
                code=ErrorCode.AUDIO_MISSING_DATA,
            )
        media = getattr(note.col, "media", None)
        if media is None:
            raise ExternalException(
                "Anki media manager is unavailable.",
                code=ErrorCode.MEDIA_WRITE_FAILED,
            )
        normalized_format = (
            detected_format
            or self._audio_format
            or "wav"
        ).lower().strip()
        if "/" in normalized_format:
            normalized_format = normalized_format.split("/", 1)[-1]
        normalized_format = normalized_format.lstrip(".") or "wav"
        filename = (
            f"nano_banana_{note.id}_{audio_field}_{uuid.uuid4().hex[:8]}."
            f"{normalized_format}"
        )
        writer = getattr(media, "write_data", None)
        if callable(writer):
            writer(filename, audio_bytes)
        else:
            legacy_writer = getattr(media, "writeData", None)
            if callable(legacy_writer):
                legacy_writer(filename, audio_bytes)  # type: ignore[attr-defined]
            else:
                raise ExternalException(
                    "Could not persist audio to Anki media collection.",
                    code=ErrorCode.MEDIA_WRITE_FAILED,
                )
        return filename

    @staticmethod
    def _extract_audio_filenames(field_value: str) -> list[str]:
        if not field_value:
            return []
        return re.findall(r"\[sound:([^\]]+)\]", field_value)

    @staticmethod
    def _trash_audio_files(note: AnkiNote, filenames: list[str]) -> None:
        if not filenames:
            return
        media = getattr(note.col, "media", None)
        if media is None:
            return
        try:
            trash = getattr(media, "trash_files", None)
            if callable(trash):
                trash(filenames)
                return
        except Exception:
            pass
        for name in filenames:
            for candidate in ("remove_file", "removeFile"):
                remover = getattr(media, candidate, None)
                if callable(remover):
                    try:
                        remover(name)
                    except Exception:
                        pass
                    break

    @staticmethod
    def _prepare_speech_text(value: str) -> str:
        if not value:
            return ""
        text = re.sub(r"\[sound:[^\]]+\]", " ", value)
        text = re.sub(r"{{c\d+::(.*?)(::.*?)?}}", r"\1", text)
        text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"</?(div|p|span)[^>]*>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        text = text.replace("&nbsp;", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _write_image_to_media(
        self, note: AnkiNote, image_bytes: bytes, image_field: str
    ) -> str:
        media = getattr(note.col, "media", None)
        if media is None:
            raise ExternalException(
                "Anki media manager is unavailable.",
                code=ErrorCode.MEDIA_WRITE_FAILED,
            )
        filename = f"nano_banana_{note.id}_{image_field}_{uuid.uuid4().hex[:8]}.png"
        writer = getattr(media, "write_data", None)
        if callable(writer):
            writer(filename, image_bytes)
        else:
            legacy_writer = getattr(media, "writeData", None)
            if callable(legacy_writer):
                legacy_writer(filename, image_bytes)  # type: ignore[attr-defined]
            else:
                raise ExternalException(
                    "Could not persist image to Anki media collection.",
                    code=ErrorCode.MEDIA_WRITE_FAILED,
                )
        return filename

    def _get_image_client(self) -> GeminiClient:
        if self._gemini_image_client is not None:
            return self._gemini_image_client

        api_key = self._load_gemini_api_key()
        endpoint = (
            self.settings.value(
                SettingsNames.IMAGE_ENDPOINT_SETTING_NAME, defaultValue="", type=str
            )
            or ""
        )
        image_model = (
            self.settings.value(
                SettingsNames.IMAGE_MODEL_SETTING_NAME, defaultValue="", type=str
            )
            or GeminiClient.IMAGE_MODEL
        )
        config = PromptConfig.create_test_instance(
            api_key=api_key,
            system_prompt="",
            user_prompt="",
            response_keys=[],
            model=image_model,
            endpoint=endpoint,
        )
        self._gemini_image_client = GeminiClient(config)
        return self._gemini_image_client

    def _load_gemini_api_key(self) -> str:
        api_key = (
            self.settings.value(
                SettingsNames.IMAGE_API_KEY_SETTING_NAME, defaultValue="", type=str
            )
            or ""
        )
        if not api_key:
            raise ExternalException(
                "Set the image generation API key before generating images.",
                code=ErrorCode.MISSING_CREDENTIALS,
            )
        return api_key

    def _run_with_retry(
        self,
        operation: Callable[[], Any],
        stage_label: str,
        *,
        progress_value: Optional[int] = None,
    ) -> Any:
        attempt = 1
        while True:
            try:
                return operation()
            except ExternalException as exc:
                policy = self._retry_policies.get(exc.code)
                if policy and attempt < policy.max_attempts:
                    wait_seconds = policy.wait_seconds
                    message = (
                        f"{stage_label} failed ({exc.code.value}). Retrying in "
                        f"{int(wait_seconds)}s..."
                    )
                    progress = progress_value if progress_value is not None else 0
                    self.progress_updated.emit(progress, message)
                    QThread.msleep(int(wait_seconds * 1000))
                    attempt += 1
                    continue
                exc.attempts = attempt
                exc.retry_policy = policy
                raise

    def _format_error_message(self, stage_label: str, exc: ExternalException) -> str:
        guidance_map = {
            ErrorCode.CONNECTION: "Check your network connection, then click Continue to retry.",
            ErrorCode.RATE_LIMIT: "You are hitting the provider's rate limit. Wait a few seconds before trying again.",
            ErrorCode.UNAUTHORIZED: "Verify the API key in the plugin settings before retrying.",
            ErrorCode.MISSING_CREDENTIALS: "Provide the image generation API key in plugin settings and rerun.",
            ErrorCode.BAD_REQUEST: "The request looks invalid. Adjust the prompt/model settings before retrying.",
            ErrorCode.IMAGE_MISSING_DATA: "The model did not return image bytes. Adjust the prompt or switch the image model.",
            ErrorCode.IMAGE_DECODE: "Received image data could not be decoded. Try a different prompt or model.",
            ErrorCode.AUDIO_MISSING_DATA: "The speech model did not return audio bytes. Adjust the prompt or switch the speech model.",
            ErrorCode.MEDIA_WRITE_FAILED: "Anki refused to write the image. Check media folder permissions.",
        }
        code_text = f"[{exc.code.value}] " if hasattr(exc, "code") else ""
        attempts = getattr(exc, "attempts", 1)
        guidance = guidance_map.get(getattr(exc, "code", None))
        if getattr(exc, "retry_policy", None) and attempts > 1:
            summary = f"{code_text}{stage_label} failed after {attempts} attempt(s): {exc}"
        else:
            summary = f"{code_text}{stage_label} failed: {exc}"
        if guidance:
            summary = f"{summary}\n{guidance}"
        return summary
