from anki.notes import Note as AnkiNote
from aqt.qt import QSettings

from .openai_client import OpenAIClient
from .prompt_config import PromptConfig
from .settings import SettingsNames


class NoteProcessor:
    """
    Stores the relevant information from a note that will be sent to GPT for modification.
    """

    def __init__(
        self,
        prompt_config: PromptConfig,
        notes: list[AnkiNote],
        client: OpenAIClient,
        settings: QSettings,  # might be cleaner to pass in the fields we need directly, not sure
    ):
        self.prompt_config: PromptConfig = prompt_config
        self.notes = notes
        self.client = client
        self.note_fields = settings.value(
            SettingsNames.DESTINATION_FIELD_SETTING_NAME, type="QStringList"
        )
        self.response_keys = settings.value(
            SettingsNames.RESPONSE_KEYS_SETTING_NAME, type="QStringList"
        )

    def process(self, missing_field_is_error=False):
        """
        Processes all notes sequentially, by calling the LLM client.
        """
        for i, note in enumerate(self.notes):
            # TODO: UI
            print(f"Processing note {i}")
            prompt = self.get_user_prompt(note, missing_field_is_error)
            response = self.client.call([prompt])
            print(f"Response: {response}")
            for note_field, response_key in zip(self.note_fields, self.response_keys):
                note[note_field] = response[0][response_key]
            note.col.update_note(note)

    def fill_string_with_note_fields(
        self, s: str, note: AnkiNote, missing_field_is_error=False
    ) -> str:
        """
        Replaces any keys in {braces} in the string with actual values from the Note.
        Substitutes a blank string if the Note did not have the corresponding key.
        """

        class DefaultDict(dict):
            """
            Replaces missing key with blank.
            """

            def __missing__(self, key):
                if missing_field_is_error:
                    raise RuntimeError(f"NoteID {note.id} does not have field {key}.")
                return ""

        return s.format_map(DefaultDict(dict(zip(note.keys(), note.values()))))

    def get_user_prompt(self, note: AnkiNote, missing_field_is_error=False) -> str:
        """
        Creates the prompt by filling in fields from the Note.
        """
        return self.fill_string_with_note_fields(
            self.prompt_config.user_prompt, note, missing_field_is_error
        )
