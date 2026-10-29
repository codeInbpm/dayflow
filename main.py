from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from dayflow.bridge import DayflowBridge
from dayflow.database import UsageDatabase
from dayflow.tracker import ForegroundTracker
from dayflow.tray import TrayController, create_tray_icon_image


def get_resource_dir() -> Path:
    """获取静态资源根目录（兼容 PyInstaller 单文件/文件夹打包模式与源码开发模式）。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).resolve()
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_default_db_path() -> Path:
    """获取默认 SQLite 数据库存储路径（打包后优先存放在 exe 同级 data/ 目录，无写权限时回退到 %LOCALAPPDATA%/Dayflow）。"""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidate_dir = exe_dir / "data"
        try:
            candidate_dir.mkdir(parents=True, exist_ok=True)
            test_file = candidate_dir / ".write_probe"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            return candidate_dir / "dayflow.db"
        except Exception:
            local_appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
            fallback_dir = local_appdata / "Dayflow" / "data"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            return fallback_dir / "dayflow.db"
    return Path(__file__).resolve().parent / "data" / "dayflow.db"


BASE_DIR = get_resource_dir()
DEFAULT_DB_PATH = get_default_db_path()
DIST_INDEX_PATH = BASE_DIR / "frontend" / "dist" / "index.html"
ICON_PATH = BASE_DIR / "assets" / "dayflow.ico"
DEV_SERVER_URL = "http://localhost:5173"

_SINGLE_INSTANCE_MUTEX = None


def ensure_app_icon_file() -> Path | None:
    """确保 assets/dayflow.ico 存在，供 pywebview 主线程加载为任务栏与窗口图标。"""
    if ICON_PATH.is_file():
        return ICON_PATH
    fallback_path = DEFAULT_DB_PATH.parent / "dayflow.ico"
    if fallback_path.is_file():
        return fallback_path
    for candidate in (ICON_PATH, fallback_path):
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            img = create_tray_icon_image(256)
            img.save(
                candidate,
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
            )
            return candidate
        except Exception:
            continue
    return None


def set_windows_app_user_model_id() -> None:
    """设置独立 Windows AppUserModelID，避免任务栏将窗口归入 python.exe 默认分组。"""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Dayflow.Desktop.TimeTracker.v1"
        )
    except Exception:
        pass


def ensure_single_instance() -> bool:
    """确保同一台电脑只运行一个 Dayflow 实例；若已运行则异步唤醒已有窗口并返回 False。"""
    global _SINGLE_INSTANCE_MUTEX
    if sys.platform != "win32":
        return True
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        mutex_name = "Local\\Dayflow_TimeTracker_SingleInstance_Mutex_v1"
        handle = kernel32.CreateMutexW(None, False, mutex_name)
        last_err = ctypes.get_last_error()
        _SINGLE_INSTANCE_MUTEX = handle
        # ERROR_ALREADY_EXISTS == 183
        if last_err == 183:
            hwnd = user32.FindWindowW(None, "Dayflow")
            if hwnd:
                # 使用异步 ShowWindowAsync 避免在旧窗口繁忙时阻塞
                user32.ShowWindowAsync(hwnd, 9)
                user32.ShowWindowAsync(hwnd, 5)
                user32.SetForegroundWindow(hwnd)
            return False
    except Exception:
        pass
    return True


def run_smoke_test(db_path: Path, duration_sec: float = 2.0) -> int:
    """采集真实系统窗口 2 秒并输出看板 JSON 概览后退出，用于自动化冒烟验证。"""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    db = UsageDatabase(db_path)
    tracker = ForegroundTracker(db, poll_interval=0.5, flush_interval=5.0)
    bridge = DayflowBridge(db, tracker)

    tracker.start()
    try:
        time.sleep(max(0.5, duration_sec))
        dashboard = bridge.get_dashboard_data()
    finally:
        tracker.stop()
        db.close()

    # 精简 icon_base64 长度以便终端清晰展示 JSON 结构
    apps_preview = []
    for app in dashboard.get("apps", []):
        item = dict(app)
        icon = item.get("icon_base64", "")
        if len(icon) > 64:
            item["icon_base64"] = f"{icon[:48]}...({len(icon)} chars)"
        apps_preview.append(item)

    output = {
        "status": "ok",
        "date_str": dashboard["date_str"],
        "total_sec": dashboard["total_sec"],
        "active_app": dashboard["active_app"],
        "apps_count": len(apps_preview),
        "apps": apps_preview,
        "recent_dates": dashboard["recent_dates"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def run_desktop_app(db_path: Path, dev_mode: bool = False, dev_url: str = DEV_SERVER_URL) -> int:
    """启动 Dayflow 后台采样守护线程、系统托盘与 PyWebView 桌面窗口。"""
    set_windows_app_user_model_id()
    if not ensure_single_instance():
        return 0

    import webview

    icon_file = ensure_app_icon_file()

    db = UsageDatabase(db_path)
    tracker = ForegroundTracker(db, poll_interval=1.0, flush_interval=10.0)
    window_ref: dict[str, Any] = {"win": None}

    bridge = DayflowBridge(
        db=db,
        tracker=tracker,
        window_getter=lambda: window_ref.get("win"),
    )

    if dev_mode:
        target_url = dev_url
    else:
        if DIST_INDEX_PATH.is_file():
            target_url = DIST_INDEX_PATH.resolve().as_uri()
        else:
            target_url = dev_url

    win = webview.create_window(
        title="Dayflow",
        url=target_url,
        js_api=bridge,
        width=440,
        height=780,
        min_size=(360, 500),
        resizable=True,
        frameless=True,
        easy_drag=False,
        on_top=False,
        background_color="#18181B",
    )
    window_ref["win"] = win

    def _on_window_shown() -> None:
        # 仅通过纯 Win32 EnumWindows 解析缓存 HWND 并补充 WS_MINIMIZEBOX 样式位，支持任务栏点击『最小化 ↔ 恢复』
        try:
            hwnd = bridge._resolve_hwnd(win)
            if hwnd:
                bridge.enable_taskbar_minimize_toggle(hwnd)
        except Exception:
            pass

    try:
        win.events.shown += _on_window_shown
    except Exception:
        pass

    tray_ref: dict[str, Any] = {"tray": None}

    def quit_app() -> None:
        # 立即隐藏主窗口，随后落盘关闭数据库并直接终止进程（不等待 1s 轮询线程 sleep 周期，实现毫秒级瞬时关闭）
        try:
            bridge.stop_edge_autohide_monitor()
            bridge.hide_to_tray()
        except Exception:
            pass

        def _force_terminate() -> None:
            try:
                tracker._stop_event.set()
                tracker.flush()
            except Exception:
                pass
            try:
                db.close()
            except Exception:
                pass
            os._exit(0)

        threading.Thread(target=_force_terminate, daemon=True).start()

    bridge.set_on_quit(quit_app)

    tray = TrayController(
        on_show=bridge.toggle_window,
        on_toggle_top=bridge.toggle_always_on_top,
        is_on_top=lambda: bridge.always_on_top,
        on_quit=quit_app,
    )
    tray_ref["tray"] = tray

    tracker.start()
    tray.start()
    bridge.start_edge_autohide_monitor()
    try:
        webview.start(
            debug=dev_mode,
            icon=str(icon_file) if icon_file is not None else None,
        )
    finally:
        bridge.stop_edge_autohide_monitor()
        tray.stop()
        tracker.stop()
        db.close()

    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dayflow - Windows 桌面应用使用时间追踪工具")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="采集 2 秒真实系统窗口并打印 JSON 概览后退出",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="连接 Vite 前端开发服务器 (http://localhost:5173)",
    )
    parser.add_argument(
        "--dev-url",
        default=DEV_SERVER_URL,
        help="指定前端开发服务器地址",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="指定 SQLite 数据库文件路径",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    if args.smoke_test:
        return run_smoke_test(db_path=db_path, duration_sec=2.0)
    return run_desktop_app(db_path=db_path, dev_mode=args.dev, dev_url=args.dev_url)


if __name__ == "__main__":
    raise SystemExit(main())
