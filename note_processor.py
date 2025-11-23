
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

import html
import json
import re
import sqlite3
import threading
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from urllib import request as urllib_request, error as urllib_error

from anki.notes import Note as AnkiNote
from aqt.qt import QSettings
from PyQt6.QtCore import QThread, pyqtSignal

import uuid

try:
    from anki.errors import BackendError, DBError
except Exception:  # pragma: no cover
    BackendError = DBError = Exception

from .exceptions import ErrorCode, ExternalException
from .llm_client import LLMClient
from .speech_client import SpeechClient
from .prompt_config import PromptConfig
from .settings import SettingsNames
from .gemini_client import GeminiClient

IMAGE_MAPPING_SEPARATOR = "->"
LOG_FILE = Path(__file__).with_name("anki_ai_runtime.log")
COLLECTION_LOCK_FRAGMENTS = (
    "collection is locked",
    "collection is in use",
    "collection currently locked",
    "collection already locked",
    "collection busy",
    "busy, another operation is running",
    "another operation is running",
    "database is locked",
    "db is locked",
    "database table is locked",
    "the database file is locked",
)
OAAD_HOME_URL = "https://www.oxfordlearnersdictionaries.com/"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    wait_seconds: float


class NoteProcessor(QThread):
    """Processes notes via the configured LLM plus optional image and speech pipelines."""

    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    conflict_detected = pyqtSignal(dict)
    conflict_decision = pyqtSignal(int, str)

    def __init__(
        self,
        notes: list[AnkiNote],
        client: LLMClient,
        settings: QSettings,
        speech_client: Optional[SpeechClient] = None,
        *,
        generate_text: bool = True,
        generate_images: bool = True,
        generate_audio: bool = True,
        generate_youglish: bool = True,
        generate_oaad: bool = True,
        missing_field_is_error: bool = False,
    ) -> None:
        super().__init__()
        self.conflict_decision.connect(self._on_conflict_decision)
        self._conflict_event = threading.Event()
        self._active_conflict_note_id: Optional[int] = None
        self._current_conflict_decision: Optional[str] = None
        self.cancelled = False
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
        self.note_fields = list(self.note_fields or [])
        self.response_keys = list(self.response_keys or [])
        raw_text_entries = settings.value(
            SettingsNames.TEXT_MAPPING_ENTRIES_SETTING_NAME,
            defaultValue="",
            type=str,
        )
        self._text_rows = self._parse_text_rows(
            raw_text_entries,
            self.response_keys,
            self.note_fields,
        )
        if generate_text:
            active_text_rows = [
                (key, field)
                for key, field, _ in self._text_rows
                if key and field
            ]
        else:
            active_text_rows = [
                (key, field)
                for key, field, enabled in self._text_rows
                if enabled and key and field
            ]
        self.response_keys = [key for key, _ in active_text_rows]
        self.note_fields = [field for _, field in active_text_rows]
        self._speech_client = speech_client
        audio_mappings = settings.value(
            SettingsNames.AUDIO_MAPPING_SETTING_NAME, type="QStringList"
        ) or []
        decoded_audio = [self._decode_mapping_entry(entry) for entry in audio_mappings]
        self._audio_rows = [
            (prompt, target, enabled)
            for prompt, target, enabled in decoded_audio
            if prompt and target
        ]
        if generate_audio:
            self.audio_field_mappings = [
                (prompt, target) for prompt, target, _ in self._audio_rows
            ]
        else:
            self.audio_field_mappings = [
                (prompt, target)
                for prompt, target, enabled in self._audio_rows
                if enabled
            ]
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
        self._youglish_enabled = self._get_bool_setting(
            self.settings,
            SettingsNames.YOUGLISH_ENABLED_SETTING_NAME,
            default=True,
        )
        self._youglish_source_field = (
            self.settings.value(
                SettingsNames.YOUGLISH_SOURCE_FIELD_SETTING_NAME,
                defaultValue="_word",
                type=str,
            )
            or "_word"
        ).strip()
        self._youglish_target_field = (
            self.settings.value(
                SettingsNames.YOUGLISH_TARGET_FIELD_SETTING_NAME,
                defaultValue="_youglish",
                type=str,
            )
            or "_youglish"
        ).strip()
        accent_raw = (
            self.settings.value(
                SettingsNames.YOUGLISH_ACCENT_SETTING_NAME,
                defaultValue="us",
                type=str,
            )
            or "us"
        ).strip()
        accent_normalized = accent_raw.lower()
        self._youglish_accent = (
            accent_normalized if accent_normalized in {"us", "uk", "aus"} else "us"
        )
        self._youglish_overwrite = self._get_bool_setting(
            self.settings,
            SettingsNames.YOUGLISH_OVERWRITE_SETTING_NAME,
            default=False,
        )
        self._generate_youglish = generate_youglish
        self._oaad_enabled = self._get_bool_setting(
            self.settings,
            SettingsNames.OAAD_ENABLED_SETTING_NAME,
            default=True,
        )
        self._oaad_source_field = (
            self.settings.value(
                SettingsNames.OAAD_SOURCE_FIELD_SETTING_NAME,
                defaultValue="_word",
                type=str,
            )
            or "_word"
        ).strip()
        self._oaad_target_field = (
            self.settings.value(
                SettingsNames.OAAD_TARGET_FIELD_SETTING_NAME,
                defaultValue="_oaad",
                type=str,
            )
            or "_oaad"
        ).strip()
        oaad_accent_raw = (
            self.settings.value(
                SettingsNames.OAAD_ACCENT_SETTING_NAME,
                defaultValue="us",
                type=str,
            )
            or "us"
        ).strip()
        oaad_normalized = oaad_accent_raw.lower()
        self._oaad_accent = oaad_normalized if oaad_normalized in {"us", "uk"} else "us"
        self._oaad_overwrite = self._get_bool_setting(
            self.settings,
            SettingsNames.OAAD_OVERWRITE_SETTING_NAME,
            default=False,
        )
        self._generate_oaad = generate_oaad
        mappings = settings.value(
            SettingsNames.IMAGE_MAPPING_SETTING_NAME, type="QStringList"
        ) or []
        decoded_images = [self._decode_mapping_entry(entry) for entry in mappings]
        self._image_rows = [
            (prompt, target, enabled)
            for prompt, target, enabled in decoded_images
            if prompt and target
        ]
        if generate_images:
            self.image_field_mappings = [
                (prompt, target) for prompt, target, _ in self._image_rows
            ]
        else:
            self.image_field_mappings = [
                (prompt, target)
                for prompt, target, enabled in self._image_rows
                if enabled
            ]
        self.missing_field_is_error = missing_field_is_error
        self.current_index = 0
        self._image_provider = (
            self.settings.value(
                SettingsNames.IMAGE_PROVIDER_SETTING_NAME, defaultValue="gemini", type=str
            )
            or "gemini"
        ).lower()
        self._image_client: Optional[GeminiClient] = None
        retry_limit = int(
            settings.value(SettingsNames.RETRY_LIMIT_SETTING_NAME, defaultValue=50)
        )
        retry_delay = float(
            settings.value(SettingsNames.RETRY_DELAY_SETTING_NAME, defaultValue=5.0)
        )
        retry_limit = max(1, retry_limit)
        retry_delay = max(0.5, retry_delay)
        self._retry_policies: dict[ErrorCode, RetryPolicy] = {
            ErrorCode.CONNECTION: RetryPolicy(
                max_attempts=retry_limit,
                wait_seconds=retry_delay,
            ),
            ErrorCode.RATE_LIMIT: RetryPolicy(
                max_attempts=retry_limit,
                wait_seconds=max(retry_delay * 2, retry_delay),
            ),
            ErrorCode.IMAGE_MISSING_DATA: RetryPolicy(
                max_attempts=retry_limit,
                wait_seconds=max(retry_delay, 1.0),
            ),
            ErrorCode.AUDIO_MISSING_DATA: RetryPolicy(
                max_attempts=retry_limit,
                wait_seconds=max(retry_delay, 1.0),
            ),
        }
        self._enable_text_generation = bool(generate_text and self.response_keys)
        self._enable_image_generation = bool(generate_images and self.image_field_mappings)
        self._enable_audio_generation = bool(
            generate_audio and self.audio_field_mappings and speech_client is not None
        )
        self._enable_youglish = bool(
            generate_youglish
            and self._youglish_enabled
            and self._youglish_source_field
            and self._youglish_target_field
        )
        self._enable_oaad = bool(
            generate_oaad
            and self._oaad_enabled
            and self._oaad_source_field
            and self._oaad_target_field
        )
        if not self._enable_audio_generation:
            self._speech_client = None

        self._note_progress: dict[int, dict[str, Any]] = {}
        self._snapshots = self._build_initial_snapshots()
        self._initialize_note_progress()
        self._collection_retry_limit = 120
        self._collection_retry_delay = 0.5
        self._completed_successfully = False
        self._had_error = False
        self._note_errors: list[str] = []
        self.note_error_summary: str = ""
        self._json_parse_retry_limit = 3

    def run(self) -> None:
        self._log_event(f"NoteProcessor started; total_notes={self.total_items}")
        try:
            self._process_notes()
            if (
                not self._completed_successfully
                and not self.cancelled
                and not self._had_error
            ):
                message = (
                    f"任务未能完成全部笔记（已完成 {self.current_index}/{self.total_items}）。\n"
                    f"请查看日志获取详情：{LOG_FILE}"
                )
                self._emit_plain_error(message)
                return
        except ExternalException as exc:
            self._emit_stage_error("Processing", exc)
        except Exception as exc:  # pragma: no cover
            self._log_event("NoteProcessor crashed with unexpected error.", exc=exc)
            message = (
                f"任务异常退出：{exc}\n"
                f"请查看日志获取更多信息：{LOG_FILE}"
            )
            self.error.emit(message)
        finally:
            status = "cancelled" if self.cancelled else "completed"
            self._log_event(f"NoteProcessor finished with status={status}")

    def _process_notes(self) -> None:
        for i in range(self.current_index, self.total_items):
            if self.isInterruptionRequested():
                self.cancelled = True
                self._log_event("Processing interrupted externally; stopping thread.")
                return
            note = self.notes[self.current_index]
            refresh_progress = int((i / self.total_items) * 100) if self.total_items else 0
            note = self._refresh_note_reference(
                note,
                progress_value=refresh_progress,
            )
            self.notes[self.current_index] = note
            self._log_event(
                f"Processing note {i + 1}/{self.total_items} (note_id={getattr(note, 'id', 'unknown')})."
            )
            note_state = self._note_progress.setdefault(
                note.id, self._create_note_state()
            )
            prompt_preview = self.client.get_user_prompt(
                note, self.missing_field_is_error
            )
            base_progress = (i / self.total_items) * 100 if self.total_items else 0
            per_card = 100 / self.total_items if self.total_items else 100

            self.progress_updated.emit(
                int(base_progress),
                f"Processing: {prompt_preview}",
            )

            if self._enable_text_generation and not note_state["text"]:
                skip_note = False
                response = None
                json_retry_attempt = 0
                while True:
                    try:
                        response = self._run_with_retry(
                            lambda: self.client.call([prompt_preview]),
                            "Text generation",
                            progress_value=int(base_progress),
                        )
                        break
                    except ExternalException as exc:
                        if (
                            self._is_json_parse_error(exc)
                            and json_retry_attempt + 1 < self._json_parse_retry_limit
                        ):
                            json_retry_attempt += 1
                            self._report_json_retry(
                                note,
                                json_retry_attempt,
                                self._json_parse_retry_limit,
                                exc,
                            )
                            continue
                        if self._should_skip_note_error("text", exc):
                            self._record_note_error(note, "文本生成", exc)
                            self.current_index += 1
                            skip_note = True
                            break
                        self._emit_stage_error("Text generation", exc)
                        return
                if skip_note or response is None:
                    continue

                missing_keys: list[str] = []
                text_new_values: dict[str, Any] = {}
                for note_field, response_key in zip(self.note_fields, self.response_keys):
                    if response_key not in response:
                        missing_keys.append(response_key)
                        continue
                    text_new_values[note_field] = response[response_key]

                if missing_keys:
                    available = list(response.keys()) if isinstance(response, dict) else []
                    self._log_event(
                        "Model response missing expected keys.",
                        {
                            "note_id": getattr(note, "id", "unknown"),
                            "missing_keys": missing_keys,
                            "available_keys": available,
                        },
                    )
                    self._record_note_error(
                        note,
                        "文本生成",
                        ExternalException(
                            f"模型响应缺少字段：{', '.join(missing_keys)}",
                            code=ErrorCode.BAD_REQUEST,
                            details={
                                "missing_keys": missing_keys,
                                "available_keys": available,
                            },
                        ),
                    )
                    self.current_index += 1
                    continue

                text_fields = list(text_new_values.keys())
                note, conflicts = self._check_for_conflicts(
                    note,
                    "text",
                    text_fields,
                    text_new_values,
                )
                self.notes[self.current_index] = note
                skip_text = False
                if conflicts:
                    decision = self._wait_for_conflict_resolution(
                        note.id,
                        "text",
                        conflicts,
                    )
                    if decision == "skip":
                        skip_text = True
                        self._update_snapshot_section(note, "text", text_fields)
                    elif decision == "abort":
                        self._emit_plain_error("Processing cancelled by user.")
                        return
                if not skip_text:
                    for field_name, value in text_new_values.items():
                        note[field_name] = value
                    try:
                        self._commit_note_sections(
                            note,
                            [("text", text_fields)],
                        )
                    except ExternalException as exc:
                        self._emit_stage_error("Saving text fields", exc)
                        return
                note_state["text"] = True
            else:
                note_state["text"] = True

            if self._enable_image_generation:
                needs_image = any(
                    not note_state["image"].get((prompt_field, image_field), False)
                    and prompt_field in note
                    and str(note[prompt_field]).strip()
                    for prompt_field, image_field in self.image_field_mappings
                )
                if needs_image:
                    interim_progress = int(min(99, base_progress + per_card / 2))
                    self.progress_updated.emit(interim_progress, "Generating image...")
                    try:
                        note, image_fields = self._apply_image_generation(
                            note,
                            note_state,
                            base_progress=base_progress,
                            per_card=per_card,
                        )
                        self.notes[self.current_index] = note
                        if image_fields:
                            try:
                                self._commit_note_sections(
                                    note,
                                    [("image", image_fields)],
                                )
                            except ExternalException as exc:
                                self._emit_stage_error("Saving image fields", exc)
                                return
                    except ExternalException as exc:
                        self._emit_stage_error("Image generation", exc)
                        return
                else:
                    for mapping in self.image_field_mappings:
                        note_state["image"][mapping] = True
            else:
                for mapping in self.image_field_mappings:
                    note_state["image"][mapping] = True

            if self._enable_audio_generation:
                needs_speech = any(
                    not note_state["audio"].get((prompt_field, audio_field), False)
                    and prompt_field in note
                    and str(note[prompt_field]).strip()
                    for prompt_field, audio_field in self.audio_field_mappings
                )
                if needs_speech:
                    speech_progress = int(min(99, base_progress + (per_card * 0.75)))
                    self.progress_updated.emit(speech_progress, "Generating audio...")
                    try:
                        note, audio_fields = self._apply_speech_generation(
                            note,
                            note_state,
                            base_progress=base_progress,
                            per_card=per_card,
                        )
                        self.notes[self.current_index] = note
                        if audio_fields:
                            try:
                                self._commit_note_sections(
                                    note,
                                    [("audio", audio_fields)],
                                )
                            except ExternalException as exc:
                                self._emit_stage_error("Saving audio fields", exc)
                                return
                    except ExternalException as exc:
                        self._emit_stage_error("Speech generation", exc)
                        return
                else:
                    for mapping in self.audio_field_mappings:
                        note_state["audio"][mapping] = True
            else:
                for mapping in self.audio_field_mappings:
                    note_state["audio"][mapping] = True

            if self._enable_oaad:
                try:
                    note, oaad_fields = self._apply_oaad_links(
                        note,
                        note_state,
                        base_progress=base_progress,
                        per_card=per_card,
                    )
                    self.notes[self.current_index] = note
                    if oaad_fields:
                        self._commit_note_sections(
                            note,
                            [("oaad", oaad_fields)],
                        )
                except ExternalException as exc:
                    self._emit_stage_error("OAAD 链接生成", exc)
                    return
            else:
                note_state["oaad"] = True

            if self._enable_youglish:
                try:
                    note, youglish_fields = self._apply_youglish_links(
                        note,
                        note_state,
                        base_progress=base_progress,
                        per_card=per_card,
                    )
                    self.notes[self.current_index] = note
                    if youglish_fields:
                        self._commit_note_sections(
                            note,
                            [("youglish", youglish_fields)],
                        )
                except ExternalException as exc:
                    self._emit_stage_error("YouGlish 链接生成", exc)
                    return
            else:
                note_state["youglish"] = True

            self.progress_updated.emit(
                min(100, int(base_progress + per_card)),
                f"Completed {i + 1}/{self.total_items}",
            )
            self.current_index += 1

        if self.total_items == 1:
            self.progress_updated.emit(100, "Completed")

        self._finalize_note_errors()
        self._completed_successfully = True
        self.finished.emit()

    def _apply_speech_generation(
        self,
        note: AnkiNote,
        state: dict[str, Any],
        *,
        base_progress: float,
        per_card: float,
    ) -> tuple[AnkiNote, list[str]]:
        if not self._speech_client or not self.audio_field_mappings:
            for mapping in self.audio_field_mappings:
                state["audio"][mapping] = True
            return note, []

        pending: list[tuple[tuple[str, str], str]] = []
        for prompt_field, audio_field in self.audio_field_mappings:
            mapping_key = (prompt_field, audio_field)
            if state["audio"].get(mapping_key):
                continue
            if prompt_field not in note or audio_field not in note:
                state["audio"][mapping_key] = True
                continue
            prompt_raw = str(note[prompt_field])
            prompt_value = self._prepare_speech_text(prompt_raw)
            if not prompt_value:
                state["audio"][mapping_key] = True
                continue
            pending.append((mapping_key, prompt_value))

        if not pending:
            return note, []

        pending_targets = [audio_field for (_, audio_field), _ in pending]
        note, conflicts = self._check_for_conflicts(
            note,
            "audio",
            pending_targets,
            {field: "[将写入新音频标签]" for field in pending_targets},
        )
        if conflicts:
            decision = self._wait_for_conflict_resolution(note.id, "audio", conflicts)
            if decision == "skip":
                self._update_snapshot_section(note, "audio", pending_targets)
                for mapping_key, _ in pending:
                    state["audio"][mapping_key] = True
                return note, []
            if decision == "abort":
                raise ExternalException(
                    "Speech generation cancelled by user.",
                    code=ErrorCode.GENERIC,
                )

        retry_progress = int(min(99, base_progress + (per_card * 0.75)))
        overwritten_fields: list[str] = []

        for (prompt_field, audio_field), prompt_value in pending:
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
            state["audio"][(prompt_field, audio_field)] = True
            overwritten_fields.append(audio_field)

        return note, overwritten_fields

    def _apply_image_generation(
        self,
        note: AnkiNote,
        state: dict[str, Any],
        *,
        base_progress: float,
        per_card: float,
    ) -> tuple[AnkiNote, list[str]]:
        if not self.image_field_mappings:
            return note, []

        image_client = self._get_image_client()
        configured_model = getattr(image_client.prompt_config, "model", "") or None

        pending: list[tuple[tuple[str, str], str]] = []
        for prompt_field, image_field in self.image_field_mappings:
            mapping_key = (prompt_field, image_field)
            if state["image"].get(mapping_key):
                continue
            if prompt_field not in note or image_field not in note:
                state["image"][mapping_key] = True
                continue
            prompt_value = str(note[prompt_field]).strip()
            if not prompt_value:
                state["image"][mapping_key] = True
                continue
            pending.append((mapping_key, prompt_value))

        if not pending:
            return note, []

        pending_targets = [image_field for (_, image_field), _ in pending]
        note, conflicts = self._check_for_conflicts(
            note,
            "image",
            pending_targets,
            {field: "[将写入新图像]" for field in pending_targets},
        )
        if conflicts:
            decision = self._wait_for_conflict_resolution(note.id, "image", conflicts)
            if decision == "skip":
                self._update_snapshot_section(note, "image", pending_targets)
                for mapping_key, _ in pending:
                    state["image"][mapping_key] = True
                return note, []
            if decision == "abort":
                raise ExternalException(
                    "Image generation cancelled by user.",
                    code=ErrorCode.GENERIC,
                )

        overwritten_fields: list[str] = []
        retry_progress = int(min(99, base_progress + per_card / 2))

        for (prompt_field, image_field), prompt_value in pending:
            def generate(value: str = prompt_value) -> bytes:
                return image_client.generate_image(value, model=configured_model)

            image_bytes = self._run_with_retry(
                generate,
                f"Image generation ({prompt_field}->{image_field})",
                progress_value=retry_progress,
            )
            filename = self._write_image_to_media(note, image_bytes, image_field)
            note[image_field] = f'<img src="{filename}">'
            state["image"][(prompt_field, image_field)] = True
            overwritten_fields.append(image_field)

        return note, overwritten_fields

    def _apply_oaad_links(
        self,
        note: AnkiNote,
        state: dict[str, Any],
        *,
        base_progress: float,
        per_card: float,
    ) -> tuple[AnkiNote, list[str]]:
        if state.get("oaad", False):
            return note, []
        state["oaad"] = True
        if not self._oaad_source_field or not self._oaad_target_field:
            return note, []
        if (
            self._oaad_source_field not in note
            or self._oaad_target_field not in note
        ):
            return note, []
        source_raw = str(note[self._oaad_source_field])
        term = self._prepare_oaad_term(source_raw)
        current_value = str(note[self._oaad_target_field] or "")
        if current_value.strip() and not self._oaad_overwrite:
            return note, []
        base_url = OAAD_HOME_URL
        link = base_url
        if term:
            candidate = self._build_oaad_url(term)
            exists = self._probe_oaad_url(candidate)
            self._log_event(
                "oaad_probe",
                {
                    "note_id": getattr(note, "id", None),
                    "term": term,
                    "candidate": candidate,
                    "exists": exists,
                    "accent": self._oaad_accent,
                },
            )
            link = candidate if exists else base_url
        else:
            self._log_event(
                "oaad_skip_empty_term",
                {"note_id": getattr(note, "id", None), "raw": source_raw},
            )

        note, conflicts = self._check_for_conflicts(
            note,
            "oaad",
            [self._oaad_target_field],
            {self._oaad_target_field: link},
        )
        if conflicts:
            decision = self._wait_for_conflict_resolution(
                note.id,
                "oaad",
                conflicts,
            )
            if decision == "skip":
                self._update_snapshot_section(
                    note,
                    "oaad",
                    [self._oaad_target_field],
                )
                return note, []
            if decision == "abort":
                raise ExternalException(
                    "OAAD 链接写入已取消。",
                    code=ErrorCode.GENERIC,
                )
        progress_hint = int(min(99, base_progress + (per_card * 0.82)))
        self.progress_updated.emit(
            progress_hint,
            "Writing OAAD link...",
        )
        note[self._oaad_target_field] = link
        return note, [self._oaad_target_field]

    def _apply_youglish_links(
        self,
        note: AnkiNote,
        state: dict[str, Any],
        *,
        base_progress: float,
        per_card: float,
    ) -> tuple[AnkiNote, list[str]]:
        if state.get("youglish", False):
            return note, []
        state["youglish"] = True
        if not self._youglish_source_field or not self._youglish_target_field:
            return note, []
        if (
            self._youglish_source_field not in note
            or self._youglish_target_field not in note
        ):
            return note, []
        source_raw = str(note[self._youglish_source_field])
        term = self._prepare_youglish_term(source_raw)
        if not term:
            return note, []
        current_value = str(note[self._youglish_target_field] or "")
        if current_value.strip() and not self._youglish_overwrite:
            return note, []
        link = self._build_youglish_url(term)
        if not link:
            return note, []
        note, conflicts = self._check_for_conflicts(
            note,
            "youglish",
            [self._youglish_target_field],
            {self._youglish_target_field: link},
        )
        if conflicts:
            decision = self._wait_for_conflict_resolution(
                note.id,
                "youglish",
                conflicts,
            )
            if decision == "skip":
                self._update_snapshot_section(
                    note,
                    "youglish",
                    [self._youglish_target_field],
                )
                return note, []
            if decision == "abort":
                raise ExternalException(
                    "YouGlish 链接写入已取消。",
                    code=ErrorCode.GENERIC,
                )
        progress_hint = int(min(99, base_progress + (per_card * 0.9)))
        self.progress_updated.emit(
            progress_hint,
            "Writing YouGlish link...",
        )
        note[self._youglish_target_field] = link
        return note, [self._youglish_target_field]

    def _prepare_oaad_term(self, value: str) -> str:
        text = html.unescape(str(value or ""))
        # strip HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        sanitized = text.replace("::", ":").replace(";", " ").strip()
        sanitized = re.sub(r"\s+", " ", sanitized)
        return sanitized

    def _build_oaad_url(self, term: str) -> str:
        encoded = quote_plus(term.strip())
        if self._oaad_accent == "us":
            return (
                f"https://www.oxfordlearnersdictionaries.com/us/definition/american_english/"
                f"{encoded}?q={encoded}"
            )
        return (
            f"https://www.oxfordlearnersdictionaries.com/definition/english/{encoded}"
            f"?q={encoded}"
        )

    def _probe_oaad_url(self, url: str) -> bool:
        try:
            req = urllib_request.Request(url, method="GET")
            req.add_header("User-Agent", "anki-ai-field-generator/oaad-probe")
            with urllib_request.urlopen(req, timeout=3) as resp:  # nosec B310
                status = getattr(resp, "status", 200)
                self._log_event("oaad_probe_status", {"url": url, "status": status})
                return 200 <= status < 400
        except urllib_error.HTTPError as exc:
            self._log_event("oaad_probe_http_error", {"url": url, "code": exc.code})
            if exc.code == 404:
                return False
            return False
        except Exception as err:
            self._log_event("oaad_probe_error", {"url": url, "error": str(err)})
            return False

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

    def _prepare_youglish_term(self, value: str) -> str:
        if not value:
            return ""
        text = html.unescape(str(value))
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _build_youglish_url(self, term: str) -> str:
        normalized = (term or "").strip()
        if not normalized:
            return ""
        accent = self._youglish_accent if self._youglish_accent in {"us", "uk", "aus"} else "us"
        encoded = quote_plus(normalized)
        return f"https://youglish.com/pronounce/{encoded}/english?accent={accent}"

    @staticmethod
    def _get_bool_setting(settings: QSettings, name: str, *, default: bool = False) -> bool:
        value = settings.value(name, defaultValue=default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        try:
            return bool(int(value))
        except Exception:
            return bool(value)

    def _initialize_note_progress(self) -> None:
        for note in self.notes:
            self._note_progress[note.id] = self._create_note_state()

    def _create_note_state(self) -> dict[str, Any]:
        text_fields_present = bool(self.note_fields)
        image_state = {
            mapping: (not self._enable_image_generation)
            for mapping in self.image_field_mappings
        }
        audio_state = {
            mapping: (not self._enable_audio_generation)
            for mapping in self.audio_field_mappings
        }
        return {
            "text": (not self._enable_text_generation) or not text_fields_present,
            "image": image_state,
            "audio": audio_state,
            "oaad": (
                not self._enable_oaad
                or not self._oaad_source_field
                or not self._oaad_target_field
            ),
            "youglish": (
                not self._enable_youglish
                or not self._youglish_source_field
                or not self._youglish_target_field
            ),
        }

    def _build_initial_snapshots(self) -> dict[int, dict[str, dict[str, str]]]:
        snapshots: dict[int, dict[str, dict[str, str]]] = {}
        for note in self.notes:
            note_snap = {
                "text": {
                    field: note[field] if field in note else ""
                    for field in self.note_fields
                },
                "image": {
                    target: note[target] if target in note else ""
                    for _, target in self.image_field_mappings
                },
                "audio": {
                    target: note[target] if target in note else ""
                    for _, target in self.audio_field_mappings
                },
                "oaad": {
                    self._oaad_target_field: (
                        note[self._oaad_target_field]
                        if self._oaad_target_field in note
                        else ""
                    )
                }
                if self._oaad_target_field
                else {},
                "youglish": {
                    self._youglish_target_field: (
                        note[self._youglish_target_field]
                        if self._youglish_target_field in note
                        else ""
                    )
                }
                if self._youglish_target_field
                else {},
            }
            snapshots[note.id] = note_snap
        return snapshots

    @staticmethod
    def _parse_text_rows(
        raw_entries: Optional[str],
        default_keys: list[str],
        default_fields: list[str],
    ) -> list[tuple[str, str, bool]]:
        rows: list[tuple[str, str, bool]] = []
        if raw_entries:
            try:
                data = json.loads(raw_entries)
                for entry in data:
                    if not isinstance(entry, dict):
                        continue
                    key = str(entry.get("key", "")).strip()
                    field = str(entry.get("field", "")).strip()
                    enabled = bool(entry.get("enabled", True))
                    if key or field:
                        rows.append((key, field, enabled))
            except (json.JSONDecodeError, TypeError):
                rows = []
        if not rows and default_keys and default_fields and len(default_keys) == len(default_fields):
            rows = [
                (str(key).strip(), str(field).strip(), True)
                for key, field in zip(default_keys, default_fields)
                if str(key).strip() or str(field).strip()
            ]
        return rows

    @staticmethod
    def _decode_mapping_entry(entry: str) -> tuple[str, str, bool]:
        if not isinstance(entry, str):
            return "", "", False
        base = entry
        enabled = True
        if "::" in entry:
            base, flag = entry.rsplit("::", 1)
            enabled = flag.strip().lower() not in {"0", "false"}
        if IMAGE_MAPPING_SEPARATOR not in base:
            return "", "", False
        prompt, target = [
            part.strip() for part in base.split(IMAGE_MAPPING_SEPARATOR, 1)
        ]
        return prompt, target, enabled

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
        if self._image_client is not None:
            return self._image_client

        provider = self._image_provider
        if provider not in {"", "gemini", "custom"}:
            raise ExternalException(
                f"Image provider '{provider}' is not supported yet.",
                code=ErrorCode.INVALID_INPUT,
            )

        api_key = self._load_image_api_key()
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
        self._image_client = GeminiClient(config)
        return self._image_client

    def _load_image_api_key(self) -> str:
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
            if self.isInterruptionRequested():
                raise ExternalException(
                    "Operation cancelled by user.",
                    code=ErrorCode.GENERIC,
                )
            try:
                return operation()
            except ExternalException as exc:
                policy = self._retry_policies.get(exc.code)
                if policy and exc.code == ErrorCode.RATE_LIMIT:
                    # propagate to allow scheduler/outer layer to pause
                    exc.attempts = attempt
                    exc.retry_policy = policy
                    raise
                if policy and attempt < policy.max_attempts:
                    group = max(0, (attempt - 1) // 10)
                    wait_seconds = policy.wait_seconds * (2 ** group)
                    attempt_text = (
                        f" attempt {attempt}/{policy.max_attempts}"
                        if policy.max_attempts
                        else ""
                    )
                    message = (
                        f"{stage_label} failed ({exc.code.value}){attempt_text}. "
                        f"Retrying in {int(wait_seconds)}s..."
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

    def _emit_stage_error(self, stage_label: str, exc: ExternalException) -> None:
        self._had_error = True
        message = self._format_error_message(stage_label, exc)
        self._log_event(message, exc=exc)
        self.error.emit(message)

    def _emit_plain_error(self, text: str) -> None:
        self._had_error = True
        self._log_event(text)
        self.error.emit(text)

    def _check_for_conflicts(
        self,
        note: AnkiNote,
        section: str,
        fields: Iterable[str],
        generated_values: Optional[dict[str, str]] = None,
    ) -> tuple[AnkiNote, dict[str, dict[str, str]]]:
        latest = self._refresh_note_reference(note)
        snapshot_section = (
            self._snapshots.get(note.id, {}).get(section, {})
            if note.id in self._snapshots
            else {}
        )
        conflicts: dict[str, dict[str, str]] = {}
        for field in fields:
            original_value = snapshot_section.get(field, "")
            current_value = latest[field] if field in latest else ""
            if current_value != original_value:
                generated_value = (
                    generated_values.get(field, "")
                    if generated_values is not None
                    else ""
                )
                conflicts[field] = {
                    "original": original_value,
                    "current": current_value,
                    "generated": generated_value,
                }
        return latest, conflicts

    def _wait_for_conflict_resolution(
        self,
        note_id: int,
        section: str,
        conflicts: dict[str, dict[str, str]],
    ) -> str:
        self._active_conflict_note_id = note_id
        self._current_conflict_decision = None
        self._conflict_event.clear()
        payload = {
            "note_id": note_id,
            "section": section,
            "fields": conflicts,
        }
        self.conflict_detected.emit(payload)
        while not self._conflict_event.wait(0.1):
            if self.isInterruptionRequested():
                self._current_conflict_decision = "abort"
                self._conflict_event.set()
                break
        decision = self._current_conflict_decision or "abort"
        self._active_conflict_note_id = None
        return decision

    def _on_conflict_decision(self, note_id: int, decision: str) -> None:
        if self._active_conflict_note_id != note_id:
            return
        self._current_conflict_decision = decision
        self._conflict_event.set()

    def _update_snapshot_section(
        self,
        note: AnkiNote,
        section: str,
        fields: Iterable[str],
    ) -> None:
        section_snap = self._snapshots.setdefault(note.id, {}).setdefault(section, {})
        for field in fields:
            section_snap[field] = note[field] if field in note else ""

    def _commit_note_sections(
        self,
        note: AnkiNote,
        sections: Iterable[tuple[str, Iterable[str]]],
    ) -> None:
        sections_list: list[tuple[str, list[str]]] = []
        for section, fields in sections:
            field_list = [field for field in fields if field]
            if field_list:
                sections_list.append((section, field_list))
        if not sections_list:
            return
        collection = getattr(note, "col", None)
        if collection is None:
            return
        self._with_collection_retry(
            lambda: collection.update_note(note),
            "写入笔记",
            progress_value=self._current_progress_value(),
        )
        for section, fields in sections_list:
            self._update_snapshot_section(note, section, fields)

    def _refresh_note_reference(
        self,
        note: AnkiNote,
        *,
        progress_value: Optional[int] = None,
    ) -> AnkiNote:
        collection = getattr(note, "col", None)
        if collection is None:
            return note

        def _fetch_note() -> Optional[AnkiNote]:
            return collection.get_note(note.id)

        refreshed = self._with_collection_retry(
            _fetch_note,
            "同步笔记",
            progress_value=progress_value,
        )
        return refreshed or note

    def _current_progress_value(self) -> int:
        if not self.total_items:
            return 0
        percentage = (self.current_index / self.total_items) * 100
        return max(0, min(99, int(percentage)))

    def _with_collection_retry(
        self,
        operation: Callable[[], Any],
        stage_label: str,
        *,
        progress_value: Optional[int] = None,
    ) -> Any:
        attempt = 0
        while True:
            try:
                return operation()
            except ExternalException:
                raise
            except Exception as exc:
                if not self._is_collection_lock_error(exc):
                    raise
                attempt += 1
                self._log_event(
                    f"{stage_label} waiting for collection lock release (attempt {attempt}).",
                    exc=exc,
                )
                if attempt >= self._collection_retry_limit:
                    raise ExternalException(
                        "Anki 正在执行其它操作（例如添加或同步）。待其完成后再重试。",
                        code=ErrorCode.CONNECTION,
                    ) from exc
                wait_seconds = self._collection_retry_delay
                progress = (
                    progress_value
                    if progress_value is not None
                    else self._current_progress_value()
                )
                self.progress_updated.emit(
                    progress,
                    f"{stage_label} 暂停，正在等待 Anki 完成其它操作…",
                )
                QThread.msleep(int(wait_seconds * 1000))
        # unreachable

    def _is_collection_lock_error(self, exc: Exception) -> bool:
        if isinstance(exc, (BackendError, DBError)):
            message = str(exc).lower()
            return any(fragment in message for fragment in COLLECTION_LOCK_FRAGMENTS)
        if isinstance(exc, sqlite3.OperationalError):
            return "locked" in str(exc).lower()
        message = str(exc).lower()
        return bool(message) and any(
            fragment in message for fragment in COLLECTION_LOCK_FRAGMENTS
        )

    def _log_event(
        self,
        message: str,
        data: Optional[dict[str, Any]] = None,
        *,
        exc: Optional[BaseException] = None,
    ) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = f" {data}" if data else ""
        entry_lines = [f"[{timestamp}] {message}{payload}"]
        if exc is not None:
            entry_lines.append(f"Exception: {exc}")
        entry = " ".join(entry_lines) + "\n"
        try:
            with LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(entry)
                if exc is not None:
                    traceback.print_exception(
                        exc.__class__,
                        exc,
                        exc.__traceback__,
                        file=handle,
                    )
        except Exception:
            pass

    def _should_skip_note_error(self, stage: str, exc: ExternalException) -> bool:
        if stage != "text":
            return False
        return self._is_json_parse_error(exc)

    def _record_note_error(
        self,
        note: AnkiNote,
        stage_label: str,
        exc: ExternalException,
    ) -> None:
        note_id = getattr(note, "id", "unknown")
        message = (
            f"笔记 {note_id} 在 {stage_label} 阶段失败，已跳过：{exc}"
        )
        self._note_errors.append(message)
        self._log_event(message, exc=exc)
        self.progress_updated.emit(
            min(99, max(0, self._current_progress_value())),
            message,
        )

    def _finalize_note_errors(self) -> None:
        if not self._note_errors:
            self.note_error_summary = ""
            return
        summary = (
            f"处理完成，但有 {len(self._note_errors)} 张笔记失败并被跳过。"
            f"详情请查看 {LOG_FILE.name}。"
        )
        self.note_error_summary = summary
        self._log_event(summary)

    def _is_json_parse_error(self, exc: ExternalException) -> bool:
        if exc.code != ErrorCode.BAD_REQUEST:
            return False
        text = str(exc).lower()
        markers = (
            "could not parse json",
            "did not return valid json",
            "unexpected openai-style response shape",
            "response must be a json object",
            "returned invalid json",
        )
        return any(marker in text for marker in markers)

    def _report_json_retry(
        self,
        note: AnkiNote,
        attempt: int,
        total_attempts: int,
        exc: ExternalException,
    ) -> None:
        note_id = getattr(note, "id", "unknown")
        message = (
            f"笔记 {note_id} 文本生成返回非法 JSON，正在重试 "
            f"{attempt}/{total_attempts - 1} ..."
        )
        self._log_event(message, exc=exc)
        self.progress_updated.emit(
            min(99, max(0, self._current_progress_value())),
            message,
        )
        QThread.msleep(250)
