
from dataclasses import dataclass
from typing import Any, Callable, Optional

from anki.notes import Note as AnkiNote
from aqt.qt import QSettings
from PyQt6.QtCore import QThread, pyqtSignal

import uuid

from .exceptions import ErrorCode, ExternalException
from .llm_client import LLMClient
from .prompt_config import PromptConfig
from .settings import SettingsNames
from .gemini_client import GeminiClient

IMAGE_MAPPING_SEPARATOR = "->"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    wait_seconds: float


class NoteProcessor(QThread):
    """Processes notes by invoking the configured LLM and optional image pipeline."""

    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        notes: list[AnkiNote],
        client: LLMClient,
        settings: QSettings,
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

            self.progress_updated.emit(
                min(100, int(base_progress + per_card)),
                f"Completed {i + 1}/{self.total_items}",
            )
            note.col.update_note(note)
            self.current_index += 1

        if self.total_items == 1:
            self.progress_updated.emit(100, "Completed")

        self.finished.emit()

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
