"""All our custom exceptions"""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    GENERIC = "generic"
    CONNECTION = "connection"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMIT = "rate_limit"
    BAD_REQUEST = "bad_request"
    INVALID_INPUT = "invalid_input"
    MISSING_CREDENTIALS = "missing_credentials"
    IMAGE_MISSING_DATA = "image_missing_data"
    IMAGE_DECODE = "image_decode"
    MEDIA_WRITE_FAILED = "media_write_failed"
    AUDIO_MISSING_DATA = "audio_missing_data"


class ExternalException(Exception):
    """Exception that will be displayed in UI when thrown"""

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode = ErrorCode.GENERIC,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code: ErrorCode = code
        self.details: Dict[str, Any] = details or {}
