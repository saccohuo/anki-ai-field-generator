from aqt import mw
from aqt.qt import QAction, QMenu
from anki import hooks

from .modify_cards_ui import ModifyCardsUI
from .openai_client import OpenAIClient
from .openai_ui import OpenAIDialog
from .prompt_config import PromptConfig
from .settings import get_settings


def on_setup_menus(browser):
    def display_ui():
        modify_cards_ui.show(browser)

    menu = QMenu("Anki AI", browser.form.menubar)
    browser.form.menubar.addMenu(menu)
    cps_action = QAction("Anki AI Settings", mw)
    cps_action.triggered.connect(display_ui)
    menu.addAction(cps_action)


settings = get_settings("OpenAI")
prompt_config = PromptConfig(settings)
llm_client = OpenAIClient(prompt_config)
dialog = OpenAIDialog(settings)

modify_cards_ui = ModifyCardsUI(settings, dialog, llm_client)
hooks.addHook("browser.setupMenus", on_setup_menus)
