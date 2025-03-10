from .user_base_dialog import UserBaseDialog


class ClaudeDialog(UserBaseDialog):

    @property
    def service_name(self):
        return "Claude"

    @property
    def models(self):
        return [
            "claude-3-5-haiku-latest",
            "claude-3-haiku-20240307",
            "claude-3-7-sonnet-latest",
            "claude-3-5-sonnet-latest",
            "claude-3-opus-latest",
        ]

    @property
    def system_prompt_description(self):
        return (
            'Enter the System Prompt to give Claude a "role".\n'
            "This is where you should give very specific instructions, examples, and "
            'do "prompt engineering". For more examples, see:\n'
            "https://docs.anthropic.com/en/prompt-library/library"
        )

    @property
    def system_prompt_placeholder(self):
        return (
            "Example:\n"
            "You are a helpful German teacher.  You will be provided with: a German word delimited by triple quotes, "
            "followed by a German sentence.  Follow the below steps:\n\n"
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
