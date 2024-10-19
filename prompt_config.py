import re

from .settings import Settings


class PromptConfig:
    """
    Stores all the user configuration needed to create a prompt and parse the response
    """
    def __init__(self, settings: Settings):
            self.settings = settings
            if self.settings:
                self.settings.on_change.connect(self._load_settings)
                self._load_settings()

    @classmethod
    def create_test_instance(cls, api_key, system_prompt, user_prompt, response_keys):
         '''For testing only'''
         obj = cls(None)

         obj.api_key = api_key
         obj.system_prompt = system_prompt
         obj.user_prompt = user_prompt
         obj.response_keys = [key.strip() for key in response_keys.split(",")]
         obj.required_fields = obj._extract_text_between_braces(obj.user_prompt)
         return obj


    def _load_settings(self) -> None:
        self.api_key: str = self.settings.get_api_key()
        self.system_prompt: str = self.settings.get_system_prompt()
        self.user_prompt: str = self.settings.get_user_prompt()
        self.response_keys: list[str] = [key.strip() for key in self.settings.get_response_keys().split(",")]
        self.required_fields: list[str] = self._extract_text_between_braces(self.user_prompt)

    def _extract_text_between_braces(self, input_string):
        # Regular expression to match content between braces { }
        pattern = r"\{(.*?)\}"
        matches = re.findall(pattern, input_string)
        # Remove blank matches
        return [m for m in matches if m]
