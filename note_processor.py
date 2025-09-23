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
            try:
                self._apply_image_generation(note)
            except ExternalException as exc:
                self.error.emit(str(exc))
                return
            except Exception as exc:  # pragma: no cover - unexpected errors
                self.error.emit(f"Image generation failed: {exc}")
                return
            note.col.update_note(note)
            self.current_index += 1

        self.finished.emit()

    def _apply_image_generation(self, note: AnkiNote) -> None:
        if not self.image_field_mappings:
            return
        image_client = self._get_image_client()
        for prompt_field, image_field in self.image_field_mappings:
            if prompt_field not in note or image_field not in note:
                continue
            prompt_value = str(note[prompt_field]).strip()
            if not prompt_value:
                continue
            image_bytes = image_client.generate_image(prompt_value)
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
        config = PromptConfig.create_test_instance(
            api_key=api_key,
            system_prompt="",
            user_prompt="",
            response_keys=[],
            model=GeminiClient.IMAGE_MODEL,
        )
        self._gemini_image_client = GeminiClient(config)
        return self._gemini_image_client

    def _load_gemini_api_key(self) -> str:
        key_path = Path(__file__).resolve().parent / "tests" / "gemini_api"
        try:
            api_key = key_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise ExternalException(
                f"Gemini API key file not found at {key_path}."
            ) from exc
        if not api_key:
            raise ExternalException(
                "Gemini API key file is empty; cannot generate images."
            )
        return api_key
