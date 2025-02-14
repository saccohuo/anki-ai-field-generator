from openai import LengthFinishReasonError, OpenAI
from pydantic import BaseModel


class Response(BaseModel):
    modifiedSentence: str
    translation: str


client = OpenAI()


try:
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """You are a helpful German teacher.  You will be provided with a German word, followed by a German sentence.  Follow the below steps:

            Step 1 - Give a very slightly modified version of the sentence - for example, a different subject, verb, or object - while still using the provided German word.  Only change one or two words in the sente

            Step 2 - Translate the sentence from Step 1 into English.""",
            },
            {
                "role": "user",
                "content": """\"\"\"das Kino, -s\"\"\"

            Wir sehen heute Abend im Kino einen schönen Film.""",
            },
        ],
        response_format=Response,
    )

    response = completion.choices[0].message
    if response.parsed:
        print(f"modifiedSentence: {response.parsed.modifiedSentence}")
        print(f"translation: {response.parsed.translation}")
    elif response.refusal:
        # handle refusal
        print(response.refusal)
except Exception as e:
    # Handle edge cases
    if type(e) == LengthFinishReasonError:
        # Retry with a higher max tokens
        print("Too many tokens: ", e)
        pass
    else:
        # Handle other exceptions
        print(e)
        pass
