from .modify_cards_ui import ModifyCardsDialog


class OpenAIDialog(ModifyCardsDialog):

    @property
    def system_prompt_description(self):
        return (
            "Enter the System Prompt that is the overall system instructions.\n"
            'This is where you should give very specific instructions, examples, and do "prompt engineering". '
            "For more examples, see:\n"
            "https://platform.openai.com/docs/guides/prompt-engineering/strategy-write-clear-instructions"
        )

    @property
    def system_prompt_placeholder(self):
        return (
            "Example:\n"
            "You are a helpful German teacher.  You will be provided with a series of: a German word delimited by triple quotes, "
            "followed by a German sentence.  For each word and sentence pair, follow the below steps:\n\n"
            "- Give a very slightly modified version of the sentence - for example, use a different subject, "
            "verb, or object - while still using the provided German word.  Only change one or two words in the sentence.\n\n"
            "- Translate the modified sentence into English."
        )

    @property
    def user_prompt_description(self):
        return (
            "Enter the prompt that will be created and sent for each card.\n"
            "Use the field name surrounded by braces to substitute in a field from the card."
        )

    @property
    def user_prompt_placeholder(self):
        return "Example:\n" '"""{german_word}"""\n\n{german_sentence}\n'
