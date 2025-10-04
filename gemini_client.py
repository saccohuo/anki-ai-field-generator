"""Client for interacting with the Gemini API."""

from __future__ import annotations

import base64
import json
import time
from typing import Optional

import requests

try:
    from .exceptions import ErrorCode, ExternalException
    from .llm_client import LLMClient
    from .prompt_config import PromptConfig
    from .response_utils import get_gemini_response_format
except ImportError:  # pragma: no cover - allow running outside package context
    from exceptions import ErrorCode, ExternalException
    from llm_client import LLMClient
    from prompt_config import PromptConfig
    from response_utils import get_gemini_response_format


class GeminiClient(LLMClient):
    SERVICE_NAME = "Google Gemini"
    IMAGE_MODEL = "gemini-2.5-flash-image"
    IMAGE_MIME_TYPE = "image/png"

    def __init__(self, prompt_config: PromptConfig):
        super(LLMClient, self).__init__()
        self._prompt_config = prompt_config
        self.debug = False
        self.next_request_time = 0
        self.max_retries = 5

    @property
    def prompt_config(self) -> PromptConfig:
        return self._prompt_config

    def call(self, prompts: list[str]) -> dict:
        if not prompts:
            raise Exception("Empty list of prompts given")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.prompt_config.model}:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": self.prompt_config.api_key}

        user_input = "\n\n".join(prompts)

        if self.debug:
            print(f"Content String: {user_input}\n")
            print(f"System Prompt: {self.prompt_config.system_prompt}\n")

        contents = [{"role": "user", "parts": [{"text": user_input}]}]

        data = {
            "contents": contents,
            "generationConfig": get_gemini_response_format(
                self.prompt_config.response_keys
            ),
        }
        data["generationConfig"]["maxOutputTokens"] = 1024

        if (
            hasattr(self.prompt_config, "system_prompt")
            and self.prompt_config.system_prompt
        ):
            system_instruction = {"parts": [{"text": self.prompt_config.system_prompt}]}
            data["systemInstruction"] = system_instruction

        for i in range(self.max_retries):
            self.wait_if_needed()
            try:
                response = requests.post(
                    url, headers=headers, params=params, json=data, timeout=30
                )
            except requests.exceptions.ConnectionError as exc:
                raise ExternalException(
                    f"ConnectionError, could not access the {GeminiClient.SERVICE_NAME} service."
                    "\nAre you sure you have an internet connection?",
                    code=ErrorCode.CONNECTION,
                ) from exc
            try:
                response.raise_for_status()
                self.next_request_time = 0
                return self.parse_json_response(response=response.json())
            except requests.exceptions.HTTPError as exc:
                if response.status_code == 401:
                    raise ExternalException(
                        'Received an "Unauthorized" response; your API key is probably invalid.',
                        code=ErrorCode.UNAUTHORIZED,
                    ) from exc
                if response.status_code == 429:
                    retry_after_time = 4 * (2**i)
                    self.next_request_time = time.time() + retry_after_time + 0.5
                    if i == self.max_retries - 1:
                        raise ExternalException(
                            'Received a "429 Client Error: Too Many Requests" response.'
                            f" And did not succeed after {self.max_retries} retries."
                            "The Gemini error is:"
                            f"{response.status_code} {response.reason}\n{response.text}",
                            code=ErrorCode.RATE_LIMIT,
                        ) from exc
                if response.status_code == 400:
                    error_details = response.json().get("error", {})
                    error_message = error_details.get("message", "Bad Request")
                    raise ExternalException(
                        f"Bad Request (400): {error_message}\n"
                        "This might be due to invalid model name, malformed request, or unsupported features.",
                        code=ErrorCode.BAD_REQUEST,
                    ) from exc
                raise ExternalException(
                    f"Error: {response.status_code} {response.reason}\n{response.text}",
                    code=ErrorCode.GENERIC,
                ) from exc
        raise ExternalException("Code is unreachable.")

    def wait_if_needed(self) -> None:
        """Wait until the global `next_request_time` allows a new request."""
        now = time.time()
        if now < self.next_request_time:
            wait_time = self.next_request_time - now
            print(f"Waiting {wait_time:.2f} seconds before the next request.")
            time.sleep(wait_time)

    def generate_image(self, prompt: str, model: Optional[str] = None) -> bytes:
        if not prompt:
            raise ExternalException("Image prompt is empty.", code=ErrorCode.INVALID_INPUT)

        if not self.prompt_config.api_key:
            raise ExternalException(
                "Gemini API key is required for image generation.",
                code=ErrorCode.MISSING_CREDENTIALS,
            )

        raw_model = (
            model
            or getattr(self.prompt_config, "model", "")
            or self.IMAGE_MODEL
        )
        image_model = raw_model.strip()
        if image_model.startswith("models/"):
            image_model = image_model.split("/", 1)[1]

        base_endpoint = (getattr(self.prompt_config, "endpoint", "") or "").strip()
        if base_endpoint:
            base = base_endpoint.rstrip("/")
            if base.endswith("/models"):
                url = f"{base}/{image_model}:generateContent"
            else:
                url = f"{base}/models/{image_model}:generateContent"
        else:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{image_model}:generateContent"
            )
        headers = {"Content-Type": "application/json"}
        params = {"key": self.prompt_config.api_key}
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE",
                },
            ],
        }

        try:
            response = requests.post(
                url, headers=headers, params=params, json=body, timeout=60
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise ExternalException(
                "Could not connect to Gemini image generation service.",
                code=ErrorCode.CONNECTION,
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status = response.status_code
            detail = response.text
            if status == 401:
                message = "Gemini image generation returned Unauthorized; check your API key."
                code = ErrorCode.UNAUTHORIZED
            elif status == 429:
                message = "Gemini image generation hit a rate limit. Please try again later."
                code = ErrorCode.RATE_LIMIT
            else:
                message = f"Gemini image generation failed with {status}: {response.reason}."
                code = ErrorCode.BAD_REQUEST if 400 <= status < 500 else ErrorCode.GENERIC
            raise ExternalException(f"{message}\n{detail}", code=code) from exc

        payload = response.json()
        try:
            parts = payload["candidates"][0]["content"].get("parts", [])
        except (KeyError, IndexError) as exc:
            raise ExternalException(
                "Gemini image generation response did not include image data.",
                code=ErrorCode.IMAGE_MISSING_DATA,
            ) from exc

        encoded = None
        for part in parts:
            if isinstance(part, dict) and "inlineData" in part:
                encoded = part["inlineData"].get("data")
                if encoded:
                    break

        if not encoded:
            raise ExternalException(
                "Gemini image generation response did not include inline image data.",
                code=ErrorCode.IMAGE_MISSING_DATA,
            )

        try:
            return base64.b64decode(encoded)
        except (base64.binascii.Error, ValueError) as exc:
            raise ExternalException(
                "Failed to decode Gemini image data.",
                code=ErrorCode.IMAGE_DECODE,
            ) from exc

    def parse_json_response(self, response) -> dict:
        if self.debug:
            print(f"Full response: {json.dumps(response, indent=2)}")

        if not response or "candidates" not in response or not response["candidates"]:
            raise ExternalException(
                "Gemini API response is missing 'candidates'.",
                code=ErrorCode.BAD_REQUEST,
            )

        candidate = response["candidates"][0]
        if (
            "content" not in candidate
            or "parts" not in candidate["content"]
            or not candidate["content"]["parts"]
        ):
            raise ExternalException(
                "Gemini API response candidate is missing 'content' or 'parts'."
            )

        message_content = candidate["content"]["parts"][0].get("text")
        try:
            return json.loads(message_content)
        except json.JSONDecodeError as exc:
            raise ExternalException(
                f"Failed to parse JSON from Gemini response: {exc}. Raw content: {message_content}"
            ) from exc
