from __future__ import annotations

import argparse
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
from dayflow.tray import TrayController

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "dayflow.db"
DIST_INDEX_PATH = BASE_DIR / "frontend" / "dist" / "index.html"
DEV_SERVER_URL = "http://localhost:5173"


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
    import webview

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
        min_size=(380, 620),
        frameless=True,
        easy_drag=False,
        on_top=False,
        background_color="#18181B",
    )
    window_ref["win"] = win

    def _on_window_shown() -> None:
        try:
            native = getattr(win, "native", None)
            if native is not None and hasattr(native, "Handle"):
                handle = native.Handle
                hwnd = int(handle.ToInt32()) if hasattr(handle, "ToInt32") else int(handle)
                bridge.set_hwnd(hwnd)
        except Exception:
            pass

    try:
        win.events.shown += _on_window_shown
    except Exception:
        pass

    tray_ref: dict[str, Any] = {"tray": None}

    def quit_app() -> None:
        def _force_terminate() -> None:
            time.sleep(0.04)
            try:
                t = tray_ref.get("tray")
                if t is not None:
                    t.stop()
            except Exception:
                pass
            try:
                tracker.stop()
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
        on_show=bridge.show_window,
        on_toggle_top=bridge.toggle_always_on_top,
        is_on_top=lambda: bridge.always_on_top,
        on_quit=quit_app,
    )
    tray_ref["tray"] = tray

    tracker.start()
    tray.start()
    try:
        webview.start(debug=dev_mode)
    finally:
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
