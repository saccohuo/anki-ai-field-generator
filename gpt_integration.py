from aqt import mw
from aqt.qt import QAction, QMenu
from anki import hooks

from .modify_cards_ui import ModifyCardsUI


# def on_field_filter(field_text: str, field_name: str, filter_name: str, ctx: TemplateRenderContext):
#     note = ctx.note()
#     if all(key in note for key in prompt_config.required_fields):
#         try:
#             current_note_info = future_notes.get_note_info(note)
#         except ExternalException as e:
#             show_error_dialog(str(e))
#             return field_text

#         if current_note_info and current_note_info.is_loaded_successfully():
#             if filter_name in current_note_info.updates_dict:
#                 return current_note_info.updates_dict[filter_name]
#             else:
#                 return field_text
#     # Default
#     return field_text


def on_setup_menus(browser):
    def display_ui():
        modify_cards_ui.show(browser)

    menu = QMenu("Anki AI", browser.form.menubar)
    browser.form.menubar.addMenu(menu)
    cps_action = QAction("Anki AI Settings", mw)
    cps_action.triggered.connect(display_ui)
    menu.addAction(cps_action)


modify_cards_ui = ModifyCardsUI()
hooks.addHook("browser.setupMenus", on_setup_menus)
