try:
    from aqt.qt import QSettings
except ImportError:  # pragma: no cover - fallback for tests outside Anki
    class QSettings:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise RuntimeError("QSettings requires the Anki environment.")


SETTINGS_ORGANIZATION = "github_rroessler1"
SETTINGS_APPLICATION = "anki-gpt-plugin"


class SettingsNames:
    API_KEY_SETTING_NAME = "api_key"
    ENDPOINT_SETTING_NAME = "endpoint"
    DESTINATION_FIELD_SETTING_NAME = "destination_field"
    LLM_CLIENT_NAME = "llm_client_name"
    CONFIG_NAME_SETTING_NAME = "config_name"
    MODEL_SETTING_NAME = "model"
    TEXT_PROVIDER_SETTING_NAME = "text_provider"
    TEXT_PROVIDER_CUSTOM_VALUE_SETTING_NAME = "text_provider_custom"
    SYSTEM_PROMPT_SETTING_NAME = "system_prompt"
    USER_PROMPT_SETTING_NAME = "user_prompt"
    RESPONSE_KEYS_SETTING_NAME = "response_keys"
    TEXT_MAPPING_ENTRIES_SETTING_NAME = "text_mapping_entries"
    IMAGE_MAPPING_SETTING_NAME = "image_prompt_mappings"
    IMAGE_PROVIDER_SETTING_NAME = "image_provider"
    IMAGE_API_KEY_SETTING_NAME = "image_api_key"
    IMAGE_ENDPOINT_SETTING_NAME = "image_endpoint"
    IMAGE_MODEL_SETTING_NAME = "image_model"
    AUDIO_MAPPING_SETTING_NAME = "audio_prompt_mappings"
    AUDIO_PROVIDER_SETTING_NAME = "audio_provider"
    AUDIO_API_KEY_SETTING_NAME = "audio_api_key"
    AUDIO_MODEL_SETTING_NAME = "audio_model"
    AUDIO_VOICE_SETTING_NAME = "audio_voice"
    AUDIO_ENDPOINT_SETTING_NAME = "audio_endpoint"
    AUDIO_FORMAT_SETTING_NAME = "audio_format"
    RETRY_LIMIT_SETTING_NAME = "retry_limit"
    RETRY_DELAY_SETTING_NAME = "retry_delay"
    ENABLE_TEXT_GENERATION_SETTING_NAME = "enable_text_generation"
    ENABLE_IMAGE_GENERATION_SETTING_NAME = "enable_image_generation"
    ENABLE_AUDIO_GENERATION_SETTING_NAME = "enable_audio_generation"
    YOUGLISH_ENABLED_SETTING_NAME = "youglish_enabled"
    YOUGLISH_SOURCE_FIELD_SETTING_NAME = "youglish_source_field"
    YOUGLISH_TARGET_FIELD_SETTING_NAME = "youglish_target_field"
    YOUGLISH_ACCENT_SETTING_NAME = "youglish_accent"
    YOUGLISH_OVERWRITE_SETTING_NAME = "youglish_overwrite"
    OAAD_ENABLED_SETTING_NAME = "oaad_enabled"
    OAAD_SOURCE_FIELD_SETTING_NAME = "oaad_source_field"
    OAAD_TARGET_FIELD_SETTING_NAME = "oaad_target_field"
    OAAD_ACCENT_SETTING_NAME = "oaad_accent"
    OAAD_OVERWRITE_SETTING_NAME = "oaad_overwrite"
    AUTO_GENERATE_ON_ADD_SETTING_NAME = "auto_generate_on_add"
    SCHEDULE_ENABLED_SETTING_NAME = "schedule_enabled"
    SCHEDULE_QUERY_SETTING_NAME = "schedule_query"
    SCHEDULE_INTERVAL_MIN_SETTING_NAME = "schedule_interval_minutes"
    SCHEDULE_BATCH_SIZE_SETTING_NAME = "schedule_batch_size"
    SCHEDULE_DAILY_LIMIT_SETTING_NAME = "schedule_daily_limit"
    SCHEDULE_NOTICE_SECONDS_SETTING_NAME = "schedule_notice_seconds"
    SCHEDULE_NEXT_RUN_TS_SETTING_NAME = "schedule_next_run_ts"
    SCHEDULE_DAILY_COUNT_SETTING_NAME = "schedule_daily_count"
    AUTO_QUEUE_SILENT_SETTING_NAME = "auto_queue_silent"
    AUTO_QUEUE_DISPLAY_FIELD = "auto_queue_display_field"
    AUTO_QUEUE_LAST_STATUS = "auto_queue_last_status"
    AUTO_QUEUE_LAST_TIME = "auto_queue_last_time"


def get_settings() -> QSettings:
    """Returns a tuple of the settings and the groupName."""
    settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
    client_name = settings.value(
        SettingsNames.LLM_CLIENT_NAME,
        defaultValue="Config",
        type=str,
    )
    if client_name != "Config":
        settings.setValue(SettingsNames.LLM_CLIENT_NAME, "Config")
        client_name = "Config"
    settings.beginGroup(client_name)
    return settings, client_name


def set_new_settings_group(settings: QSettings, client_name: str):
    """Sets a new group. This mutates the object!"""
    settings.endGroup()
    settings.setValue(SettingsNames.LLM_CLIENT_NAME, client_name)
    settings.beginGroup(client_name)
