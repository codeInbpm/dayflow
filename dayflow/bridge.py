from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from dayflow.app_meta import CATEGORY_META
from dayflow.database import UsageDatabase
from dayflow.tracker import ForegroundTracker

try:
    import winreg

    HAS_WINREG = True
except ImportError:  # pragma: no cover
    winreg = None  # type: ignore[assignment]
    HAS_WINREG = False

APP_VERSION = "1.0.0"
RUN_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_REG_NAME = "Dayflow"


def _build_autostart_command() -> str:
    """生成写入 Windows 注册表 HKCU\\...\\Run 的开机自启命令行。"""
    exe_path = Path(sys.executable).resolve()
    if getattr(sys, "frozen", False):
        return f'"{exe_path}"'
    main_script = Path(__file__).resolve().parent.parent / "main.py"
    # 若存在 pythonw.exe 则优先使用无控制台窗口的 pythonw.exe
    pythonw = exe_path.with_name("pythonw.exe")
    runner = pythonw if pythonw.is_file() else exe_path
    return f'"{runner}" "{main_script}"'


def _read_registry_autostart() -> bool | None:
    """检查当前 Windows 用户注册表中是否已配置 Dayflow 开机自启。"""
    if not HAS_WINREG or winreg is None:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_REG_PATH,
            0,
            winreg.KEY_READ,
        ) as key:
            val, _ = winreg.QueryValueEx(key, RUN_REG_NAME)
            return bool(val and str(val).strip())
    except FileNotFoundError:
        return False
    except Exception:
        return None


