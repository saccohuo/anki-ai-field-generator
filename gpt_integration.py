import html
import re
import webbrowser
from urllib.parse import quote_plus

from aqt import gui_hooks, mw
from aqt.qt import QAction, QMessageBox, QMenu
from anki import hooks

from .client_factory import ClientFactory
from .config_manager_dialog import ConfigManagerDialog
from .settings import SettingsNames, get_settings


_TOOLS_MENU_ACTION = None
_TOOLS_PROGRESS_ACTION = None
_CONFIG_ACTION_REGISTERED = False


def show_config_dialog(parent):
    settings, _ = get_settings()
    selected = (
        settings.value(
            SettingsNames.CONFIG_NAME_SETTING_NAME,
            defaultValue="",
            type=str,
        )
        or None
    )
    dialog = ConfigManagerDialog(parent, selected_config=selected)
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


def _show_progress_dialog(parent) -> None:
    if ClientFactory.focus_progress_dialog():
        return
    QMessageBox.information(
        parent or mw,
        "Anki AI",
        "当前没有正在运行的批处理任务。",
    )


def _current_config_name() -> str:
    settings, _ = get_settings()
    return (
        settings.value(
            SettingsNames.CONFIG_NAME_SETTING_NAME,
            defaultValue="Default",
            type=str,
        )
        or "Default"
    )


def _youglish_action_label() -> str:
    return f"Update YouGlish Links ({_current_config_name()})"


