import json
import requests

from .exceptions import ExternalException
from .note_info import NoteInfo
from .response_utils import get_response_format
from .prompt_config import PromptConfig


class OpenAIClient:
    def __init__(self, config: PromptConfig):
        self.config = config
        self.debug = False

    def modify_sentence_and_translate(self, note_infos: list[NoteInfo]) -> list[dict]:
        if not note_infos:
            raise Exception("Note info list should not be empty")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }
        user_input = "\n\n".join([note.get_user_prompt() for note in note_infos])
        if self.debug:
            print(f"Content String: {user_input}\n")
            print(f"System Prompt: {self.config.system_prompt}\n")
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                    {"role": "system", "content": self.config.system_prompt},
                    {"role": "user", "content": user_input}
                ],
            "response_format": get_response_format(self.config.response_keys)
        }

        try:
            response = requests.post(url, headers=headers, json=data)
        except requests.exceptions.ConnectionError:
            raise ExternalException(f"ConnectionError, could not access the OpenAI service.\n"
                                 f"Are you sure you have an internet connection?")

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            if response.status_code == 401:
                raise ExternalException('Received an "Unauthorized" response; your API key is probably invalid.')
            elif response.status_code == 429:
                raise ExternalException('Received a "429 Client Error: Too Many Requests" response; you might be rate limited to 3 requests per minute.')
            else:
                raise ExternalException(f'Error: {response.status_code} {response.reason}')

        return self.parse_json_response(response=response.json(), expected_length=len(note_infos), user_input=user_input)

    def parse_json_response(self, response, expected_length: int, user_input: str = None) -> list[dict]:
        message_content = response['choices'][0]['message']['content']
        sentences = json.loads(message_content)['results']
        if len(sentences) != expected_length:
            print((f"WARNING: Results size of {len(sentences)} didn't match input length of {expected_length}.\n"
                  "This is normally just ChatGPT being weird and not doing what you told it to do in the prompt.\n"
                  f'The "content" passed to ChatGPT was:\n{user_input}\nand the response was:\n{message_content}\n'
                  'Sometimes, if you only passed one sentence, ChatGPT outputs two, which isn\'t a problem.'))
        if self.debug:
            for i, sentence in enumerate(sentences):
                print(f"Result {i}: {sentence}")
        return sentences
