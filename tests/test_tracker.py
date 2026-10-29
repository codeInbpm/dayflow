from datetime import datetime
from dayflow.database import UsageDatabase
from dayflow.tracker import ForegroundTracker
from dayflow.window_filter import ActiveWindowInfo


def test_tracker_merges_ticks_and_flushes_on_switch(tmp_path):
    db = UsageDatabase(tmp_path / "tracker.db")
    tracker = ForegroundTracker(db, flush_interval=60.0)

    chrome = ActiveWindowInfo(
        10,
        1001,
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "chrome.exe",
        "GitHub - Chrome",
        "Chrome_WidgetWin_1",
    )
    wechat = ActiveWindowInfo(
        20,
        1002,
        "C:/Program Files/Tencent/WeChat/WeChat.exe",
        "WeChat.exe",
        "微信",
        "WeChatMainWndForPC",
    )

    tracker.tick(datetime(2026, 10, 29, 14, 0, 0), window_info=chrome)
    tracker.tick(datetime(2026, 10, 29, 14, 0, 5), window_info=chrome)
    tracker.tick(datetime(2026, 10, 29, 14, 0, 10), window_info=wechat)
    tracker.tick(datetime(2026, 10, 29, 14, 0, 25), window_info=None)

    summary = db.get_daily_summary("2026-10-29")
    assert summary["total_sec"] == 25
    by_name = {a["exe_name"]: a["total_sec"] for a in summary["apps"]}
    assert by_name["chrome.exe"] == 10
    assert by_name["WeChat.exe"] == 15


def test_tracker_periodic_flush_and_current_active_and_sleep_gap(tmp_path):
    db = UsageDatabase(tmp_path / "tracker_extra.db")
    tracker = ForegroundTracker(db, poll_interval=1.0, flush_interval=10.0)

    code = ActiveWindowInfo(
        30,
        2001,
        "C:/Program Files/Microsoft VS Code/Code.exe",
        "Code.exe",
        "tracker.py - dayflow - Visual Studio Code",
        "Chrome_WidgetWin_1",
    )

    # 10:00:00 -> 10:00:10 达到 flush_interval=10.0 自动刷盘
    tracker.tick(datetime(2026, 10, 29, 10, 0, 0), window_info=code)
    active = tracker.get_current_active()
    assert active is not None
    assert active["exe_name"] == "Code.exe"

    tracker.tick(datetime(2026, 10, 29, 10, 0, 10), window_info=code)
    summary_mid = db.get_daily_summary("2026-10-29")
    assert summary_mid["total_sec"] == 10

    # 模拟电脑休眠恢复：间隔 > 30s (10:00:10 -> 10:10:10)，仅按 poll_interval (1s) 计入
    tracker.tick(datetime(2026, 10, 29, 10, 10, 10), window_info=code)
    tracker.flush(datetime(2026, 10, 29, 10, 10, 12))

    summary_after = db.get_daily_summary("2026-10-29")
    assert summary_after["total_sec"] == 13


def test_tracker_start_and_stop_lifecycle(tmp_path):
    db = UsageDatabase(tmp_path / "tracker_thread.db")
    tracker = ForegroundTracker(db, poll_interval=0.05, flush_interval=1.0)
    tracker.start()
    tracker.stop()
    assert tracker.get_current_active() is None or isinstance(tracker.get_current_active(), dict)
