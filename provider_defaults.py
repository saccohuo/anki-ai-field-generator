"""Shared helpers for applying provider defaults across dialogs."""

from __future__ import annotations

from typing import Dict, Optional

from PyQt6.QtWidgets import QComboBox, QLineEdit, QPushButton


def apply_provider_defaults(
    provider_key: str,
    defaults_map: Dict[str, Dict[str, str]],
    *,
    endpoint_input: QLineEdit,
    model_input: QLineEdit,
    voice_input: Optional[QLineEdit] = None,
    format_input: Optional[QLineEdit] = None,
    force: bool = False,
) -> None:
    """Apply endpoint/model defaults (and optional voice/format) for a provider."""
    defaults = defaults_map.get(provider_key.lower())
    if not defaults:
        return
    endpoint_default = defaults.get("endpoint", "")
    model_default = defaults.get("model", "")
    if endpoint_default and (force or not endpoint_input.text().strip()):
        endpoint_input.setText(endpoint_default)
    if model_default and (force or not model_input.text().strip()):
        model_input.setText(model_default)
    if voice_input is not None:
        voice_default = defaults.get("voice")
        if voice_default is not None and (force or not voice_input.text().strip()):
            voice_input.setText(voice_default)
    if format_input is not None:
        format_default = defaults.get("format")
        if format_default is not None and (force or not format_input.text().strip()):
            format_input.setText(format_default)


def reset_button_enabled(combo: Optional[QComboBox], defaults_map: Dict[str, Dict[str, str]]) -> bool:
    """Return True when the current provider has defaults (used to toggle reset buttons)."""
    if combo is None:
        return False
    provider = combo.currentData()
    if provider is None:
        return False
    return str(provider).lower() in defaults_map


__all__ = ["apply_provider_defaults", "reset_button_enabled"]
