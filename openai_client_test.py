# Note that the import in __init__.py must be commented out to run this test.
# Run from one directory above, with:
# python -m anki-gpt.openai_client_test
import os

from .note_info import NoteInfo
from .openai_client import OpenAIClient
from .prompt_config import PromptConfig


USER_PROMPT = '"""{de_word}"""\n\n{de_sentence}\n'
SYSTEM_PROMPT = """You are a helpful German teacher.  You will be provided with a series of: a German word delimited by triple quotes, followed by a German sentence.  For each word and sentence pair, follow the below steps:

- Give a very slightly modified version of the sentence - for example, use a different subject, verb, or object - while still using the provided German word.  Only change one or two words in the sentence.

- Translate the modified sentence into English."""
RESPONSE_KEYS = "modifiedSentence, translation"


def create_notes(prompt_config: PromptConfig) -> list[NoteInfo]:
    note_info = NoteInfo(prompt_config)
    fields = {"de_word": "der Wein",
              "de_sentence": "Nein danke, ich möchte keinen Wein."}
    note_info.field_dict = fields

    note_info2 = NoteInfo(prompt_config)
    fields = {"de_word": "die Schule",
              "de_sentence": "Die Schule ist gleich hier um die Ecke."}
    note_info2.field_dict = fields
    return [note_info, note_info2]


api_key = os.getenv('OPENAI_API_KEY')
prompt_config = PromptConfig.create_test_instance(api_key, SYSTEM_PROMPT, USER_PROMPT, RESPONSE_KEYS)
client = OpenAIClient(prompt_config)
results = client.modify_sentence_and_translate(note_infos=create_notes(prompt_config))
for result in results:
    for key, value in result.items():
        print(f"{key}: {value}")
