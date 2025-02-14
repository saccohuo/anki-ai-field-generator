from anki.notes import Note as AnkiNote

from .openai_client import OpenAIClient
from .prompt_config import PromptConfig


class NoteProcessor:
    """
    Stores the relevant information from a note that will be sent to GPT for modification.
    """

    def __init__(
        self, prompt_config: PromptConfig, notes: list[AnkiNote], client: OpenAIClient
    ):
        self.prompt_config: PromptConfig = prompt_config
        self.notes = notes
        self.client = client

    def process(self, missing_field_is_error=False):
        for i, note in enumerate(self.notes):
            # TODO: UI
            print(f"Processing note {i}")
            prompt = self.get_user_prompt(note, missing_field_is_error)
            response = self.client.call([prompt])
            # TODO: save it to the note
            print(f"Response: {response}")

    def fill_string_with_note_fields(
        self, s: str, note: AnkiNote, missing_field_is_error=False
    ) -> str:
        """
        Replaces any keys in {braces} in the string with actual values from the Note. Substitutes a blank string if the Note
        did not have the corresponding key.
        """

        class DefaultDict(dict):
            def __missing__(self, key):
                if missing_field_is_error:
                    raise RuntimeError(f"NoteID {note.id} does not have field {key}.")
                return ""

        return s.format_map(DefaultDict(dict(zip(note.keys(), note.values()))))

    def get_user_prompt(self, note: AnkiNote, missing_field_is_error=False) -> str:
        return self.fill_string_with_note_fields(
            self.prompt_config.user_prompt, note, missing_field_is_error
        )
