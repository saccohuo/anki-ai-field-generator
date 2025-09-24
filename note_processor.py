from anki.notes import Note as AnkiNote
from aqt.qt import QSettings
from PyQt6.QtCore import QThread, pyqtSignal

from pathlib import Path
import uuid

from .exceptions import ExternalException
from .llm_client import LLMClient
from .prompt_config import PromptConfig
from .settings import SettingsNames
from .gemini_client import GeminiClient

IMAGE_MAPPING_SEPARATOR = "->"


class NoteProcessor(QThread):
    """
    Stores the relevant information from a note that will be sent to GPT for modification.
    """

    progress_updated = pyqtSignal(int, str)  # Signal to update progress bar and label
    finished = pyqtSignal()  # Signal for when processing is done
    error = pyqtSignal(str)  # Signal for when processing is done

    def __init__(
        self,
        notes: list[AnkiNote],
        client: LLMClient,
        settings: QSettings,  # might be cleaner to pass in the fields we need directly, not sure,
        missing_field_is_error: bool = False,
    ):
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
        self._gemini_image_client: GeminiClient | None = None

    def run(self):
        """
        Processes all notes sequentially, by calling the LLM client.
        """
        for i in range(self.current_index, self.total_items):
            note = self.notes[self.current_index]
            prompt = self.client.get_user_prompt(note, self.missing_field_is_error)
            self.progress_updated.emit(
                int((i / self.total_items) * 100),
                f"Processing: {prompt}",
            )
            try:
                response = self.client.call([prompt])
            except ExternalException as e:
                self.error.emit(str(e))
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

            per_card = 100 / self.total_items if self.total_items else 100
            base_progress = (i / self.total_items) * 100 if self.total_items else 0

            if needs_image:
                self.progress_updated.emit(
                    int(base_progress + per_card / 2), "Generating image..."
                )
            else:
                self.progress_updated.emit(
                    min(100, int(base_progress + per_card)),
                    f"Completed {i + 1}/{self.total_items}",
                )

            try:
                self._apply_image_generation(note)
            except ExternalException as exc:
                self.error.emit(str(exc))
                return
            except Exception as exc:  # pragma: no cover - unexpected errors
                self.error.emit(f"Image generation failed: {exc}")
                return
            if needs_image:
                self.progress_updated.emit(
                    min(100, int(base_progress + per_card)),
                    f"Completed {i + 1}/{self.total_items}",
                )
            note.col.update_note(note)
            self.current_index += 1

        if self.total_items == 1:
            self.progress_updated.emit(100, "Completed")

        self.finished.emit()

    def _apply_image_generation(self, note: AnkiNote) -> None:
        if not self.image_field_mappings:
            return
        image_client = self._get_image_client()
        configured_model = getattr(image_client.prompt_config, "model", "") or None
        for prompt_field, image_field in self.image_field_mappings:
            if prompt_field not in note or image_field not in note:
                continue
            prompt_value = str(note[prompt_field]).strip()
            if not prompt_value:
                continue
            image_bytes = image_client.generate_image(prompt_value, model=configured_model)
            if not image_bytes:
                continue
            filename = self._write_image_to_media(note, image_bytes, image_field)
            note[image_field] = f'<img src="{filename}">'

    def _write_image_to_media(self, note: AnkiNote, image_bytes: bytes, image_field: str) -> str:
        media = getattr(note.col, "media", None)
        if media is None:
            raise ExternalException("Anki media manager is unavailable.")
        filename = f"nano_banana_{note.id}_{image_field}_{uuid.uuid4().hex[:8]}.png"
        writer = getattr(media, "write_data", None)
        if callable(writer):
            writer(filename, image_bytes)
        else:
            legacy_writer = getattr(media, "writeData", None)
            if callable(legacy_writer):
                legacy_writer(filename, image_bytes)  # type: ignore[attr-defined]
            else:
                raise ExternalException("Could not persist image to Anki media collection.")
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
                "Set the image generation API key before generating images."
            )
        return api_key
