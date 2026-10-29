from datetime import datetime
from dayflow.database import UsageDatabase
from dayflow.tracker import ForegroundTracker
from dayflow.bridge import DayflowBridge
from dayflow.window_filter import ActiveWindowInfo
from dayflow.tray import create_tray_icon_image, TrayController


def test_bridge_dashboard_flushes_active_tracker_and_returns_full_payload(tmp_path):
    db = UsageDatabase(tmp_path / "bridge.db")
    tracker = ForegroundTracker(db)
    bridge = DayflowBridge(db, tracker)

    idea = ActiveWindowInfo(11, 2001, "C:/JetBrains/idea64.exe", "idea64.exe", "dayflow - IDEA", "SunAwtFrame")
    tracker.tick(datetime(2026, 10, 29, 10, 0, 0), window_info=idea)
    tracker.tick(datetime(2026, 10, 29, 10, 2, 0), window_info=idea)

    data = bridge.get_dashboard_data("2026-10-29")
    assert data["date_str"] == "2026-10-29"
    assert data["total_sec"] == 120
    assert len(data["hourly_buckets"]) == 24
    assert len(data["recent_dates"]) == 7
    assert data["apps"][0]["display_name"] == "IntelliJ IDEA"
    assert "category_meta" in data
    assert "active_app" in data
    assert data["active_app"]["display_name"] == "IntelliJ IDEA"
    assert data["always_on_top"] is False
    assert len(data["timeline"]) == 1
    assert data["timeline"][0]["display_name"] == "IntelliJ IDEA"
    assert data["timeline"][0]["duration_sec"] == 120

    app_id = data["apps"][0]["id"]
    detail = bridge.get_app_detail(app_id, "2026-10-29")
    assert len(detail["sessions"]) == 1
    assert detail["sessions"][0]["duration_sec"] == 120
    db.close()


def test_bridge_update_app_syncs_tracker_cache_and_ignored_apps(tmp_path):
    db = UsageDatabase(tmp_path / "bridge_update.db")
    tracker = ForegroundTracker(db)
    bridge = DayflowBridge(db, tracker)

    custom_app = ActiveWindowInfo(
        22, 3002, "C:/Apps/mytool.exe", "mytool.exe", "My Tool Window", "CustomWndClass"
    )
    tracker.tick(datetime(2026, 10, 29, 11, 0, 0), window_info=custom_app)
    tracker.tick(datetime(2026, 10, 29, 11, 1, 0), window_info=custom_app)

    dash = bridge.get_dashboard_data("2026-10-29")
    app_id = dash["apps"][0]["id"]

    updated = bridge.update_app(
        app_id,
        category="productivity",
        display_name="效率神器",
        is_ignored=False,
    )
    assert updated["category"] == "productivity"
    assert updated["display_name"] == "效率神器"
    assert updated["is_ignored"] is False

    # Verify tracker active session and cache immediately reflect updated metadata
    active = tracker.get_current_active()
    assert active is not None
    assert active["category"] == "productivity"
    assert active["display_name"] == "效率神器"

    # Ignore the app and verify it moves to get_ignored_apps() and disappears from dashboard/timeline
    bridge.update_app(app_id, is_ignored=True)
    ignored = bridge.get_ignored_apps()
    assert len(ignored) == 1
    assert ignored[0]["id"] == app_id
    assert ignored[0]["display_name"] == "效率神器"

    dash_after = bridge.get_dashboard_data("2026-10-29")
    assert dash_after["total_sec"] == 0
    assert dash_after["apps"] == []
    assert dash_after["timeline"] == []
    assert bridge.get_daily_timeline("2026-10-29") == []

    # Verify dict payload format in update_app also works
    restored = bridge.update_app(app_id, {"is_ignored": False, "display_name": "效率工具Pro"})
    assert restored["is_ignored"] is False
    assert restored["display_name"] == "效率工具Pro"
    assert bridge.get_ignored_apps() == []

    # Verify unflushed short tick (< flush_interval) is flushed by get_dashboard_data
    tracker.flush_interval = 60.0
    tracker.tick(datetime(2026, 10, 29, 11, 1, 0), window_info=custom_app)
    tracker.tick(datetime(2026, 10, 29, 11, 1, 5), window_info=custom_app)
    assert tracker.get_current_active()["unflushed_sec"] == 5

    dash_restored = bridge.get_dashboard_data("2026-10-29")
    assert dash_restored["total_sec"] == 65
    assert tracker.get_current_active()["unflushed_sec"] == 0
    db.close()


