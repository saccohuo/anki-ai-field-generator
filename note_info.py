from enum import Enum

from .prompt_config import PromptConfig

class LoadStatus(Enum):
    FAILURE = 0
    SUCCESS = 1
    UNKNOWN = 2


class NoteInfo:
    """
    Stores the relevant information from a note that will be sent to GPT for modification.
    """
    def __init__(self, prompt_config: PromptConfig):
        self.load_status: LoadStatus = LoadStatus.UNKNOWN
        self.prompt_config: PromptConfig = prompt_config
        self.field_dict = {}
        self.updates_dict = {}

    def load_note(self, note) -> LoadStatus:
        # TODO: it's possible some fields are required and some are optional - we should support that
        for field_name in self.prompt_config.required_fields:
            if field_name in note and note[field_name].strip():
                self.field_dict[field_name] = note[field_name]
            else:
                # If any field can't be loaded, early exit
                self.load_status = LoadStatus.FAILURE
                return self.load_status

        self.load_status = LoadStatus.SUCCESS
        return self.load_status

    def add_updates(self, updates: dict) -> None:
        """
        Parameters:
        updates (dict): The keys are the field filter names, and the values are the data.
        """
        self.updates_dict = updates

    def fill_string_with_note_fields(self, s: str) -> str:
        """
        Replaces any keys in {braces} in the string with actual values from the Note. Substitutes a blank string if the Note
        did not have the corresponding key.
        """
        class DefaultDict(dict):
            def __missing__(self, key):
                return ''
        return s.format_map(DefaultDict(self.field_dict))

    def get_user_prompt(self) -> str:
        return self.fill_string_with_note_fields(self.prompt_config.user_prompt)

    def is_loaded_successfully(self) -> bool:
        return self.load_status == LoadStatus.SUCCESS
