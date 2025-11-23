import html
import re
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from typing import Optional

from anki.notes import Note as AnkiNote
from aqt import gui_hooks, mw
from aqt.qt import QAction, QMessageBox, QMenu, QTimer
from anki import hooks

from .client_factory import ClientFactory
from .config_manager_dialog import ConfigManagerDialog
from .prompt_config import PromptConfig
from .settings import SettingsNames, get_settings
from .scheduler import SchedulerManager


_TOOLS_MENU_ACTION = None
_TOOLS_PROGRESS_ACTION = None
_CONFIG_ACTION_REGISTERED = False
_AUTO_QUEUE: list[int] = []
_AUTO_TIMER = None
_AUTO_BACKGROUND_PREF = False


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
    settings, _ = get_settings()
    from .client_factory import active_background_count
    from .client_factory import active_bg_notes
    bg_count = active_background_count()
    if bg_count:
        note_list = active_bg_notes()
        field_name = (
            get_settings()[0].value(
                SettingsNames.AUTO_QUEUE_DISPLAY_FIELD,
                defaultValue="",
                type=str,
            )
            or ""
        ).strip()
        entries: list[str] = []
        if mw is not None and getattr(mw, "col", None) is not None:
            col = mw.col
            for nid in note_list[:10]:
                entry = str(nid)
                if field_name:
                    note = col.get_note(nid)
                    if note is not None and field_name in note:
                        val = str(note[field_name]) or ""
                        entry = f"{entry} ({val})"
                entries.append(entry)
        note_text = ", ".join(entries) if entries else ", ".join(str(nid) for nid in note_list[:10])
        extra = "…" if len(note_list) > 10 else ""
        QMessageBox.information(
            parent or mw,
            "Anki AI",
            f"后台正在处理 {bg_count} 条自动任务：\n{note_text}{extra}\n\n请稍候。",
        )
        return
    last_status = settings.value(
        SettingsNames.AUTO_QUEUE_LAST_STATUS,
        defaultValue="No active tasks.",
        type=str,
    )
    last_time = settings.value(
        SettingsNames.AUTO_QUEUE_LAST_TIME,
        defaultValue="",
        type=str,
    )
    suffix = f"\nLast auto-run: {last_time}" if last_time else ""
    QMessageBox.information(
        parent or mw,
        "Anki AI",
        f"当前没有正在运行的批处理任务。\n\n{last_status}{suffix}",
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


def _oaad_action_label() -> str:
    return f"Update OAAD Links ({_current_config_name()})"


def _extract_oaad_term(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _build_oaad_url(term: str, accent: str) -> str:
    if not term:
        return "https://www.oxfordlearnersdictionaries.com/"
    normalized = (accent or "us").lower()
    encoded_term = quote_plus(term.strip())
    if normalized == "us":
        return (
            "https://www.oxfordlearnersdictionaries.com/us/definition/american_english/"
            f"{encoded_term}?q={encoded_term}"
        )
    return (
        "https://www.oxfordlearnersdictionaries.com/definition/english/"
        f"{encoded_term}?q={encoded_term}"
    )


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


@dataclass
class _AiMenuActions:
    update: QAction
    manage: QAction
    progress: QAction
    youglish_open: QAction
    youglish_update: QAction
    oaad_open: QAction
    oaad_update: QAction

    def refresh_labels(self) -> None:
        self.youglish_update.setText(_youglish_action_label())
        self.oaad_update.setText(_oaad_action_label())


def _create_ai_menu_actions(browser) -> _AiMenuActions:
    update_action = QAction("Update Your Flashcards with AI", browser)
    update_action.triggered.connect(lambda: _launch_client_ui(browser))

    manage_action = QAction("Manage AI Configurations", browser)
    manage_action.triggered.connect(lambda: show_config_dialog(browser))

    progress_action = QAction("显示运行中的任务", browser)
    progress_action.triggered.connect(lambda: _show_progress_dialog(browser))

    yg_open = QAction("Open YouGlish Link", browser)
    yg_open.triggered.connect(lambda: _open_youglish_for_selection(browser))
    yg_update = QAction(_youglish_action_label(), browser)
    yg_update.triggered.connect(lambda: _run_youglish_update(browser))

    oaad_open = QAction("Open OAAD Link", browser)
    oaad_open.triggered.connect(lambda: _open_oaad_for_selection(browser))
    oaad_update = QAction(_oaad_action_label(), browser)
    oaad_update.triggered.connect(lambda: _run_oaad_update(browser))

    return _AiMenuActions(
        update=update_action,
        manage=manage_action,
        progress=progress_action,
        youglish_open=yg_open,
        youglish_update=yg_update,
        oaad_open=oaad_open,
        oaad_update=oaad_update,
    )


def _open_oaad_for_selection(browser) -> None:
    note_ids = list(browser.selectedNotes())
    if not note_ids:
        QMessageBox.information(browser, "Anki AI", "Select a note to open OAAD.")
        return
    open_all = False
    if len(note_ids) > 1:
        response = QMessageBox.question(
            browser,
            "Open OAAD",
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
            SettingsNames.OAAD_SOURCE_FIELD_SETTING_NAME,
            defaultValue="_word",
            type=str,
        )
        or "_word"
    ).strip()
    target_field = (
        settings.value(
            SettingsNames.OAAD_TARGET_FIELD_SETTING_NAME,
            defaultValue="_oaad",
            type=str,
        )
        or "_oaad"
    ).strip()
    accent = (
        settings.value(
            SettingsNames.OAAD_ACCENT_SETTING_NAME,
            defaultValue="us",
            type=str,
        )
        or "us"
    )
    overwrite = settings.value(
        SettingsNames.OAAD_OVERWRITE_SETTING_NAME,
        defaultValue=False,
    )
    if isinstance(overwrite, str):
        overwrite = overwrite.lower() in {"1", "true", "yes", "on"}
    overwrite = bool(overwrite)
    if not source_field:
        QMessageBox.information(
            browser,
            "Anki AI",
            "Configure a source field for OAAD links before opening.",
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
        term = _extract_oaad_term(note[source_field])
        url = target_value if target_value else _build_oaad_url(term, accent)
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


def _confirm_oaad_settings(browser) -> bool:
    settings, _ = get_settings()
    enabled = settings.value(
        SettingsNames.OAAD_ENABLED_SETTING_NAME,
        defaultValue=True,
    )
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        QMessageBox.information(
            browser,
            "Anki AI",
            "OAAD 生成在当前配置中被关闭，请先在配置中启用。",
        )
        return False
    source = (
        settings.value(
            SettingsNames.OAAD_SOURCE_FIELD_SETTING_NAME,
            defaultValue="_word",
            type=str,
        )
        or "_word"
    ).strip()
    target = (
        settings.value(
            SettingsNames.OAAD_TARGET_FIELD_SETTING_NAME,
            defaultValue="_oaad",
            type=str,
        )
        or "_oaad"
    ).strip()
    accent = (
        settings.value(
            SettingsNames.OAAD_ACCENT_SETTING_NAME,
            defaultValue="us",
            type=str,
        )
        or "us"
    )
    overwrite = settings.value(
        SettingsNames.OAAD_OVERWRITE_SETTING_NAME,
        defaultValue=False,
    )
    if isinstance(overwrite, str):
        overwrite = overwrite.lower() in {"1", "true", "yes", "on"}
    overwrite = bool(overwrite)
    summary = (
        f"源字段: {source}\n"
        f"目标字段: {target}\n"
        f"方言: {accent.upper()}\n"
        f"覆盖已有值: {'是' if overwrite else '否'}\n\n"
        "是否使用以上设置批量更新选中笔记的 OAAD 链接？"
    )
    response = QMessageBox.question(
        browser,
        "确认 OAAD 配置",
        summary,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return response == QMessageBox.StandardButton.Yes


def _run_youglish_update(browser) -> None:
    if not _confirm_youglish_settings(browser):
        return
    client_factory = ClientFactory(browser)
    client_factory.run_youglish_only(browser)


def _run_oaad_update(browser) -> None:
    if not _confirm_oaad_settings(browser):
        return
    client_factory = ClientFactory(browser)
    client_factory.run_oaad_only(browser)


def _maybe_auto_generate_on_add(note: AnkiNote) -> None:
    """Hook: run AI generation automatically when a new note is added."""
    settings, _ = get_settings()
    enabled = settings.value(
        SettingsNames.AUTO_GENERATE_ON_ADD_SETTING_NAME,
        defaultValue=False,
    )
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return
    note_id = getattr(note, "id", None)
    if note_id is None:
        return
    silent = _as_bool(
        settings.value(
            SettingsNames.AUTO_QUEUE_SILENT_SETTING_NAME,
            defaultValue=True,
        ),
        default=True,
    )
    if ClientFactory.focus_progress_dialog():
        _AUTO_QUEUE.append(note_id)
        _ensure_auto_timer()
        return
    mw_ref = mw
    if mw_ref is None or getattr(mw_ref, "col", None) is None:
        return
    try:
        fresh = mw_ref.col.get_note(note_id)
        if fresh is None:
            return
        proxy = _NewNoteBrowserProxy(mw_ref, [fresh.id])
        factory = ClientFactory(proxy)
        factory.notes = [fresh]
        factory.on_submit(
            proxy,
            factory.notes,
            suppress_front=_AUTO_BACKGROUND_PREF,
            silent=silent,
        )
    except Exception:
        # Avoid breaking Anki add flow; errors are non-fatal here.
        return


def _ensure_auto_timer() -> None:
    global _AUTO_TIMER
    if _AUTO_TIMER is None:
        timer = QTimer(mw)
        timer.setInterval(2000)
        timer.timeout.connect(_drain_auto_queue)
        _AUTO_TIMER = timer
    if _AUTO_TIMER is not None and not _AUTO_TIMER.isActive():
        _AUTO_TIMER.start()


def _drain_auto_queue() -> None:
    global _AUTO_QUEUE, _AUTO_TIMER
    if ClientFactory.focus_progress_dialog():
        return
    if not _AUTO_QUEUE:
        if _AUTO_TIMER is not None:
            _AUTO_TIMER.stop()
        return
    mw_ref = mw
    if mw_ref is None or getattr(mw_ref, "col", None) is None:
        _AUTO_QUEUE.clear()
        if _AUTO_TIMER is not None:
            _AUTO_TIMER.stop()
        return
    note_id = _AUTO_QUEUE.pop(0)
    fresh = mw_ref.col.get_note(note_id)
    if fresh is None:
        return
    proxy = _NewNoteBrowserProxy(mw_ref, [fresh.id])
    factory = ClientFactory(proxy)
    factory.notes = [fresh]
    silent = True
    set_active_bg_notes([note_id] + list(_AUTO_QUEUE))
    _log_auto_queue("auto_run_start", {"note_id": note_id})
    factory.on_submit(
        proxy,
        factory.notes,
        suppress_front=_AUTO_BACKGROUND_PREF,
        silent=silent,
    )
    dialog = getattr(factory, "progress_dialog", None)
    if dialog is not None:
        if _AUTO_BACKGROUND_PREF:
            dialog.suppress_front = True
            dialog.hide()
            try:
                dialog.showMinimized()
            except Exception:
                pass
        _log_auto_queue(
            "start_dialog",
            {
                "note_id": note_id,
                "suppress_front": getattr(dialog, "suppress_front", False),
                "minimized": dialog.isMinimized(),
            },
        )
        try:
            dialog.background_button.clicked.connect(
                lambda: (_set_auto_background_pref(), setattr(dialog, "suppress_front", True))
            )
        except Exception:
            pass


def _set_auto_background_pref() -> None:
    global _AUTO_BACKGROUND_PREF
    _AUTO_BACKGROUND_PREF = True
    _log_auto_queue("set_background_pref", {"value": True})


def _log_auto_queue(label: str, data: Optional[dict] = None) -> None:
    log_path = Path(__file__).with_name("anki_ai_runtime.log")
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{now}] auto_queue {label} {data or {}}\n")
    except Exception:
        pass


def _as_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    try:
        return bool(int(value))
    except Exception:
        return default


class _NewNoteBrowserProxy:
    """Minimal browser proxy to reuse ClientFactory for newly added notes."""

    def __init__(self, mw_ref, note_ids: list[int]) -> None:
        self.mw = mw_ref
        self._note_ids = note_ids
        self.form = getattr(mw_ref, "form", None)

    def selectedNotes(self) -> list[int]:
        return list(self._note_ids)


def on_setup_menus(browser):
    actions = _create_ai_menu_actions(browser)
    menu = QMenu("Anki AI", browser.form.menubar)
    browser.form.menubar.addMenu(menu)
    menu.addAction(actions.update)
    menu.addAction(actions.manage)
    menu.addAction(actions.progress)
    menu.addAction(actions.youglish_open)
    menu.addAction(actions.youglish_update)
    menu.addAction(actions.oaad_open)
    menu.addAction(actions.oaad_update)
    menu.aboutToShow.connect(actions.refresh_labels)


hooks.addHook("browser.setupMenus", on_setup_menus)



def on_will_show_context_menu(browser, menu):
    actions = _create_ai_menu_actions(browser)
    actions.refresh_labels()
    menu.addAction(actions.update)
    menu.addAction(actions.manage)
    menu.addAction(actions.youglish_open)
    menu.addAction(actions.youglish_update)
    menu.addAction(actions.oaad_open)
    menu.addAction(actions.oaad_update)
    menu.aboutToShow.connect(actions.refresh_labels)


gui_hooks.browser_will_show_context_menu.append(on_will_show_context_menu)
gui_hooks.add_cards_did_add_note.append(_maybe_auto_generate_on_add)
_SCHEDULER = SchedulerManager()


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