def _extract_youglish_term(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _build_youglish_url(term: str, accent: str) -> str:
    if not term:
        return ""
    normalized = accent.lower() if accent else "us"
    accent_value = normalized if normalized in {"us", "uk", "aus"} else "us"
    encoded_term = quote_plus(term.strip())
    return f"https://youglish.com/pronounce/{encoded_term}/english?accent={accent_value}"


def _open_youglish_for_selection(browser) -> None:
    note_ids = list(browser.selectedNotes())
    if not note_ids:
        QMessageBox.information(
            browser,
            "Anki AI",
            "Select a note to open YouGlish.",
        )
        return
    open_all = False
    if len(note_ids) > 1:
        response = QMessageBox.question(
            browser,
            "Open YouGlish",
            (
                f"已选择 {len(note_ids)} 条笔记。\n"
                "是：为全部笔记打开并写入链接。\n"
                "否：仅处理第一条笔记。\n"
                "取消：不执行。"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if response == QMessageBox.StandardButton.Cancel:
            return
        open_all = response == QMessageBox.StandardButton.Yes
    target_note_ids = note_ids if open_all else [note_ids[0]]
    settings, _ = get_settings()
    source_field = (
        settings.value(
            SettingsNames.YOUGLISH_SOURCE_FIELD_SETTING_NAME,
            defaultValue="_word",
            type=str,
        )
        or "_word"
    ).strip()
    target_field = (
        settings.value(
            SettingsNames.YOUGLISH_TARGET_FIELD_SETTING_NAME,
            defaultValue="_youglish",
            type=str,
        )
        or "_youglish"
    ).strip()
    accent = (
        settings.value(
            SettingsNames.YOUGLISH_ACCENT_SETTING_NAME,
            defaultValue="us",
            type=str,
        )
        or "us"
    )
    overwrite = settings.value(
        SettingsNames.YOUGLISH_OVERWRITE_SETTING_NAME,
        defaultValue=False,
    )
    if isinstance(overwrite, str):
        overwrite = overwrite.lower() in {"1", "true", "yes", "on"}
    overwrite = bool(overwrite)
    if not source_field:
        QMessageBox.information(
            browser,
            "Anki AI",
            "Configure a source field for YouGlish links before opening.",
        )
        return
    for note_id in target_note_ids:
        note = browser.mw.col.get_note(note_id)
        if note is None:
            continue
        if source_field not in note:
            continue
        target_value = (
            str(note[target_field]).strip()
            if target_field and target_field in note
            else ""
        )
        term = _extract_youglish_term(note[source_field])
        if not term and not target_value:
            continue
        url = target_value if target_value else _build_youglish_url(term, accent)
        if not url:
            continue
        if target_field and target_field in note and (overwrite or not target_value):
            note[target_field] = url
            try:
                note.col.update_note(note)
            except Exception:
                pass
        webbrowser.open(url)


def _confirm_youglish_settings(browser) -> bool:
    settings, _ = get_settings()
    enabled = settings.value(
        SettingsNames.YOUGLISH_ENABLED_SETTING_NAME,
        defaultValue=True,
    )
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        QMessageBox.information(
            browser,
            "Anki AI",
            "YouGlish 生成在当前配置中被关闭，请先在配置中启用。",
        )
        return False
    source = (
        settings.value(
            SettingsNames.YOUGLISH_SOURCE_FIELD_SETTING_NAME,
            defaultValue="_word",
            type=str,
        )
        or "_word"
    ).strip()
    target = (
        settings.value(
            SettingsNames.YOUGLISH_TARGET_FIELD_SETTING_NAME,
            defaultValue="_youglish",
            type=str,
        )
        or "_youglish"
    ).strip()
    if not source or not target:
        QMessageBox.warning(
            browser,
            "Anki AI",
            "YouGlish 源/目标字段未配置，请先在配置中设置。",
        )
        return False
    accent = (
        settings.value(
            SettingsNames.YOUGLISH_ACCENT_SETTING_NAME,
            defaultValue="us",
            type=str,
        )
        or "us"
    ).strip()
    overwrite = settings.value(
        SettingsNames.YOUGLISH_OVERWRITE_SETTING_NAME,
        defaultValue=False,
    )
    if isinstance(overwrite, str):
        overwrite = overwrite.strip().lower() in {"1", "true", "yes", "on"}
    config_name = _current_config_name()
    summary = (
        f"配置: {config_name}\n"
        f"源字段: {source}\n"
        f"目标字段: {target}\n"
        f"方言: {accent.upper()}\n"
        f"覆盖已有值: {'是' if overwrite else '否'}\n\n"
        "是否使用以上设置批量更新选中笔记的 YouGlish 链接？"
    )
    response = QMessageBox.question(
        browser,
        "确认 YouGlish 配置",
        summary,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return response == QMessageBox.StandardButton.Yes


def _run_youglish_update(browser) -> None:
    if not _confirm_youglish_settings(browser):
        return
    client_factory = ClientFactory(browser)
    client_factory.run_youglish_only(browser)


def on_setup_menus(browser):
    menu = QMenu("Anki AI", browser.form.menubar)
    browser.form.menubar.addMenu(menu)
    cps_action = QAction("Update Your Flashcards with AI", mw)
    cps_action.triggered.connect(lambda: _launch_client_ui(browser))
    menu.addAction(cps_action)

    settings_action = QAction("Manage AI Configurations", mw)
    settings_action.triggered.connect(lambda: show_config_dialog(browser))
    menu.addAction(settings_action)

    progress_action = QAction("显示运行中的任务", mw)
    progress_action.triggered.connect(lambda: _show_progress_dialog(browser))
    menu.addAction(progress_action)
    youglish_action = QAction("Open YouGlish Link", mw)
    youglish_action.triggered.connect(lambda: _open_youglish_for_selection(browser))
    menu.addAction(youglish_action)
    youglish_update_action = QAction(_youglish_action_label(), mw)
    youglish_update_action.triggered.connect(lambda: _run_youglish_update(browser))
    menu.addAction(youglish_update_action)
    menu.aboutToShow.connect(
        lambda: youglish_update_action.setText(
            _youglish_action_label()
        )
    )


hooks.addHook("browser.setupMenus", on_setup_menus)



def on_will_show_context_menu(browser, menu):
    action = QAction("Update Your Flashcards with AI", browser)
    action.triggered.connect(lambda _: _launch_client_ui(browser))
    menu.addAction(action)
    yg_action = QAction("Open YouGlish Link", browser)
    yg_action.triggered.connect(lambda _: _open_youglish_for_selection(browser))
    menu.addAction(yg_action)
    yg_update = QAction(_youglish_action_label(), browser)
    yg_update.triggered.connect(lambda _: _run_youglish_update(browser))
    menu.addAction(yg_update)


gui_hooks.browser_will_show_context_menu.append(on_will_show_context_menu)


def _ensure_tools_menu_entry():
    global _TOOLS_MENU_ACTION, _TOOLS_PROGRESS_ACTION
    if mw is None or mw.form is None:
        return
    if _TOOLS_MENU_ACTION is None:
        action = QAction("Anki AI Configuration", mw)
        action.triggered.connect(lambda: show_config_dialog(mw))
        mw.form.menuTools.addAction(action)
        _TOOLS_MENU_ACTION = action
    if _TOOLS_PROGRESS_ACTION is None:
        progress_action = QAction("Show Anki AI Task Progress", mw)
        progress_action.triggered.connect(lambda: _show_progress_dialog(mw))
        mw.form.menuTools.addAction(progress_action)
        _TOOLS_PROGRESS_ACTION = progress_action


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
