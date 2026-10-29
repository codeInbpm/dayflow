from __future__ import annotations

import os
from dataclasses import dataclass

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:  # pragma: no cover
    HAS_PSUTIL = False

try:
    import win32gui
    import win32process

    HAS_WIN32 = True
except ImportError:  # pragma: no cover
    HAS_WIN32 = False


# 系统底层进程与壳组件黑名单（统一小写）
SYSTEM_EXE_BLACKLIST: frozenset[str] = frozenset(
    {
        "svchost.exe",
        "searchhost.exe",
        "searchapp.exe",
        "startmenuexperiencehost.exe",
        "shellexperiencehost.exe",
        "textinputhost.exe",
        "lockapp.exe",
        "logonui.exe",
        "dwm.exe",
        "conhost.exe",
        "dllhost.exe",
        "sihost.exe",
        "taskhostw.exe",
        "ctfmon.exe",
        "applicationframehost.exe",
        "widgets.exe",
        "widgetservice.exe",
        "gamebar.exe",
        "gamebarftserver.exe",
        "fontdrvhost.exe",
        "csrss.exe",
        "smss.exe",
        "services.exe",
        "lsass.exe",
        "wininit.exe",
        "winlogon.exe",
        "spoolsv.exe",
        "audiodg.exe",
        "securityhealthsystray.exe",
        "securityhealthservice.exe",
        "runtimebroker.exe",
        "backgroundtaskhost.exe",
        "systemsettingsbroker.exe",
        "smartscreen.exe",
        "consent.exe",
        "werfault.exe",
        "wermgr.exe",
        "chsime.exe",
        "dayflow.exe",
        "msedgewebview2.exe",
    }
)

EXPLORER_ALLOWED_CLASSES: tuple[str, ...] = ("CabinetWClass", "ExploreWClass")

SHELL_BACKGROUND_CLASSES: frozenset[str] = frozenset(
    {
        "Progman",
        "WorkerW",
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
        "NotifyIconOverflowWindow",
        "MultitaskingViewFrame",
        "ForegroundStaging",
    }
)


@dataclass
class ActiveWindowInfo:
    hwnd: int
    pid: int
    exe_path: str
    exe_name: str
    window_title: str
    window_class: str


def resolve_uwp_child_pid(host_pid: int, child_pids: list[int]) -> int | None:
    """从 ApplicationFrameHost 子窗口 PID 列表中找到第一个不同于宿主 PID 的真实 UWP 进程 PID。"""
    for cpid in child_pids:
        if cpid and cpid > 0 and cpid != host_pid:
            return int(cpid)
    return None


def should_track_window(
    info: ActiveWindowInfo | None,
    self_pid: int | None = None,
) -> bool:
    """判断前台窗口是否属于应被计入使用时间的用户软件。"""
    if info is None:
        return False
    if info.hwnd <= 0 or info.pid <= 0:
        return False
    if self_pid is not None and info.pid == self_pid:
        return False

    raw_name = (info.exe_name or "").strip()
    if not raw_name and info.exe_path:
        raw_name = os.path.basename(info.exe_path.replace("\\", "/"))
    exe_lower = raw_name.lower()
    if not exe_lower:
        return False

    if exe_lower in SYSTEM_EXE_BLACKLIST:
        return False

    win_class = (info.window_class or "").strip()
    win_title = (info.window_title or "").strip()

    if win_class in SHELL_BACKGROUND_CLASSES:
        return False

    if exe_lower == "explorer.exe":
        return win_class in EXPLORER_ALLOWED_CLASSES and bool(win_title)

    return True


def _query_process_exe(pid: int) -> tuple[str, str]:
    """根据 PID 获取 (exe_path, exe_name)，遇到权限或进程退出异常时返回空串。"""
    if not HAS_PSUTIL or pid <= 0:
        return "", ""
    try:
        proc = psutil.Process(pid)
        exe_path = proc.exe() or ""
        exe_name = proc.name() or ""
        if not exe_name and exe_path:
            exe_name = os.path.basename(exe_path.replace("\\", "/"))
        return exe_path, exe_name
    except Exception:
        return "", ""


def _collect_child_window_pids(hwnd: int) -> list[int]:
    """枚举指定父窗口的所有子窗口并返回其所属进程 PID 列表。"""
    if not HAS_WIN32 or hwnd <= 0:
        return []
    child_pids: list[int] = []

    def _enum_cb(child_hwnd: int, _extra: object) -> bool:
        try:
            _, cpid = win32process.GetWindowThreadProcessId(child_hwnd)
            if cpid and cpid > 0:
                child_pids.append(int(cpid))
        except Exception:
            pass
        return True

    try:
        win32gui.EnumChildWindows(hwnd, _enum_cb, None)
    except Exception:
        pass
    return child_pids


def get_foreground_window_info(self_pid: int | None = None) -> ActiveWindowInfo | None:
    """获取当前前台活动窗口信息，对 UWP 宿主窗口进行子窗口 PID 穿透并执行过滤。"""
    if not HAS_WIN32 or not HAS_PSUTIL:
        return None

    effective_self_pid = os.getpid() if self_pid is None else self_pid

    try:
        hwnd = int(win32gui.GetForegroundWindow())
    except Exception:
        return None

    if hwnd <= 0:
        return None

    try:
        if hasattr(win32gui, "IsWindowVisible") and not win32gui.IsWindowVisible(hwnd):
            return None
        if hasattr(win32gui, "IsIconic") and win32gui.IsIconic(hwnd):
            return None
    except Exception:
        pass

    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        pid = int(pid)
    except Exception:
        return None

    if pid <= 0:
        return None

    try:
        window_title = (win32gui.GetWindowText(hwnd) or "").strip()
    except Exception:
        window_title = ""

    try:
        window_class = (win32gui.GetClassName(hwnd) or "").strip()
    except Exception:
        window_class = ""

    exe_path, exe_name = _query_process_exe(pid)

    # UWP 宿主进程穿透
    if (
        exe_name.lower() == "applicationframehost.exe"
        or window_class == "ApplicationFrameWindow"
    ):
        child_pids = _collect_child_window_pids(hwnd)
        real_pid = resolve_uwp_child_pid(pid, child_pids)
        if real_pid is not None:
            uwp_path, uwp_name = _query_process_exe(real_pid)
            if uwp_path or uwp_name:
                pid = real_pid
                exe_path = uwp_path
                exe_name = uwp_name

    if not exe_path and not exe_name:
        return None

    info = ActiveWindowInfo(
        hwnd=hwnd,
        pid=pid,
        exe_path=exe_path,
        exe_name=exe_name,
        window_title=window_title,
        window_class=window_class,
    )
    if not should_track_window(info, self_pid=effective_self_pid):
        return None
    return info


def is_fullscreen_or_game_active() -> bool:
    """使用 Windows Shell API (SHQueryUserNotificationState) 检查当前用户是否处于全屏独占游戏或全屏免打扰状态。"""
    try:
        import ctypes

        state = ctypes.c_int()
        res = ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state))
        if res == 0:
            # 2: QUNS_BUSY (全屏独占游戏/全屏视频)
            # 3: QUNS_RUNNING_D_NOT_PRESENT (Direct3D 全屏独占)
            # 4: QUNS_PRESENTATION_MODE (全屏演示模式)
            return state.value in (2, 3, 4)
    except Exception:
        pass
    return False

