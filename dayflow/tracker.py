from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from dayflow.app_meta import resolve_app_metadata, resolve_browser_tab_category
from dayflow.database import UsageDatabase
from dayflow.window_filter import (
    ActiveWindowInfo,
    get_foreground_window_info,
    should_track_window,
)

_UNSET = object()
MAX_TICK_GAP_SEC = 300.0


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def get_system_idle_seconds() -> float:
    """通过 Windows GetLastInputInfo 获取系统全局无鼠标/键盘操作的空闲秒数。"""
    if os.name != "nt":
        return 0.0
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = kernel32.GetTickCount() - lii.dwTime
            return max(0.0, float(millis) / 1000.0)
    except Exception:
        pass
    return 0.0


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
    """后台前台窗口采样追踪器，支持挂机空闲检测、浏览器二级分类细分、健康疲劳提醒、会话合并与睡眠保护。"""

    def __init__(
        self,
        db: UsageDatabase,
        poll_interval: float = 1.0,
        flush_interval: float = 10.0,
        self_pid: int | None = None,
        idle_threshold_sec: float = 180.0,
        idle_detector: Callable[[], float] | None = None,
        rest_remind_interval_sec: float = 2700.0,
    ) -> None:
        self.db = db
        self.poll_interval = float(poll_interval)
        self.flush_interval = float(flush_interval)
        self._self_pid = os.getpid() if self_pid is None else self_pid

        # 1. 挂机/离线空闲智能检测配置（默认 180 秒无键鼠操作判定为离开电脑）
        self.idle_threshold_sec = float(idle_threshold_sec)
        self._custom_idle_detector = idle_detector is not None
        self._idle_detector = idle_detector or get_system_idle_seconds
        self.is_idle: bool = False
        self.current_idle_sec: float = 0.0

        # 2. 连续专注用眼/久坐疲劳微光提醒配置（默认连续活跃 45 分钟提醒一次）
        self.rest_remind_interval_sec = float(rest_remind_interval_sec)
        self.continuous_active_sec: float = 0.0
        self._health_remind_pending: bool = False

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
        """将当前活跃会话写入数据库，自动应用浏览器二级分类细分。"""
        if self._current is None:
            return
        if end_dt > self._current.start_dt:
            # 浏览器网页二级分类细分判断
            sub_cat = resolve_browser_tab_category(
                self._current.exe_name, self._current.window_title
            )
            effective_cat = sub_cat or self._current.category

            self.db.record_usage_span(
                app_id=self._current.app_id,
                start_dt=self._current.start_dt,
                end_dt=end_dt,
                window_title=self._current.window_title,
                category=effective_cat,
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

    def check_and_consume_health_remind(self) -> bool:
        """检查并消耗疲劳提醒状态（前端调用后重置）。"""
        with self._lock:
            if self._health_remind_pending:
                self._health_remind_pending = False
                return True
            return False

    def tick(
        self,
        now: datetime | None = None,
        window_info: ActiveWindowInfo | None | object = _UNSET,
        idle_sec: float | None = None,
    ) -> None:
        """执行单次前台窗口采样状态更新，融合挂机检测与健康久坐统计。"""
        with self._lock:
            cur_now = now or datetime.now()

            # 1. 检查用户当前空闲秒数
            # 若显式传入 idle_sec 则使用之；
            # 若提供了自定义 detector 或真实运行时（now is None），调用 _idle_detector()；
            # 否则（单测场景且未自定义 detector），默认为活跃 (0.0)
            if idle_sec is not None:
                check_idle = float(idle_sec)
            elif self._custom_idle_detector or now is None:
                check_idle = float(self._idle_detector())
            else:
                check_idle = 0.0

            self.current_idle_sec = max(0.0, check_idle)

            # 当空闲时间达到设定阈值（用户离开电脑），挂机保护触发！
            if self.current_idle_sec >= self.idle_threshold_sec:
                if not self.is_idle:
                    # 刚进入挂机状态：把会话封口，不计入离线后的时间
                    if self._current is not None:
                        end_dt = self._effective_end_dt(cur_now)
                        self._commit_current_until(end_dt)
                        self._current = None
                    self.is_idle = True
                    # 离线超过休息间隔的一半视为真正休息，重置连续专注计时
                    if self.current_idle_sec >= 120.0:
                        self.continuous_active_sec = 0.0
                return

            # 用户有键盘或鼠标操作，解除挂机状态
            if self.is_idle:
                self.is_idle = False

            if window_info is _UNSET:
                info = get_foreground_window_info(self_pid=self._self_pid)
            else:
                raw_info = window_info  # type: ignore[assignment]
                info = (
                    raw_info
                    if should_track_window(raw_info, self_pid=self._self_pid)
                    else None
                )

            # 2. 当前进入锁屏或桌面无窗体状态
            if info is None:
                if self._current is not None:
                    end_dt = self._effective_end_dt(cur_now)
                    self._commit_current_until(end_dt)
                    self._current = None
                return

            app_rec = self._resolve_and_register_app(info)
            app_id = int(app_rec["app_id"])

            # 3. 尚无活跃会话：开启新会话
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
                self.continuous_active_sec += self.poll_interval
                return

            # 4. 同一应用继续处于前台
            if self._current.app_id == app_id:
                gap = (cur_now - self._current.last_tick_dt).total_seconds()
                if gap > MAX_TICK_GAP_SEC:
                    sleep_end = self._current.last_tick_dt + timedelta(
                        seconds=self.poll_interval
                    )
                    self._commit_current_until(sleep_end)
                    self._current.start_dt = cur_now
                    self._current.last_tick_dt = cur_now
                    if info.window_title:
                        self._current.window_title = info.window_title
                    self.continuous_active_sec = 0.0
                    return

                if cur_now > self._current.last_tick_dt:
                    step_sec = (cur_now - self._current.last_tick_dt).total_seconds()
                    self._current.last_tick_dt = cur_now
                    self.continuous_active_sec += step_sec

                if info.window_title:
                    self._current.window_title = info.window_title

                # 检查是否触发疲劳久坐提醒
                if (
                    self.continuous_active_sec >= self.rest_remind_interval_sec
                    and not self._health_remind_pending
                ):
                    self._health_remind_pending = True

                elapsed = (
                    self._current.last_tick_dt - self._current.start_dt
                ).total_seconds()
                if elapsed >= self.flush_interval:
                    self._commit_current_until(self._current.last_tick_dt)
                return

            # 5. 切换到了不同应用：结算旧应用，开启新应用会话
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
            self.continuous_active_sec += self.poll_interval

    def flush(self, now: datetime | None = None) -> None:
        """立即将当前内存中尚未落盘的活跃会话时长写入数据库。"""
        with self._lock:
            if self._current is None:
                return
            target_now = self._current.last_tick_dt if now is None else now
            end_dt = self._effective_end_dt(target_now)
            self._commit_current_until(end_dt)

    def get_current_active(self) -> dict | None:
        """返回当前正在前台活跃的应用信息快照，包含挂机与疲劳提醒状态。"""
        with self._lock:
            if self.is_idle:
                return {
                    "app_id": None,
                    "exe_path": "",
                    "exe_name": "",
                    "display_name": "离开电脑 (空闲)",
                    "category": "other",
                    "icon_base64": "",
                    "window_title": "用户处于挂机离线状态",
                    "start_dt": datetime.now().isoformat(),
                    "last_tick_dt": datetime.now().isoformat(),
                    "unflushed_sec": 0,
                    "is_idle": True,
                    "idle_sec": int(self.current_idle_sec),
                }

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
            sub_cat = resolve_browser_tab_category(
                self._current.exe_name, self._current.window_title
            )
            return {
                "app_id": self._current.app_id,
                "exe_path": self._current.exe_path,
                "exe_name": self._current.exe_name,
                "display_name": self._current.display_name,
                "category": sub_cat or self._current.category,
                "icon_base64": self._current.icon_base64,
                "window_title": self._current.window_title,
                "start_dt": self._current.start_dt.isoformat(),
                "last_tick_dt": self._current.last_tick_dt.isoformat(),
                "unflushed_sec": unflushed,
                "is_idle": False,
                "continuous_active_sec": int(self.continuous_active_sec),
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