def test_bridge_window_controls_and_tray_icon(tmp_path):
    class DummyWindow:
        def __init__(self):
            self.on_top = False
            self.minimized = False
            self.hidden = False
            self.restored = False

        def minimize(self):
            self.minimized = True

        def hide(self):
            self.hidden = True

        def show(self):
            self.hidden = False

        def restore(self):
            self.restored = True
            self.minimized = False

    db = UsageDatabase(tmp_path / "bridge_win.db")
    tracker = ForegroundTracker(db)
    dummy_win = DummyWindow()
    bridge = DayflowBridge(db, tracker, window_getter=lambda: dummy_win)

    res1 = bridge.toggle_always_on_top()
    assert res1["always_on_top"] is True
    assert dummy_win.on_top is True

    res2 = bridge.toggle_always_on_top()
    assert res2["always_on_top"] is False
    assert dummy_win.on_top is False

    min_res = bridge.minimize_window()
    assert min_res["ok"] is True
    assert dummy_win.minimized is True

    hide_res = bridge.hide_to_tray()
    assert hide_res["ok"] is True
    assert dummy_win.hidden is True

    show_res = bridge.show_window()
    assert show_res["ok"] is True
    assert dummy_win.hidden is False

    img = create_tray_icon_image(64)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"

    tray = TrayController(
        on_show=bridge.show_window,
        on_toggle_top=bridge.toggle_always_on_top,
        is_on_top=lambda: bridge.always_on_top,
        on_quit=lambda: None,
    )
    assert tray is not None
    db.close()


def test_toggle_always_on_top_uses_async_win32_without_deadlocking_winforms_setter(tmp_path):
    """回归测试：
    1. 当存在原生 HWND 或 pywebview.Window(带 gui 属性) 时，绝不能调用 win.on_top setter 导致 WinForms TopMost 跨线程死锁；
    2. 全局 ctypes.windll.user32.SetWindowPos.argtypes 必须保持为 None，确保 pywebview 内置 window.move(x, y) 传 None 时正常拖动窗口。
    """
    import ctypes

    assert ctypes.windll.user32.SetWindowPos.argtypes is None

    class DeadlockingPyWebViewWindow:
        gui = object()

        @property
        def on_top(self):
            return getattr(self, "_Window__on_top", False)

        @on_top.setter
        def on_top(self, _value):
            raise RuntimeError("Deadlock! Should never call win.on_top setter from JS bridge thread")

    db = UsageDatabase(tmp_path / "bridge_topmost.db")
    tracker = ForegroundTracker(db)
    win = DeadlockingPyWebViewWindow()
    bridge = DayflowBridge(db, tracker, window_getter=lambda: win)
    bridge.set_hwnd(123456)

    res_on = bridge.toggle_always_on_top(True)
    assert res_on == {"ok": True, "always_on_top": True}
    assert bridge.always_on_top is True

    res_off = bridge.toggle_always_on_top(False)
    assert res_off == {"ok": True, "always_on_top": False}
    assert bridge.always_on_top is False
    db.close()


def test_bridge_period_summaries_and_quit_app(tmp_path):
    db = UsageDatabase(tmp_path / "bridge_period_quit.db")
    tracker = ForegroundTracker(db)
    quit_called = []
    bridge = DayflowBridge(db, tracker, on_quit=lambda: quit_called.append(True))

    idea = ActiveWindowInfo(
        11, 2001, "C:/JetBrains/idea64.exe", "idea64.exe", "dayflow - IDEA", "SunAwtFrame"
    )
    tracker.tick(datetime(2026, 10, 28, 10, 0, 0), window_info=idea)
    tracker.tick(datetime(2026, 10, 28, 10, 0, 10), window_info=None)
    tracker.tick(datetime(2026, 10, 29, 11, 0, 0), window_info=idea)
    tracker.tick(datetime(2026, 10, 29, 11, 0, 5), window_info=idea)

    week_data = bridge.get_dashboard_data("2026-10-29", period="week")
    assert week_data["period"] == "week"
    assert week_data["total_sec"] == 15
    assert len(week_data["chart_buckets"]) == 7
    assert len(week_data["timeline"]) == 2

    month_data = bridge.get_dashboard_data("2026-10-29", period="month")
    assert month_data["period"] == "month"
    assert month_data["total_sec"] == 15
    assert len(month_data["chart_buckets"]) == 31

    res_quit = bridge.quit_app()
    assert res_quit == {"ok": True, "quitting": True}
    assert quit_called == [True]
    db.close()


def test_bridge_preferences_and_version(tmp_path):
    db = UsageDatabase(tmp_path / "bridge_prefs.db")
    tracker = ForegroundTracker(db)
    bridge = DayflowBridge(db, tracker)

    prefs = bridge.get_preferences()
    assert prefs["language"] == "system"
    assert prefs["theme"] == "dark"
    assert prefs["font_scale"] == 1.0
    assert prefs["version"] == "1.0.0"

    updated = bridge.update_preferences(
        {
            "language": "en",
            "theme": "light",
            "font_scale": 1.15,
        }
    )
    assert updated["language"] == "en"
    assert updated["theme"] == "light"
    assert updated["font_scale"] == 1.15
    assert updated["version"] == "1.0.0"
    db.close()
