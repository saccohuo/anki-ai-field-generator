"""Shared provider option definitions for text, image, and speech pipelines."""

from __future__ import annotations

from typing import Final

TEXT_PROVIDERS: Final[list[tuple[str, str]]] = [
    ("openai", "OpenAI (GPT)"),
    ("claude", "Anthropic Claude"),
    ("gemini", "Google Gemini"),
    ("deepseek", "DeepSeek"),
    ("custom", "Custom"),
]

IMAGE_PROVIDERS: Final[list[tuple[str, str]]] = [
    ("gemini", "Google Nano Banana"),
    ("openai", "OpenAI Images"),
    ("custom", "Custom"),
]

AUDIO_PROVIDERS: Final[list[tuple[str, str]]] = [
    ("openai", "OpenAI TTS"),
    ("gemini", "Gemini TTS"),
    ("custom", "Custom"),
]

TEXT_PROVIDER_DEFAULTS: Final[dict[str, dict[str, str]]] = {
    "openai": {
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
    },
    "claude": {
        "endpoint": "https://api.anthropic.com/v1/messages",
        "model": "claude-3.5-sonnet",
    },
    "gemini": {
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models",
        "model": "gemini-2.0-flash",
    },
    "deepseek": {
        "endpoint": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-chat",
    },
}

IMAGE_PROVIDER_DEFAULTS: Final[dict[str, dict[str, str]]] = {
    "gemini": {
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models",
        "model": "gemini-2.5-flash-image",
    },
    "openai": {
        "endpoint": "https://api.openai.com/v1/images/generations",
        "model": "gpt-image-1",
    },
}

AUDIO_PROVIDER_DEFAULTS: Final[dict[str, dict[str, str]]] = {
    "openai": {
        "endpoint": "https://api.openai.com/v1/audio/speech",
        "model": "gpt-4o-mini-tts",
        "voice": "alloy",
        "format": "mp3",
    },
    "gemini": {
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models",
        "model": "gemini-2.5-flash-preview-tts",
        "voice": "Kore",
        "format": "wav",
    },
}

__all__ = [
    "TEXT_PROVIDERS",
    "IMAGE_PROVIDERS",
    "AUDIO_PROVIDERS",
    "TEXT_PROVIDER_DEFAULTS",
    "IMAGE_PROVIDER_DEFAULTS",
    "AUDIO_PROVIDER_DEFAULTS",
]
