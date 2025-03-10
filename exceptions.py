"""All our custom exceptions"""


class ExternalException(Exception):
    """Exception that will be displayed in UI when thrown"""

    def __init__(self, message):
        super().__init__(message)
