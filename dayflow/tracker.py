from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

from dayflow.app_meta import resolve_app_metadata
from dayflow.database import UsageDatabase
from dayflow.window_filter import (
    ActiveWindowInfo,
    get_foreground_window_info,
    should_track_window,
)

_UNSET = object()
MAX_TICK_GAP_SEC = 300.0


@dataclass
class _ActiveSession:
    app_id: int
    exe_path: str
    exe_name: str
    display_name: str
    category: str
    icon_base64: str
    window_title: str
    start_dt: datetime
    last_tick_dt: datetime


class ForegroundTracker:
    """后台 1 秒间隔前台窗口采样追踪器，支持会话合并、周期性刷盘与睡眠间隙保护。"""

    def __init__(
        self,
        db: UsageDatabase,
        poll_interval: float = 1.0,
        flush_interval: float = 10.0,
        self_pid: int | None = None,
    ) -> None:
        self.db = db
        self.poll_interval = float(poll_interval)
        self.flush_interval = float(flush_interval)
        self._self_pid = os.getpid() if self_pid is None else self_pid

        self._lock = threading.RLock()
        self._app_cache: dict[str, dict] = {}
        self._current: _ActiveSession | None = None

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _resolve_and_register_app(self, info: ActiveWindowInfo) -> dict:
        norm_key = (info.exe_path or info.exe_name).strip().lower()
        cached = self._app_cache.get(norm_key)
        if cached is not None:
            return cached

        meta = resolve_app_metadata(info.exe_path, info.exe_name)
        exe_path = info.exe_path or meta["exe_path"]
        exe_name = info.exe_name or meta["exe_name"]
        app_id = self.db.upsert_app(
            exe_path=exe_path,
            exe_name=exe_name,
            display_name=meta["display_name"],
            category=meta["category"],
            icon_base64=meta["icon_base64"],
        )
        record = {
            "app_id": app_id,
            "exe_path": exe_path,
            "exe_name": exe_name,
            "display_name": meta["display_name"],
            "category": meta["category"],
            "icon_base64": meta["icon_base64"],
        }
        self._app_cache[norm_key] = record
        return record

    def _commit_current_until(self, end_dt: datetime) -> None:
        """将当前活跃会话记录到 end_dt 并推进或清除状态（调用方需持有 self._lock）。"""
        if self._current is None:
            return
        if end_dt > self._current.start_dt:
            self.db.record_usage_span(
                app_id=self._current.app_id,
                start_dt=self._current.start_dt,
                end_dt=end_dt,
                window_title=self._current.window_title,
            )
        self._current.start_dt = end_dt
        self._current.last_tick_dt = end_dt

    def _effective_end_dt(self, now: datetime) -> datetime:
        """若距离上次采样超过 MAX_TICK_GAP_SEC（如系统睡眠），仅按 poll_interval 累加最后一次采样。"""
        assert self._current is not None
        gap = (now - self._current.last_tick_dt).total_seconds()
        if gap > MAX_TICK_GAP_SEC:
            return self._current.last_tick_dt + timedelta(seconds=self.poll_interval)
        if now < self._current.last_tick_dt:
            return self._current.last_tick_dt
        return now

    def tick(
        self,
        now: datetime | None = None,
        window_info: ActiveWindowInfo | None | object = _UNSET,
    ) -> None:
        """执行单次前台窗口采样状态更新。"""
        with self._lock:
            cur_now = now or datetime.now()
            if window_info is _UNSET:
                info = get_foreground_window_info(self_pid=self._self_pid)
            else:
                raw_info = window_info  # type: ignore[assignment]
                info = (
                    raw_info
                    if should_track_window(raw_info, self_pid=self._self_pid)
                    else None
                )

            # 1. 当前进入空闲/锁屏/桌面状态
            if info is None:
                if self._current is not None:
                    end_dt = self._effective_end_dt(cur_now)
                    self._commit_current_until(end_dt)
                    self._current = None
                return

            app_rec = self._resolve_and_register_app(info)
            app_id = int(app_rec["app_id"])

            # 2. 尚无活跃会话：开启新会话
            if self._current is None:
                self._current = _ActiveSession(
                    app_id=app_id,
                    exe_path=app_rec["exe_path"],
                    exe_name=app_rec["exe_name"],
                    display_name=app_rec["display_name"],
                    category=app_rec["category"],
                    icon_base64=app_rec["icon_base64"],
                    window_title=info.window_title or "",
                    start_dt=cur_now,
                    last_tick_dt=cur_now,
                )
                return

            # 3. 同一应用继续处于前台
            if self._current.app_id == app_id:
                gap = (cur_now - self._current.last_tick_dt).total_seconds()
                if gap > MAX_TICK_GAP_SEC:
                    # 发生睡眠或长时间挂起：先按 1 个 poll_interval 结算挂起前会话，再从 cur_now 重新开始
                    sleep_end = self._current.last_tick_dt + timedelta(
                        seconds=self.poll_interval
                    )
                    self._commit_current_until(sleep_end)
                    self._current.start_dt = cur_now
                    self._current.last_tick_dt = cur_now
                    if info.window_title:
                        self._current.window_title = info.window_title
                    return

                if cur_now > self._current.last_tick_dt:
                    self._current.last_tick_dt = cur_now
                if info.window_title:
                    self._current.window_title = info.window_title

                elapsed = (
                    self._current.last_tick_dt - self._current.start_dt
                ).total_seconds()
                if elapsed >= self.flush_interval:
                    self._commit_current_until(self._current.last_tick_dt)
                return

            # 4. 切换到了不同应用：先结算旧应用，再开启新应用会话
            end_dt = self._effective_end_dt(cur_now)
            self._commit_current_until(end_dt)
            self._current = _ActiveSession(
                app_id=app_id,
                exe_path=app_rec["exe_path"],
                exe_name=app_rec["exe_name"],
                display_name=app_rec["display_name"],
                category=app_rec["category"],
                icon_base64=app_rec["icon_base64"],
                window_title=info.window_title or "",
                start_dt=cur_now,
                last_tick_dt=cur_now,
            )

    def flush(self, now: datetime | None = None) -> None:
        """立即将当前内存中尚未落盘的活跃会话时长写入数据库。"""
        with self._lock:
            if self._current is None:
                return
            target_now = self._current.last_tick_dt if now is None else now
            end_dt = self._effective_end_dt(target_now)
            self._commit_current_until(end_dt)

    def get_current_active(self) -> dict | None:
        """返回当前正在前台活跃的应用信息快照。"""
        with self._lock:
            if self._current is None:
                return None
            unflushed = max(
                0,
                int(
                    round(
                        (
                            self._current.last_tick_dt - self._current.start_dt
                        ).total_seconds()
                    )
                ),
            )
            return {
                "app_id": self._current.app_id,
                "exe_path": self._current.exe_path,
                "exe_name": self._current.exe_name,
                "display_name": self._current.display_name,
                "category": self._current.category,
                "icon_base64": self._current.icon_base64,
                "window_title": self._current.window_title,
                "start_dt": self._current.start_dt.isoformat(),
                "last_tick_dt": self._current.last_tick_dt.isoformat(),
                "unflushed_sec": unflushed,
            }

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception:
                pass
            if self._stop_event.wait(self.poll_interval):
                break

    def start(self) -> None:
        """启动后台守护采样线程。"""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="DayflowForegroundTracker",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        """停止后台采样线程并将未刷盘时长写入数据库。"""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(2.0, self.poll_interval * 2))
        with self._lock:
            self._thread = None
            self.flush()
            self._current = None
