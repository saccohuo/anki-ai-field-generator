import aqt
from aqt import mw


WINDOW_NAME = "ANKI GPT Error"


class ExternalException(Exception):
    def __init__(self, message):
        super().__init__(message)


def show_error_dialog(message: str, show_settings_after: bool = False):
    error_dialog = aqt.qt.QErrorMessage(mw)
    error_dialog.setWindowTitle(WINDOW_NAME)
    error_dialog.showMessage(message)
