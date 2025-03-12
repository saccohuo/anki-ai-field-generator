# anki-ai-field-generator

This is not a standalone script, it's a plugin for Anki which can be downloaded here: https://ankiweb.net/shared/info/643253121

## Description

- This plugin allows you to use Large Language Models (LLMs) to add information to your Anki flashcards using the power of AI.
- Supports Claude (Anthropic), ChatGPT (OpenAI), and Deepseek models.
- Completely free! (You create your own API key and pay for LLM usage)

## Quickstart:
1. Install this plugin. (Open Anki. Tools -> Add-ons -> Get Addons -> Enter code: 643253121)
1. In the Card Browser, select the cards you want to modify (tip: Shift+Click to select many or Ctrl+A to select all)
1. You have a new menu option: Anki AI -> Update Your Flashcards with AI
1. Enter your API key and the required prompts.

## Detailed Setup:

<details>
<summary><b>1. Create an API Key:</b></summary>

For all of these you'll have to add a credit card and add a few dollars of credit first.

<b>Claude (Anthropic):</b>

Sign up here: https://console.anthropic.com/dashboard

Then click "Get API Keys" and create a key.

<b>ChatGPT (OpenAI):</b>

Go here: https://platform.openai.com/

If you've never signed up for OpenAI before, click "Sign up".

Follow the prompts, and be sure to create an API key and also to add a credit card with a few dollars, otherwise it won't work.

<b>DeepSeek</b>

Sign up here: https://platform.deepseek.com/

Then click on "API Keys" and create a key.
</details>

<details>
<summary><b>2. Create a System Prompt:</b></summary>
This is where you write specific instructions, examples, and do "prompt engineering".

This is <u>also</u> where you tell the model which output to return, which you'll need in Step 4.

Example System Prompt:

```
You are an experienced German teacher who is helping me practice grammar.  You will be provided with a German word.  Respond with:
-an "exampleSentence" at A2 or B1 level about 10-15 words long using the provided German word, and
-the "translation" of that sentence into English
```
In the above prompt, the model will return "exampleSentence" and "translation", which you'll use in step 4.

<details>
<summary><b>DeepSeek specific:</b></summary>
If you use DeepSeek, you must include an example JSON response in your System Prompt. Your prompt should look like this:

```
You are an experienced German teacher who is helping me practice grammar.  You will be provided with a German word.  Respond with:
-an "exampleSentence" at A2 or B1 level about 10-15 words long using the provided German word, and
-the "translation" of that sentence into English

EXAMPLE JSON OUTPUT:
{
    "exampleSentence": "Mein Bruder kommt aus den USA.",
    "translation": "My brother is from the USA."
}
```
</details>
</details>

<details>
<summary><b>3. Create a User Prompt:</b></summary>
This is where you use Fields from your Cards by writing the field name surrounded by braces {}.

Example User Prompt:

```
{de_sentence}
```
</details>

<details>
<summary><b>4. Save the response to your Anki Cards:</b></summary>
In the System Prompt, you told the LLM what information you want.

In our example it's an "exampleSentence" and a "translation", but you can ask the LLM for any information and call it whatever you want.

In the "Save the Output" part, match the information to Fields on your Cards. For example:

```
exampleSentence de_sentence
translation     en_sentence
```

In our example, the LLM returns:
- an "exampleSentence", which gets saved to the "de_sentence" field on our card
- a "translation", which gets saved to the "en_sentence" field on our card

</details>

## FAQ:

<details>
<summary><b>What is an API Key?</b></summary>

An API Key is a secret unique identifier used to authenticate and authorize a user. So basically it identifies you with your account, so you can be charged for your usage.

**An API Key should never be shared with anyone.** Because then they can use your account and your saved credit.

If you accidentally "expose" your API key (text it to someone by accident or whatever), you can easily delete it and create a new one using the links listed above.

</details>
<details>
<summary><b>Which LLM should I use?</b></summary>

**Answer quality:** they're all pretty good, and it depends more on your prompt engineering

**Speed:** Claude is the fastest, as it allows 50 calls per minute, whereas OpenAI only allows 3 per minute and 200 per day (from the beginner tier).

**Cost:** OpenAI's gpt-4o-mini model is currently the cheapest.

</details>
<details>
<summary><b>Why is the OpenAI model so slow / why am I getting rate-limited?</b></summary>

Unfortunately when you first sign up for OpenAI you can only make 3 calls per minute (and 200 per day). The plugin handles this, sadly just by "pausing" for 20 seconds at a time.

Once you spend $5, then you can make 500 calls per minute. I don't know of any way to just automatically spend $5 to get to the next Tier.

</details>
<details>
<summary><b>How much does it cost?</b></summary>

This Add-on is free! See "Pricing" below for a more detailed breakdown of expected costs of using the LLMs.

</details>
<details>
<summary><b>What if I have questions, bug reports, or feature requests?</b></summary>

Please submit them to the GitHub repo here: https://github.com/rroessler1/anki-ai-field-generator/issues

</details>
<details>
<summary><b>How can I support the creator of this plugin?</b></summary>

Well, I'd be very grateful! You can buy me a coffee here: https://buymeacoffee.com/rroessler

And please upvote it here: https://ankiweb.net/shared/info/643253121 , that helps other people discover it and encourages me to keep it maintained.
</details>

## Pricing

All the companies have models are relatively inexpensive, and have the pricing information on their website. But specifically:

- The cheapest models currently are Anthropic's claude-3-5-haiku, DeepSeek's deepseek-chat, and OpenAI's gpt-4o-mini.
- More advanced models might cost quite a bit more.
- Pricing is based on number of tokens in the input and the output. A "token" is generally a few letters.
- I tested with the same prompt, and Claude uses 3x the number of tokens as OpenAI and Deepseek. This makes Claude more expensive.

<details>
<summary><b>Estimated Costs:</b></summary>

Using the example prompts shown in the UI:

**OpenAI**: One flashcard uses 180 tokens, so 1 million tokens = 5500 cards = $0.15 USD

**DeepSeek**: One flashcard uses 195 tokens, so 1 million tokens = 5100 cards = $0.27 USD

**Claude**: One flashcard uses 660 tokens, so 1 million tokens = 1500 cards = $0.80 USD

So Claude is relatively more expensive, but it's the fastest. Once you are past the basic tier on OpenAI (once you spend $5), it becomes equivalently fast.

</details>

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
