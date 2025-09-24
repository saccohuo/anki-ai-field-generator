import json
from typing import Any

import requests

from .exceptions import ErrorCode, ExternalException
from .llm_client import LLMClient
from .prompt_config import PromptConfig


class CustomLLMClient(LLMClient):
    """Generic HTTP client for user-specified LLM endpoints."""

    SERVICE_NAME = "Custom"

    def __init__(self, prompt_config: PromptConfig):
        self._prompt_config = prompt_config

    @property
    def prompt_config(self) -> PromptConfig:
        return self._prompt_config

    def call(self, prompts: list[str]) -> dict[str, Any]:
        if not prompts:
            raise ExternalException(
                "Empty list of prompts given",
                code=ErrorCode.INVALID_INPUT,
            )

        endpoint = (self.prompt_config.endpoint or "").strip()
        if not endpoint:
            raise ExternalException(
                "Custom endpoint is missing. Please update the settings and try again.",
                code=ErrorCode.INVALID_INPUT,
            )

        headers = {"Content-Type": "application/json"}
        if self.prompt_config.api_key:
            headers["Authorization"] = f"Bearer {self.prompt_config.api_key}"

        payload: dict[str, Any] = {
            "messages": [],
        }
        if self.prompt_config.model:
            payload["model"] = self.prompt_config.model
        if self.prompt_config.system_prompt:
            payload["messages"].append(
                {"role": "system", "content": self.prompt_config.system_prompt}
            )
        payload["messages"].extend({"role": "user", "content": prompt} for prompt in prompts)

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        except requests.exceptions.RequestException as exc:
            raise ExternalException(
                "Could not reach the custom endpoint. Verify the URL and network access.",
                code=ErrorCode.CONNECTION,
            ) from exc

        if response.status_code >= 400:
            raise ExternalException(
                "Custom endpoint returned an error: "
                f"{response.status_code} {response.reason}\n{response.text}",
                code=ErrorCode.BAD_REQUEST,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalException(
                "Custom endpoint did not return valid JSON. Ensure the response body "
                "is a JSON object that matches your configured keys.",
                code=ErrorCode.BAD_REQUEST,
            ) from exc

        if isinstance(data, dict) and "choices" in data:
            try:
                message_content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise ExternalException(
                    "Unexpected OpenAI-style response shape returned by the custom endpoint.",
                    code=ErrorCode.BAD_REQUEST,
                ) from exc
            try:
                return json.loads(message_content)
            except json.JSONDecodeError as exc:
                raise ExternalException(
                    "Could not parse JSON from the message content returned by the endpoint.",
                    code=ErrorCode.BAD_REQUEST,
                ) from exc

        if not isinstance(data, dict):
            raise ExternalException(
                "Custom endpoint response must be a JSON object mapping keys to values.",
                code=ErrorCode.BAD_REQUEST,
            )

        return data
