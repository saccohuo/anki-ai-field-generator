from typing import Optional

import anki.cards
import anki.notes
from aqt import mw

from .note_info import NoteInfo
from .openai_client import OpenAIClient
from .prompt_config import PromptConfig


class FutureNotes:
    """
    Stores the next N notes to send a batch request to GPT.
    This improves performance and reduces cost and rate limiting.
    """

    def __init__(
        self,
        openai_client: OpenAIClient,
        prompt_config: PromptConfig,
        num_notes_to_store: int = 5,
    ):
        self.erase_past_notes = False
        self.client = openai_client
        self.num_notes_to_store = num_notes_to_store
        self.prompt_config = prompt_config
        self.note_infos = {}

    def has_note_id(self, id: anki.notes.NoteId) -> bool:
        return id in self.note_infos

    def has_note(self, note: anki.notes.Note) -> bool:
        return self.has_note_id(note.id)

    def get_note_info(self, note: anki.notes.Note) -> Optional[NoteInfo]:
        if self.has_note(note):
            return self.note_infos[note.id]
        else:
            # TODO: improvement: once the last note has been accessed we could read the next 5 notes
            # on a background thread, to avoid blocking the UI and improve performance
            self.fetch_future_notes()
            if self.has_note(note):
                return self.note_infos[note.id]
        return None

    def fetch_future_notes(self) -> None:
        if self.erase_past_notes:
            self.note_infos = {}
        scheduler = mw.col.sched
        scheduler.getCard()
        next_cards = scheduler.get_queued_cards(
            fetch_limit=self.num_notes_to_store
        ).cards
        new_note_list: list[NoteInfo] = []
        for i in range(min(self.num_notes_to_store, len(next_cards))):
            next_card = next_cards[i].card
            card = anki.cards.Card(mw.col)
            card._load_from_backend_card(next_card)
            note = card.note()
            if not self.has_note(note):
                note_info = NoteInfo(self.prompt_config)
                note_info.load_note(note)
                self.note_infos[note.id] = note_info
                if note_info.is_loaded_successfully():
                    new_note_list.append(note_info)
        if new_note_list:
            updated_note_datas = self.client.modify_sentence_and_translate(
                new_note_list
            )
            # Trim to make sure we didn't get more responses than we have notes - sometimes ChatGPT is a little overzealous.
            updated_note_datas = updated_note_datas[: len(new_note_list)]
            for i, updated_data in enumerate(updated_note_datas):
                new_note_list[i].add_updates(updated_data)
