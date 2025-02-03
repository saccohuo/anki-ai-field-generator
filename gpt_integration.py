from aqt import mw
from aqt.qt import *
from anki import hooks
from anki.template import TemplateRenderContext

from .exceptions import ExternalException, show_error_dialog
from .future_notes import FutureNotes
from .openai_client import OpenAIClient
from .prompt_config import PromptConfig
from .settings import Settings


def on_field_filter(field_text: str, field_name: str, filter_name: str, ctx: TemplateRenderContext):
    note = ctx.note()
    if all(key in note for key in prompt_config.required_fields):
        try:
            current_note_info = future_notes.get_note_info(note)
        except ExternalException as e:
            show_error_dialog(str(e))
            return field_text

        if current_note_info and current_note_info.is_loaded_successfully():
            if filter_name in current_note_info.updates_dict:
                return current_note_info.updates_dict[filter_name]
            else:
                return field_text
    # Default
    return field_text


def on_setup_menus(browser):
    def temp():
        app_settings.show(browser)

    menu = QMenu("Anki AI", browser.form.menubar)
    browser.form.menubar.addMenu(menu)
    cps_action = QAction("Anki AI Settings", mw)
    cps_action.triggered.connect(temp)
    menu.addAction(cps_action)


hooks.addHook('browser.setupMenus', on_setup_menus)


app_settings = Settings()
# TODO: handle if required settings don't exist
prompt_config = PromptConfig(app_settings)
client = OpenAIClient(prompt_config)
future_notes = FutureNotes(openai_client=client, prompt_config=prompt_config, num_notes_to_store=5)
hooks.field_filter.append(on_field_filter)
