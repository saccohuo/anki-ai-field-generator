from aqt import gui_hooks, mw
from aqt.qt import QAction, QMessageBox, QMenu
from anki import hooks

from .client_factory import ClientFactory
from .config_manager_dialog import ConfigManagerDialog


_TOOLS_MENU_ACTION = None
_CONFIG_ACTION_REGISTERED = False


def show_config_dialog(parent):
    dialog = ConfigManagerDialog(parent)
    dialog.exec()


def _launch_client_ui(browser) -> None:
    client_factory = ClientFactory(browser)
    if not client_factory.notes:
        QMessageBox.information(
            browser,
            "Anki AI",
            "Select at least one note before launching the Anki AI plugin.",
        )
        return
    client_factory.show()


def on_setup_menus(browser):
    menu = QMenu("Anki AI", browser.form.menubar)
    browser.form.menubar.addMenu(menu)
    cps_action = QAction("Update Your Flashcards with AI", mw)
    cps_action.triggered.connect(lambda: _launch_client_ui(browser))
    menu.addAction(cps_action)

    settings_action = QAction("Manage AI Configurations", mw)
    settings_action.triggered.connect(lambda: show_config_dialog(browser))
    menu.addAction(settings_action)


hooks.addHook("browser.setupMenus", on_setup_menus)



def on_will_show_context_menu(browser, menu):
    action = QAction("Update Your Flashcards with AI", browser)
    action.triggered.connect(lambda _: _launch_client_ui(browser))
    menu.addAction(action)


gui_hooks.browser_will_show_context_menu.append(on_will_show_context_menu)


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
