from aqt import mw
from aqt.qt import QAction, QMenu
from anki import hooks

from .client_factory import ClientFactory


def on_setup_menus(browser):
    def display_ui():
        client_factory.show(browser)

    menu = QMenu("Anki AI", browser.form.menubar)
    browser.form.menubar.addMenu(menu)
    cps_action = QAction("Anki AI Settings", mw)
    cps_action.triggered.connect(display_ui)
    menu.addAction(cps_action)


client_factory = ClientFactory()
hooks.addHook("browser.setupMenus", on_setup_menus)
