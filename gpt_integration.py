from aqt import mw
from aqt.qt import QAction, QMenu
from anki import hooks

from .client_factory import ClientFactory
from .config_manager_dialog import ConfigManagerDialog


_TOOLS_MENU_ACTION = None
_CONFIG_ACTION_REGISTERED = False


def show_config_dialog(parent):
    dialog = ConfigManagerDialog(parent)
    dialog.exec()


def on_setup_menus(browser):
    def display_ui():
        client_factory = ClientFactory(browser)
        client_factory.show()

    menu = QMenu("Anki AI", browser.form.menubar)
    browser.form.menubar.addMenu(menu)
    cps_action = QAction("Update Your Flashcards with AI", mw)
    cps_action.triggered.connect(display_ui)
    menu.addAction(cps_action)

    settings_action = QAction("Manage AI Configurations", mw)
    settings_action.triggered.connect(lambda: show_config_dialog(browser))
    menu.addAction(settings_action)


hooks.addHook("browser.setupMenus", on_setup_menus)


def _ensure_tools_menu_entry():
    global _TOOLS_MENU_ACTION
    if _TOOLS_MENU_ACTION is not None:
        return
    if mw is None or mw.form is None:
        return
    action = QAction("Anki AI Configuration", mw)
    action.triggered.connect(lambda: show_config_dialog(mw))
    mw.form.menuTools.addAction(action)
    _TOOLS_MENU_ACTION = action


def _ensure_addon_manager_action():
    global _CONFIG_ACTION_REGISTERED
    if _CONFIG_ACTION_REGISTERED:
        return
    if mw is None or not hasattr(mw, "addonManager"):
        return

    def _open_config(manager=None):
        parent = getattr(manager, "mw", None) if manager is not None else None
        show_config_dialog(parent or mw)

    try:
        mw.addonManager.setConfigAction(__name__, _open_config)
        _CONFIG_ACTION_REGISTERED = True
    except AttributeError:
        # Older Anki versions may not support custom config actions.
        pass


def _on_profile_loaded():
    _ensure_tools_menu_entry()
    _ensure_addon_manager_action()


hooks.addHook("profileLoaded", _on_profile_loaded)
