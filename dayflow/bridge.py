from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from dayflow.app_meta import CATEGORY_META
from dayflow.database import UsageDatabase
from dayflow.tracker import ForegroundTracker


class DayflowBridge:
    """PyWebView JS-Python 桥接层，提供看板聚合查询、软件分类/屏蔽管理与无边框窗口控制。"""

    def __init__(
        self,
        db: UsageDatabase,
        tracker: ForegroundTracker,
        window_getter: Callable[[], Any] | None = None,
    ) -> None:
        self.db = db
        self.tracker = tracker
        self._window_getter = window_getter
        self.always_on_top: bool = False

    def set_window_getter(self, window_getter: Callable[[], Any] | None) -> None:
        """设置或更新 PyWebView 窗口获取函数。"""
        self._window_getter = window_getter

    def _get_window(self) -> Any | None:
        if self._window_getter is None:
            return None
        try:
            return self._window_getter()
        except Exception:
            return None

    def get_daily_timeline(self, date_str: str | None = None) -> list[dict]:
        """按时间顺序返回指定日期所有未屏蔽软件的使用会话流水。"""
        target_date = date_str or datetime.now().strftime("%Y-%m-%d")
        with self.db._lock:
            rows = self.db._conn.execute(
                """
                SELECT
                    s.id,
                    s.app_id,
                    s.date_str,
                    s.hour_bucket,
                    s.start_time,
                    s.end_time,
                    s.duration_sec,
                    s.last_window_title,
                    a.exe_path,
                    a.exe_name,
                    a.display_name,
                    a.category,
                    a.icon_base64
                FROM usage_sessions s
                JOIN apps a ON a.id = s.app_id
                WHERE s.date_str = ? AND a.is_ignored = 0
                ORDER BY s.hour_bucket ASC, s.start_time ASC, s.id ASC
                """,
                (target_date,),
            ).fetchall()

            return [
                {
                    "id": int(r["id"]),
                    "app_id": int(r["app_id"]),
                    "date_str": str(r["date_str"]),
                    "hour_bucket": int(r["hour_bucket"]),
                    "start_time": str(r["start_time"]),
                    "end_time": str(r["end_time"]),
                    "duration_sec": int(r["duration_sec"]),
                    "last_window_title": str(r["last_window_title"] or ""),
                    "exe_path": str(r["exe_path"]),
                    "exe_name": str(r["exe_name"]),
                    "display_name": str(r["display_name"]),
                    "category": str(r["category"]),
                    "icon_base64": str(r["icon_base64"] or ""),
                }
                for r in rows
            ]

    def get_dashboard_data(self, date_str: str | None = None) -> dict:
        """刷盘当前活跃计时并返回看板完整聚合数据。"""
        target_date = date_str or datetime.now().strftime("%Y-%m-%d")
        self.tracker.flush()

        summary = self.db.get_daily_summary(target_date)
        recent_dates = self.db.get_recent_dates(days=7, ref_date=target_date)
        timeline = self.get_daily_timeline(target_date)
        active_app = self.tracker.get_current_active()

        return {
            **summary,
            "recent_dates": recent_dates,
            "category_meta": CATEGORY_META,
            "active_app": active_app,
            "always_on_top": self.always_on_top,
            "timeline": timeline,
        }

    def get_app_detail(self, app_id: int, date_str: str | None = None) -> dict:
        """刷盘当前活跃计时并返回单个软件在指定日期的小时分布与会话明细。"""
        target_date = date_str or datetime.now().strftime("%Y-%m-%d")
        self.tracker.flush()
        return self.db.get_app_daily_sessions(int(app_id), target_date)

    def update_app(
        self,
        app_id: int,
        category: str | dict | None = None,
        display_name: str | None = None,
        is_ignored: bool | None = None,
    ) -> dict:
        """修改软件分类、显示名称或屏蔽状态，并同步更新采集器内存缓存。"""
        if isinstance(category, dict):
            payload = category
            category = payload.get("category")
            display_name = payload.get("display_name", display_name)
            is_ignored = payload.get("is_ignored", is_ignored)

        target_id = int(app_id)
        updated = self.db.update_app_settings(
            target_id,
            category=category,
            display_name=display_name,
            is_ignored=is_ignored,
        )

        with self.tracker._lock:
            for key, rec in list(self.tracker._app_cache.items()):
                if int(rec.get("app_id", -1)) == target_id:
                    rec["category"] = updated["category"]
                    rec["display_name"] = updated["display_name"]
                    rec["icon_base64"] = updated["icon_base64"]

            norm_key = (updated.get("exe_path") or updated.get("exe_name") or "").strip().lower()
            if norm_key and norm_key in self.tracker._app_cache:
                self.tracker._app_cache[norm_key]["category"] = updated["category"]
                self.tracker._app_cache[norm_key]["display_name"] = updated["display_name"]

            if self.tracker._current is not None and self.tracker._current.app_id == target_id:
                self.tracker._current.category = updated["category"]
                self.tracker._current.display_name = updated["display_name"]

        return updated

    def get_ignored_apps(self) -> list[dict]:
        """获取所有被用户屏蔽的软件列表。"""
        return self.db.get_ignored_apps()

    def toggle_always_on_top(self, state: bool | None = None) -> dict:
        """切换或设置窗口置顶状态。"""
        self.always_on_top = (not self.always_on_top) if state is None else bool(state)
        win = self._get_window()
        if win is not None:
            try:
                win.on_top = self.always_on_top
            except Exception:
                pass
        return {"ok": True, "always_on_top": self.always_on_top}

    def minimize_window(self) -> dict:
        """最小化当前窗口。"""
        win = self._get_window()
        if win is not None:
            try:
                win.minimize()
            except Exception:
                pass
        return {"ok": True}

    def hide_to_tray(self) -> dict:
        """隐藏窗口至系统托盘。"""
        win = self._get_window()
        if win is not None:
            try:
                win.hide()
            except Exception:
                pass
        return {"ok": True, "hidden": True}

    def show_window(self) -> dict:
        """从系统托盘唤醒并显示窗口。"""
        win = self._get_window()
        if win is not None:
            try:
                win.show()
                win.restore()
            except Exception:
                pass
        return {"ok": True, "hidden": False}
