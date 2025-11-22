"""Background scheduler for periodic note processing."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from aqt import gui_hooks, mw
from aqt.qt import QTimer

from .client_factory import ClientFactory
from .settings import SettingsNames, get_settings


@dataclass
class ScheduleConfig:
    enabled: bool
    query: str
    interval_minutes: int
    batch_size: int
    daily_limit: int
    notice_seconds: int
    next_run_ts: float
    daily_count: int


class SchedulerManager:
    """Manages periodic processing based on saved settings."""

    def __init__(self) -> None:
        self._timer: Optional[QTimer] = None
        self._notice_timer: Optional[QTimer] = None
        self._pending_run = False
        self._paused_until: float = 0.0
        self._notice_deadline: float = 0.0
        gui_hooks.profile_did_open.append(self.start)
        gui_hooks.profile_will_close.append(self.stop)

    def start(self) -> None:
        self.stop()
        settings, _ = get_settings()
        cfg = self._load_config(settings)
        if not cfg.enabled:
            return
        self._timer = QTimer(mw)
        self._timer.setInterval(max(1, cfg.interval_minutes) * 60 * 1000)
        self._timer.timeout.connect(self._on_timer)
        self._timer.start()

    def stop(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer.deleteLater()
        if self._notice_timer:
            self._notice_timer.stop()
            self._notice_timer.deleteLater()
        self._timer = None
        self._notice_timer = None
        self._pending_run = False

    def _on_timer(self) -> None:
        now = time.time()
        if self._paused_until and now < self._paused_until:
            return
        if ClientFactory.focus_progress_dialog():
            return
        settings, _ = get_settings()
        cfg = self._load_config(settings)
        if not cfg.enabled:
            return
        if cfg.daily_limit and cfg.daily_count >= cfg.daily_limit:
            return
        if cfg.next_run_ts and now < cfg.next_run_ts:
            return
        self._schedule_warning(cfg)

    def _schedule_warning(self, cfg: ScheduleConfig) -> None:
        self._pending_run = True
        self._notice_deadline = time.time() + cfg.notice_seconds
        if self._notice_timer:
            self._notice_timer.stop()
            self._notice_timer.deleteLater()
        if cfg.notice_seconds <= 0:
            self._run_batch(cfg)
            return
        self._notice_timer = QTimer(mw)
        self._notice_timer.setInterval(cfg.notice_seconds * 1000)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.timeout.connect(lambda: self._run_batch(cfg))
        self._notice_timer.start()
        if mw is not None:
            mw.progress.start(
                label=(
                    f"{cfg.notice_seconds} 秒后将自动处理笔记（每批最多 {cfg.batch_size} 条，"
                    f"每日上限 {cfg.daily_limit}）。点击取消以跳过本次。"
                ),
                parent=mw,
                immediate=True,
                cancel_callback=self._cancel_pending,
            )

    def _cancel_pending(self) -> None:
        self._pending_run = False
        if self._notice_timer:
            self._notice_timer.stop()
            self._notice_timer.deleteLater()
            self._notice_timer = None
        if mw is not None:
            mw.progress.finish()

    def _run_batch(self, cfg: ScheduleConfig) -> None:
        self._pending_run = False
        if mw is not None:
            mw.progress.finish()
        collection = getattr(mw, "col", None)
        if collection is None:
            return
        note_ids = []
        try:
            note_ids = collection.find_notes(cfg.query) if cfg.query else []
        except Exception:
            note_ids = []
        if not note_ids:
            self._update_next_run(cfg.interval_minutes)
            return
        limited = note_ids[: cfg.batch_size]
        browser_proxy = _ScheduledBrowserProxy(mw, limited)
        factory = ClientFactory(browser_proxy)
        factory.notes = [collection.get_note(nid) for nid in limited if collection.get_note(nid)]
        def on_done():
            self._bump_daily_count(cfg, len(factory.notes))
            self._update_next_run(cfg.interval_minutes)
            if mw is not None:
                mw.reset()
        factory.on_submit(browser_proxy, factory.notes)

    def _bump_daily_count(self, cfg: ScheduleConfig, count: int) -> None:
        settings, _ = get_settings()
        today = time.strftime("%Y-%m-%d")
        stored_day = settings.value("schedule_daily_day", defaultValue="", type=str) or ""
        if stored_day != today:
            settings.setValue("schedule_daily_day", today)
            settings.setValue(SettingsNames.SCHEDULE_DAILY_COUNT_SETTING_NAME, 0)
        current = int(settings.value(SettingsNames.SCHEDULE_DAILY_COUNT_SETTING_NAME, defaultValue=0) or 0)
        settings.setValue(SettingsNames.SCHEDULE_DAILY_COUNT_SETTING_NAME, current + count)

    def _update_next_run(self, interval_minutes: int) -> None:
        settings, _ = get_settings()
        next_ts = time.time() + max(1, interval_minutes) * 60
        settings.setValue(SettingsNames.SCHEDULE_NEXT_RUN_TS_SETTING_NAME, next_ts)

    def _load_config(self, settings) -> ScheduleConfig:
        enabled = settings.value(SettingsNames.SCHEDULE_ENABLED_SETTING_NAME, defaultValue=False)
        if isinstance(enabled, str):
            enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
        query = settings.value(SettingsNames.SCHEDULE_QUERY_SETTING_NAME, defaultValue="", type=str) or ""
        interval = int(settings.value(SettingsNames.SCHEDULE_INTERVAL_MIN_SETTING_NAME, defaultValue=10) or 10)
        batch_size = int(settings.value(SettingsNames.SCHEDULE_BATCH_SIZE_SETTING_NAME, defaultValue=5) or 5)
        daily_limit = int(settings.value(SettingsNames.SCHEDULE_DAILY_LIMIT_SETTING_NAME, defaultValue=30) or 30)
        notice_seconds = int(settings.value(SettingsNames.SCHEDULE_NOTICE_SECONDS_SETTING_NAME, defaultValue=30) or 30)
        next_run_ts = float(settings.value(SettingsNames.SCHEDULE_NEXT_RUN_TS_SETTING_NAME, defaultValue=0) or 0)
        daily_count = int(settings.value(SettingsNames.SCHEDULE_DAILY_COUNT_SETTING_NAME, defaultValue=0) or 0)
        return ScheduleConfig(
            enabled=bool(enabled),
            query=query,
            interval_minutes=max(1, interval),
            batch_size=max(1, batch_size),
            daily_limit=max(0, daily_limit),
            notice_seconds=max(0, notice_seconds),
            next_run_ts=next_run_ts,
            daily_count=max(0, daily_count),
        )


class _ScheduledBrowserProxy:
    """Minimal proxy to satisfy ClientFactory with chosen note ids."""

    def __init__(self, mw_ref, note_ids: list[int]) -> None:
        self.mw = mw_ref
        self._note_ids = note_ids
        self.form = getattr(mw_ref, "form", None)

    def selectedNotes(self) -> list[int]:
        return list(self._note_ids)

