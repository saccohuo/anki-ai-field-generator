"""
Factory that returns the corrent LLM Client configurations.
"""

from .llm_client import LLMClient
from .note_processor import NoteProcessor
from .openai_client import OpenAIClient
from .openai_ui import OpenAIDialog
from .prompt_config import PromptConfig
from .progress_bar import ProgressDialog
from .settings import get_settings
from .user_base_dialog import UserBaseDialog


class ClientFactory:
    """
    Factory that returns the corrent LLM Client configurations.
    """

    def __init__(
        self,
    ):
        # TODO: make this an actual setting
        self.client_name = "OpenAI"
        self.app_settings = get_settings(self.client_name)

    def get_client(self) -> LLMClient:
        """
        Factory method that returns the LLM Client implementation.
        Add an implementation for each Client you add.
        """
        if self.client_name == "OpenAI":
            prompt_config = PromptConfig(self.app_settings)
            llm_client = OpenAIClient(prompt_config)
            return llm_client
        raise NotImplementedError(f"No LLM client implemented for {self.client_name}")

    def get_dialog(self) -> UserBaseDialog:
        """
        Factory method that returns the settings dialog for the user for each LLM.
        Client. Add an implementation for each Client you add.
        """
        if self.client_name == "OpenAI":
            return OpenAIDialog(self.app_settings)
        raise NotImplementedError(
            f"No user settings dialog implemented for {self.client_name}"
        )

    def show(self, browser):
        """
        Displays the user settings UI.
        """
        notes = [
            browser.mw.col.get_note(note_id) for note_id in browser.selectedNotes()
        ]
        self.get_dialog().show(
            notes, lambda: self.on_submit(browser=browser, notes=notes)
        )

    def on_submit(self, browser, notes):
        """
        Called once the user confirms the card modifications.
        This also refreshes the settings and the LLM client, as the user may have
        changed them.
        """
        # TODO: refresh settings and client name, somehow
        note_processor = NoteProcessor(notes, self.get_client(), self.app_settings)
        dialog = ProgressDialog(note_processor)
        dialog.exec()
        browser.mw.reset()