def _write_registry_autostart(enable: bool) -> bool:
    """在当前 Windows 用户注册表 HKCU\\...\\Run 中启用或移除 Dayflow 开机自启。"""
    if not HAS_WINREG or winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_REG_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enable:
                cmd = _build_autostart_command()
                winreg.SetValueEx(key, RUN_REG_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, RUN_REG_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False

try:
    import win32gui
    import win32process

    HAS_WIN32 = True
except ImportError:  # pragma: no cover
    win32gui = None  # type: ignore[assignment]
    win32process = None  # type: ignore[assignment]
    HAS_WIN32 = False

# Win32 窗口控制常量（使用原生异步 API 避免 PyWebView WinForms 跨线程死锁）
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_ASYNCWINDOWPOS = 0x4000

SW_HIDE = 0
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

VK_LBUTTON = 0x01
MIN_WIN_WIDTH = 360
MIN_WIN_HEIGHT = 500

if os.name == "nt":
    # 使用独立 WinDLL("user32") 实例，避免修改全局 ctypes.windll.user32.SetWindowPos.argtypes
    # 导致 pywebview 内部 winforms.move() 传入 None 时抛出 ctypes.ArgumentError 而无法拖动窗口
    _user32 = ctypes.WinDLL("user32")
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    _user32.SetWindowPos.restype = wintypes.BOOL
    _user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.ShowWindowAsync.restype = wintypes.BOOL
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.SetForegroundWindow.restype = wintypes.BOOL
    _user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    _user32.GetCursorPos.restype = wintypes.BOOL
    _user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _user32.GetWindowRect.restype = wintypes.BOOL
    _user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    _user32.GetAsyncKeyState.restype = ctypes.c_short
else:  # pragma: no cover
    _user32 = None


class DayflowBridge:
    """PyWebView JS-Python 桥接层，提供看板聚合查询、软件分类/屏蔽管理与无边框窗口控制。"""

    def __init__(
        self,
        db: UsageDatabase,
        tracker: ForegroundTracker,
        window_getter: Callable[[], Any] | None = None,
        on_quit: Callable[[], Any] | None = None,
    ) -> None:
        self.db = db
        self.tracker = tracker
        self._window_getter = window_getter
        self._on_quit = on_quit
        self._hwnd: int | None = None
        self.always_on_top: bool = False
        self._resizing: bool = False

    def set_window_getter(self, window_getter: Callable[[], Any] | None) -> None:
        """设置或更新 PyWebView 窗口获取函数。"""
        self._window_getter = window_getter

    def set_on_quit(self, on_quit: Callable[[], Any] | None) -> None:
        """设置退出程序回调函数。"""
        self._on_quit = on_quit

    def set_hwnd(self, hwnd: int | None) -> None:
        """缓存主窗口的原生 Win32 HWND 句柄（在 UI 线程 shown 事件中调用）。"""
        self._hwnd = int(hwnd) if hwnd else None

    def _get_window(self) -> Any | None:
        if self._window_getter is None:
            return None
        try:
            return self._window_getter()
        except Exception:
            return None

    def _resolve_hwnd(self, win: Any | None = None) -> int | None:
        """通过缓存或纯 Win32 API 查找当前进程的 Dayflow 窗口句柄，避免跨线程访问 .NET WinForms 属性导致死锁。"""
        if self._hwnd and HAS_WIN32 and win32gui is not None:
            try:
                if win32gui.IsWindow(self._hwnd):
                    return self._hwnd
            except Exception:
                self._hwnd = None

        if win is not None and isinstance(getattr(win, "hwnd", None), int) and win.hwnd > 0:
            self._hwnd = int(win.hwnd)
            return self._hwnd

        if HAS_WIN32 and win32gui is not None and win32process is not None:
            my_pid = os.getpid()
            candidates: list[int] = []

            def _enum_cb(hwnd: int, _extra: Any) -> bool:
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid != my_pid:
                        return True
                    title = win32gui.GetWindowText(hwnd) or ""
                    cls_name = win32gui.GetClassName(hwnd) or ""
                    if title == "Dayflow" or "WindowsForms" in cls_name:
                        candidates.append(int(hwnd))
                except Exception:
                    pass
                return True

            try:
                win32gui.EnumWindows(_enum_cb, None)
            except Exception:
                pass

            if candidates:
                self._hwnd = candidates[0]
                return self._hwnd

        return None

    def get_daily_timeline(
        self,
        date_str: str | None = None,
        end_date_str: str | None = None,
    ) -> list[dict]:
        """按时间顺序返回指定日期（或日期区间）所有未屏蔽软件的使用会话流水。"""
        start_date = date_str or datetime.now().strftime("%Y-%m-%d")
        finish_date = end_date_str or start_date
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
                WHERE s.date_str BETWEEN ? AND ? AND a.is_ignored = 0
                ORDER BY s.date_str ASC, s.hour_bucket ASC, s.start_time ASC, s.id ASC
                """,
                (start_date, finish_date),
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

    def get_dashboard_data(
        self,
        date_str: str | None = None,
        period: str = "day",
    ) -> dict:
        """刷盘当前活跃计时并返回按日/按周/按月看板完整聚合数据。"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        target_date = date_str or today_str
        norm_period = period if period in ("day", "week", "month") else "day"
        self.tracker.flush()

        summary = self.db.get_period_summary(
            target_date,
            period=norm_period,
            today_str=today_str,
        )
        recent_dates = self.db.get_recent_dates(
            days=7,
            ref_date=target_date,
            today_str=today_str,
        )
        timeline = self.get_daily_timeline(
            summary.get("start_date_str", target_date),
            summary.get("end_date_str", target_date),
        )
        active_app = self.tracker.get_current_active()

        return {
            **summary,
            "recent_dates": recent_dates,
            "category_meta": CATEGORY_META,
            "active_app": active_app,
            "always_on_top": self.always_on_top,
            "timeline": timeline,
            "preferences": self.get_preferences(),
        }

    def get_preferences(self) -> dict[str, Any]:
        """获取通用设置（语言、外观、字体大小、开机自启）与版本信息。"""
        prefs = self.db.get_preferences()
        reg_state = _read_registry_autostart()
        if reg_state is not None:
            prefs["auto_start"] = reg_state
        prefs["version"] = APP_VERSION
        return prefs

    def update_preferences(self, updates: dict[str, Any] | None = None) -> dict[str, Any]:
        """更新通用设置，若包含 auto_start 则同步写入/移除 Windows 注册表开机启动项。"""
        payload = dict(updates or {})
        if "auto_start" in payload:
            want_auto = bool(payload["auto_start"])
            _write_registry_autostart(want_auto)

        saved = self.db.update_preferences(payload)
        reg_state = _read_registry_autostart()
        if reg_state is not None:
            saved["auto_start"] = reg_state
        saved["version"] = APP_VERSION
        return saved

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
        """切换或设置窗口置顶状态（采用原生 Win32 SetWindowPos + SWP_ASYNCWINDOWPOS 杜绝 WinForms TopMost 死锁）。"""
        self.always_on_top = (not self.always_on_top) if state is None else bool(state)
        win = self._get_window()
        hwnd = self._resolve_hwnd(win)

        if hwnd and _user32 is not None:
            try:
                insert_after = HWND_TOPMOST if self.always_on_top else HWND_NOTOPMOST
                flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS
                _user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags)
            except Exception:
                pass
            if win is not None:
                try:
                    # 仅同步私有字段，不触发 pywebview Window.on_top setter 的跨线程 WinForms TopMost 赋值
                    setattr(win, "_Window__on_top", self.always_on_top)
                except Exception:
                    pass
        elif win is not None and not hasattr(win, "gui"):
            # 单元测试 DummyWindow 兜底
            try:
                win.on_top = self.always_on_top
            except Exception:
                pass

        return {"ok": True, "always_on_top": self.always_on_top}

    def minimize_window(self) -> dict:
        """最小化当前窗口（优先采用异步 ShowWindowAsync 避免阻塞 JS Bridge 回调）。"""
        win = self._get_window()
        hwnd = self._resolve_hwnd(win)
        if hwnd and _user32 is not None:
            try:
                _user32.ShowWindowAsync(hwnd, SW_MINIMIZE)
                return {"ok": True}
            except Exception:
                pass

        if win is not None:
            try:
                win.minimize()
            except Exception:
                pass
        return {"ok": True}

    def hide_to_tray(self) -> dict:
        """隐藏窗口至系统托盘（优先采用异步 ShowWindowAsync 避免阻塞 JS Bridge 回调）。"""
        win = self._get_window()
        hwnd = self._resolve_hwnd(win)
        if hwnd and _user32 is not None:
            try:
                _user32.ShowWindowAsync(hwnd, SW_HIDE)
                return {"ok": True, "hidden": True}
            except Exception:
                pass

        if win is not None:
            try:
                win.hide()
            except Exception:
                pass
        return {"ok": True, "hidden": True}

    def show_window(self) -> dict:
        """从系统托盘唤醒并显示窗口（恢复置顶状态并激活至前台）。"""
        win = self._get_window()
        hwnd = self._resolve_hwnd(win)
        if hwnd and _user32 is not None:
            try:
                _user32.ShowWindowAsync(hwnd, SW_SHOW)
                _user32.ShowWindowAsync(hwnd, SW_RESTORE)
                _user32.SetForegroundWindow(hwnd)
                if self.always_on_top:
                    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS
                    _user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
                return {"ok": True, "hidden": False}
            except Exception:
                pass

        if win is not None:
            try:
                win.show()
                win.restore()
            except Exception:
                pass
        return {"ok": True, "hidden": False}

    def quit_app(self) -> dict:
        """立即隐藏窗口、保存当前正在进行的计时会话并直接退出结束整个程序（0延迟关闭）。"""
        # 1. 第一时间异步隐藏主窗口，让用户点击关闭按钮的瞬间（<5ms）窗口立即从屏幕消失
        try:
            win = self._get_window()
            hwnd = self._resolve_hwnd(win)
            if hwnd and _user32 is not None:
                _user32.ShowWindowAsync(hwnd, SW_HIDE)
        except Exception:
            pass

        # 2. 将内存中未刷盘的活跃秒数写入 SQLite
        try:
            self.tracker.flush()
        except Exception:
            pass

        # 3. 触发进程立刻终止回调
        if self._on_quit is not None:
            try:
                self._on_quit()
            except Exception:
                pass
        return {"ok": True, "quitting": True}

    def start_window_resize(self, edge: str = "se") -> dict:
        """在无边框窗口边缘/四角按下鼠标时启动原生 120Hz 窗口缩放追踪循环。"""
        norm_edge = str(edge or "se").strip().lower()
        valid_edges = {"n", "s", "e", "w", "nw", "ne", "sw", "se"}
        if norm_edge not in valid_edges:
            return {"ok": False, "reason": "invalid_edge"}

        win = self._get_window()
        hwnd = self._resolve_hwnd(win)
        if not hwnd or _user32 is None:
            return {"ok": False, "reason": "no_hwnd"}

        if self._resizing:
            return {"ok": True, "edge": norm_edge}

        pt_start = wintypes.POINT()
        rect_start = wintypes.RECT()
        if not _user32.GetCursorPos(ctypes.byref(pt_start)):
            return {"ok": False}
        if not _user32.GetWindowRect(hwnd, ctypes.byref(rect_start)):
            return {"ok": False}

        init_left = int(rect_start.left)
        init_top = int(rect_start.top)
        init_right = int(rect_start.right)
        init_bottom = int(rect_start.bottom)
        init_w = max(MIN_WIN_WIDTH, init_right - init_left)
        init_h = max(MIN_WIN_HEIGHT, init_bottom - init_top)
        start_mx = int(pt_start.x)
        start_my = int(pt_start.y)

        self._resizing = True

        def _resize_loop() -> None:
            try:
                last_rect = (init_left, init_top, init_w, init_h)
                cur_pt = wintypes.POINT()
                flags = SWP_NOZORDER | SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS
                while True:
                    # 检查鼠标左键是否仍然按住 (最高位 0x8000 表示当前按下)
                    if (_user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000) == 0:
                        break
                    if not _user32.GetCursorPos(ctypes.byref(cur_pt)):
                        break

                    dx = int(cur_pt.x) - start_mx
                    dy = int(cur_pt.y) - start_my

                    new_x = init_left
                    new_y = init_top
                    new_w = init_w
                    new_h = init_h

                    if "e" in norm_edge:
                        new_w = max(MIN_WIN_WIDTH, init_w + dx)
                    elif "w" in norm_edge:
                        new_w = max(MIN_WIN_WIDTH, init_w - dx)
                        new_x = init_right - new_w

                    if "s" in norm_edge:
                        new_h = max(MIN_WIN_HEIGHT, init_h + dy)
                    elif "n" in norm_edge:
                        new_h = max(MIN_WIN_HEIGHT, init_h - dy)
                        new_y = init_bottom - new_h

                    cur_rect = (new_x, new_y, new_w, new_h)
                    if cur_rect != last_rect:
                        _user32.SetWindowPos(
                            hwnd,
                            0,
                            new_x,
                            new_y,
                            new_w,
                            new_h,
                            flags,
                        )
                        last_rect = cur_rect

                    time.sleep(0.008)
            except Exception:
                pass
            finally:
                self._resizing = False

        threading.Thread(target=_resize_loop, daemon=True).start()
        return {"ok": True, "edge": norm_edge}
