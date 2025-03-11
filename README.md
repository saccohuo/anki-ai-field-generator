# anki-ai-field-generator

This is not a standalone script, it's a plugin for Anki which can be downloaded here: https://ankiweb.net/shared/info/643253121

## Description

This plugin allows you to use Large Language Models (LLMs) to update or add information to your Anki flashcards using the power of AI.

Features:
- Supports Claude (Anthropic), ChatGPT (OpenAI), and Deepseek models.
- Completely free! (You create your own API key and pay per usage)

## How it works:

### Quickstart:
1. Install the plugin.
1. In the card browser, select the cards you want to modify (tip: Shift+Click to select many or Ctrl+A to select all)
1. You have a new menu option: Anki AI -> Update Your Flashcards with AI
1. Enter your API key and prompt, and it updates the cards!

### How to use information from your Anki cards:
- In the "User Prompt" section, you can insert fields from your cards by writing the field name surrounded by braces {}.
    ```
    Example User Prompt: Translate this sentence into Chinese: {en_sentence}
    ```

### How to save the response to your Anki cards:
- Behind the scenes, the LLM returns a "JSON" response. This is a {key: value} response. This guarantees the model always returns exactly what you asked for.
- If you use DeepSeek, you have to give it an example JSON response in the System Prompt. For example:
```
{
    "exampleSentence": "Mein Bruder kommt aus den USA.",
    "translation": "My brother is from the USA."
}
```
- In the "Save the AI Output" section, map the JSON "keys" that the LLM returns to your Anki card "field names".  In the above example:
```
exampleSentence de_sentence
translation     en_sentence
```
- The JSON "keys" can be called whatever you want. Just specify them in the System Prompt and make sure they make sense.



## How to Create an API Key:

Note that for all of these you'll probably have to add a credit card with maybe $5 first.

### Claude (Anthropic):

Sign up here: https://console.anthropic.com/dashboard

Then click "Get API Keys" and create a key.

### ChatGPT (OpenAI):

Go here: https://platform.openai.com/api-keys

And create a key.

### DeepSeek

Sign up here: https://platform.deepseek.com/

Then click on "API Keys" and create a key.

## FAQ:

### What is an API Key?

An API Key is a secret unique identifier used to authenticate and authorize a user. So basically it identifies you with your account, so you can be charged for your usage.

**An API Key should never be shared with anyone.** Because then they can use your account and your saved credit.

If you accidentally "expose" your API key (text it to someone by accident or whatever), you can easily delete it and create a new one using the links listed above.

### Which LLM should I use?

**Answer quality:** they're all pretty good, and it depends more on your prompt engineering

**Speed:** Claude is the fastest, as it allows 50 calls per minute, whereas OpenAI only allows 3 per minute and 200 per day (from the beginner tier).

**Cost:** OpenAI's gpt-4o-mini model is currently the cheapest.

### Why is the OpenAI model so slow / why am I getting rate-limited?

Unfortunately when you first sign up for OpenAI you can only make 3 calls per minute (and 200 per day). The plugin handles this, sadly just by "pausing" for 20 seconds at a time.

Once you spend $5, then you can make 500 calls per minute. I don't know of any way to just automatically spend $5 to get to the next Tier.

### How much does it cost?

This Add-on is free! See "Pricing" below for a more detailed breakdown of expected costs of using the LLMs.

### What if I have questions, bug reports, or feature requests?

Please submit them to the GitHub repo here: https://github.com/rroessler1/anki-ai-field-generator/issues

### How can I support the creator of this plugin?

Well, I'd be very grateful! You can buy me a coffee here: https://buymeacoffee.com/rroessler

And please upvote it here: https://ankiweb.net/shared/info/643253121 , that helps other people discover it and encourages me to keep it maintained.

## Pricing

All the companies have models are relatively inexpensive, and have the pricing information on their website. But specifically:

- The cheapest models currently are Anthropic's claude-3-5-haiku, DeepSeek's deepseek-chat, and OpenAI's gpt-4o-mini.
- More advanced models might cost quite a bit more.
- Pricing is based on number of tokens in the input and the output. A "token" is generally a few letters.
- I tested with the same prompt, and Claude uses 3x the number of tokens as OpenAI and Deepseek. This makes Claude more expensive.

### Estimated Costs:

Using the example prompts shown in the UI:

**OpenAI**: One flashcard uses 180 tokens, so 1 million tokens = 5500 cards = $0.15 USD

**DeepSeek**: One flashcard uses 195 tokens, so 1 million tokens = 5100 cards = $0.27 USD

**Claude**: One flashcard uses 660 tokens, so 1 million tokens = 1500 cards = $0.80 USD

So Claude is relatively more expensive, but it's the fastest. Once you are past the basic tier on OpenAI (once you spend $5), it becomes equivalently fast.

## How should I use it?

Well, you're only limited by the power of your imagination!

I asked ChatGPT how people could use this plugin, and it gave me the following suggestions:

### Language Learning & Vocabulary Expansion

- Contextual Cloze Deletions: Generate sentences with a missing word (e.g., fill-in-the-blank exercises).
- Synonyms & Antonyms: Provide a list of synonyms and antonyms for vocabulary words.
- Collocations: Generate common phrases and word pairings to show how a word is naturally used.
-  Etymology & Word Roots: Explain the origin of a word to deepen understanding.
-  Idioms & Expressions: Provide idiomatic usage examples for specific words or phrases.

### Grammar & Writing Practice

- Sentence Transformations: Convert active to passive voice, direct to indirect speech, or rewrite using different tenses.
- Error Correction: Analyze a sentence from the card and suggest corrections with explanations.
- Paraphrasing Practice: Rephrase a sentence while keeping its meaning intact.
- Question & Answer Generation: Generate comprehension questions based on a sentence or passage.

### Subject-Specific Enhancements
- Math & Science Flashcards: Generate explanations, problem solutions, or step-by-step derivations.
- Medical & Technical Flashcards: Provide definitions with layman-friendly explanations and real-world applications.
- Historical Context: Generate a brief historical background for a fact or event.
- Mnemonic Creation: Suggest mnemonics to help remember facts, dates, or formulas.
