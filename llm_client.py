"""Generic interface for a LLM client."""

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """
    Generic interface for a LLM client.
    """

    @abstractmethod
    def call(self, prompts: list[str]) -> list[dict]:
        """
        Accepts a list of prompts, and returns a list of responses, one per prompt.
        The responses are a list of key-value pairs.
        """
