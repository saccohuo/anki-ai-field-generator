import json
import requests

from .exceptions import ExternalException
from .response_utils import get_response_format
from .prompt_config import PromptConfig


class OpenAIClient:
    def __init__(self, config: PromptConfig):
        self.config = config
        self.debug = False

    def call(self, prompts: list[str]) -> list[dict]:
        if not prompts:
            raise Exception("Empty list of prompts given")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        # This supports multiple prompts (newline-separated) if we switch back to batch processing.
        user_input = "\n\n".join(prompts)
        if self.debug:
            print(f"Content String: {user_input}\n")
            print(f"System Prompt: {self.config.system_prompt}\n")
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": self.config.system_prompt},
                {"role": "user", "content": user_input},
            ],
            "response_format": get_response_format(self.config.response_keys),
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
        except requests.exceptions.ConnectionError as exc:
            raise ExternalException(
                "ConnectionError, could not access the OpenAI service.\n"
                "Are you sure you have an internet connection?"
            ) from exc

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            if response.status_code == 401:
                raise ExternalException(
                    'Received an "Unauthorized" response; your API key is probably invalid.'
                ) from exc
            if response.status_code == 429:
                raise ExternalException(
                    'Received a "429 Client Error: Too Many Requests" response; you might be rate limited to 3 requests per minute.'
                ) from exc
            raise ExternalException(
                f"Error: {response.status_code} {response.reason}"
            ) from exc

        return self.parse_json_response(
            response=response.json(),
            expected_length=len(prompts),
            user_input=user_input,
        )

    def parse_json_response(
        self, response, expected_length: int, user_input: str = None
    ) -> list[dict]:
        message_content = response["choices"][0]["message"]["content"]
        results = json.loads(message_content)["results"]
        if len(results) != expected_length:
            print(
                (
                    f"WARNING: Results size of {len(results)} didn't match input length of {expected_length}.\n"
                    "This is normally just ChatGPT being weird and not doing what you told it to do in the prompt.\n"
                    f'The "content" passed to ChatGPT was:\n{user_input}\nand the response was:\n{message_content}'
                )
            )
        if self.debug:
            for i, sentence in enumerate(results):
                print(f"Result {i}: {sentence}")
        return results
