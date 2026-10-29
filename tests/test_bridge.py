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
    assert prefs["version"] == "1.0.1"
    assert prefs["idle_detection_enabled"] is True
    assert prefs["health_remind_enabled"] is True
    assert prefs["rest_remind_interval_sec"] == 1800
    assert prefs["health_remind_sound"] is True
    assert prefs["health_remind_dnd_game"] is True

    updated = bridge.update_preferences(
        {
            "language": "en",
            "theme": "light",
            "font_scale": 1.15,
            "rest_remind_interval_sec": 2700,
            "health_remind_sound": False,
        }
    )
    assert updated["language"] == "en"
    assert updated["theme"] == "light"
    assert updated["font_scale"] == 1.15
    assert updated["version"] == "1.0.1"
    assert updated["rest_remind_interval_sec"] == 2700
    assert updated["health_remind_sound"] is False

    # 模拟重启应用：重新实例化 tracker 与 bridge，验证读取保持修改后的持久化值
    tracker2 = ForegroundTracker(db)
    bridge2 = DayflowBridge(db, tracker2)
    prefs_restarted = bridge2.get_preferences()
    assert prefs_restarted["rest_remind_interval_sec"] == 2700
    assert prefs_restarted["health_remind_sound"] is False
    assert tracker2.rest_remind_interval_sec == 2700.0
    assert tracker2.health_remind_sound is False

    # 验证 start_window_resize 对非法方向与无句柄窗口的安全返回
    res_invalid = bridge.start_window_resize("invalid")
    assert res_invalid["ok"] is False
    res_no_hwnd = bridge.start_window_resize("se")
    assert res_no_hwnd["ok"] is False
    db.close()


def test_taskbar_minimize_toggle_and_qq_top_edge_autohide(tmp_path, monkeypatch):
    import dayflow.bridge as bridge_mod

    class FakeUser32:
        def __init__(self):
            self.style = 0x16010000
            self.rect = [200, 2, 640, 782]  # left, top, right, bottom (440x780)
            self.cursor = [300, 100]
            self.lbutton = 0
            self.iconic = False
            self.visible = True

        def GetWindowLongW(self, _hwnd, _idx):
            return self.style

        def SetWindowLongW(self, _hwnd, _idx, new_style):
            self.style = int(new_style)
            return self.style

        def IsIconic(self, _hwnd):
            return self.iconic

        def IsWindowVisible(self, _hwnd):
            return self.visible

        def GetAsyncKeyState(self, _vk):
            return self.lbutton

        def GetWindowRect(self, _hwnd, rect_ptr):
            rect_ptr._obj.left = self.rect[0]
            rect_ptr._obj.top = self.rect[1]
            rect_ptr._obj.right = self.rect[2]
            rect_ptr._obj.bottom = self.rect[3]
            return True

        def GetCursorPos(self, pt_ptr):
            pt_ptr._obj.x = self.cursor[0]
            pt_ptr._obj.y = self.cursor[1]
            return True

        def SetWindowPos(self, _hwnd, _insert_after, x, y, _w, _h, flags):
            if not (flags & bridge_mod.SWP_NOMOVE):
                h = self.rect[3] - self.rect[1]
                w = self.rect[2] - self.rect[0]
                self.rect[0] = int(x)
                self.rect[1] = int(y)
                self.rect[2] = int(x) + w
                self.rect[3] = int(y) + h
            return True

        def ShowWindowAsync(self, _hwnd, cmd):
            if cmd == bridge_mod.SW_MINIMIZE:
                self.iconic = True
            elif cmd in (bridge_mod.SW_SHOW, bridge_mod.SW_RESTORE):
                self.iconic = False
                self.visible = True
            return True

        def SetForegroundWindow(self, _hwnd):
            return True

    fake_u32 = FakeUser32()
    monkeypatch.setattr(bridge_mod, "_user32", fake_u32)

    db = UsageDatabase(tmp_path / "bridge_autohide.db")
    tracker = ForegroundTracker(db)
    dummy_win = type("W", (), {"hwnd": 9999})()
    bridge = DayflowBridge(db, tracker, window_getter=lambda: dummy_win)
    bridge.set_hwnd(9999)

    # 1. 验证任务栏最小化/恢复切换样式位注入及 toggle_window 双向切换
    bridge.enable_taskbar_minimize_toggle(9999)
    assert (fake_u32.style & bridge_mod.WS_MINIMIZEBOX) != 0
    assert (fake_u32.style & bridge_mod.WS_SYSMENU) != 0

    bridge.toggle_window()
    assert fake_u32.iconic is True
    bridge.toggle_window()
    assert fake_u32.iconic is False

    # 2. 窗口拖到屏幕顶部 (top=2) 松手 -> 自动对齐吸附 y=0 并进入 _docked_top 模式
    outside_ts = bridge._edge_autohide_step(9999, None)
    assert bridge._docked_top is True
    assert bridge._dock_collapsed is False
    assert fake_u32.rect[1] == 0

    # 3. 鼠标移出窗口范围 (cursor=[900, 500]) 超过延迟后 -> 自动向上收起隐藏
    fake_u32.cursor = [900, 500]
    outside_ts = bridge._edge_autohide_step(9999, None)
    assert outside_ts is not None
    bridge._edge_autohide_step(9999, outside_ts - 1.0)
    assert bridge._dock_collapsed is True
    assert fake_u32.rect[1] == -(780 - bridge_mod.DOCK_PEEK_VISIBLE_PX)

    # 4. 鼠标再次移动到屏幕上方窗口位置 (cursor=[350, 1]) -> 立即向下滑出恢复到 y=0
    fake_u32.cursor = [350, 1]
    bridge._edge_autohide_step(9999, None)
    assert bridge._dock_collapsed is False
    assert fake_u32.rect[1] == 0

    # 5. 将窗口向下拖离屏幕顶部 (top=80) -> 自动解除顶部贴边隐藏
    fake_u32.rect = [200, 80, 640, 860]
    bridge._edge_autohide_step(9999, None)
    assert bridge._docked_top is False
    assert bridge._dock_collapsed is False
    db.close()


def test_autostart_startup_shortcut_and_preferences(tmp_path, monkeypatch):
    """测试 Windows 启动文件夹快捷方式与 preferences 设置联动的开机自启逻辑。"""
    import dayflow.bridge as bridge_mod

    fake_startup = tmp_path / "Startup"
    fake_startup.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(bridge_mod, "_get_startup_folder", lambda: fake_startup)

    db = UsageDatabase(tmp_path / "test_autostart.db")
    tracker = ForegroundTracker(db)
    bridge = DayflowBridge(db, tracker)

    # 初始状态：未配置自启动
    assert bridge_mod._read_registry_autostart() is False

    # 1. 启用自启动 -> 触发快捷方式/引导文件创建
    ok = bridge_mod._write_registry_autostart(True)
    assert ok is True
    assert bridge_mod._read_registry_autostart() is True
    # 验证 fake_startup 目录下存在 Dayflow.lnk 或 Dayflow.bat
    created_files = [f.name for f in fake_startup.iterdir()]
    assert any(name in ("Dayflow.lnk", "Dayflow.bat") for name in created_files)

    # 2. 检查 bridge.get_preferences 状态同步
    prefs = bridge.get_preferences()
    assert prefs["auto_start"] is True

    # 3. 通过 bridge.update_preferences 关闭自启动
    updated = bridge.update_preferences({"auto_start": False})
    assert updated["auto_start"] is False
    assert bridge_mod._read_registry_autostart() is False
    assert not (fake_startup / "Dayflow.lnk").exists()
    assert not (fake_startup / "Dayflow.bat").exists()

    # 4. 再次通过 bridge.update_preferences 开启自启动
    updated2 = bridge.update_preferences({"auto_start": True})
    assert updated2["auto_start"] is True
    assert bridge_mod._read_registry_autostart() is True
    assert any(f.name in ("Dayflow.lnk", "Dayflow.bat") for f in fake_startup.iterdir())

    db.close()


def test_export_usage_report_csv(tmp_path):
    """测试第 8 点：CSV 报表导出，验证 1、2 级分类清晰展现与 UTF-8 BOM。"""
    db = UsageDatabase(tmp_path / "test_export.db")
    tracker = ForegroundTracker(db)
    bridge = DayflowBridge(db, tracker)

    # 模拟几个带二级分类的会话
    bili_win = ActiveWindowInfo(
        100, 5001, "C:/Program Files/Chrome/chrome.exe", "chrome.exe", "【4K】原神全新演示 - 哔哩哔哩_bilibili", "Chrome_WidgetWin_1"
    )
    tracker.tick(datetime(2026, 10, 29, 14, 0, 0), window_info=bili_win)
    tracker.tick(datetime(2026, 10, 29, 14, 30, 0), window_info=bili_win)

    code_win = ActiveWindowInfo(
        101, 5002, "C:/Apps/Code.exe", "Code.exe", "main.py - dayflow - Visual Studio Code", "Chrome_WidgetWin_1"
    )
    tracker.tick(datetime(2026, 10, 29, 15, 0, 0), window_info=code_win)
    tracker.tick(datetime(2026, 10, 29, 15, 45, 0), window_info=code_win)

    res = bridge.export_usage_report("2026-10-29", "day")
    assert res["success"] is True
    assert res["row_count"] >= 2
    assert "csv_text" in res
    assert res["csv_text"].startswith("\ufeff")
    assert "creative" in res["csv_text"]
    assert "entertainment" in res["csv_text"]
    assert "chrome.exe" in res["csv_text"]
    assert "Code.exe" in res["csv_text"]
    assert "bilibili" in res["csv_text"].lower()

    db.close()


def test_check_and_heal_autostart_path(tmp_path, monkeypatch):
    """测试第 10 点：自启动路径自愈机制。"""
    import dayflow.bridge as bridge_mod

    fake_startup = tmp_path / "Startup"
    fake_startup.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(bridge_mod, "_get_startup_folder", lambda: fake_startup)

    db = UsageDatabase(tmp_path / "test_heal.db")
    tracker = ForegroundTracker(db)
    bridge = DayflowBridge(db, tracker)

    # 预设一个旧的错误路径快捷方式批处理
    old_bat = fake_startup / "Dayflow.bat"
    old_bat.write_text('@start "" "D:\\OldPath\\Dayflow.exe"\n', encoding="utf-8")

    # 手动触发自愈方法
    healed = bridge.check_and_heal_autostart_path()
    assert healed is True
    # 验证旧路径批处理已被安全清理或自愈为真实路径，且启动文件夹中存在自愈后的启动项
    if old_bat.exists():
        assert "OldPath" not in old_bat.read_text(encoding="utf-8")
    created = [f.name for f in fake_startup.iterdir()]
    assert any(name in ("Dayflow.lnk", "Dayflow.bat") for name in created)
    db.close()


def test_update_preferences_hotkey(tmp_path):
    """测试第 9 点：快捷键配置与热重载。"""
    from dayflow.hotkey import GlobalHotkeyManager

    db = UsageDatabase(tmp_path / "test_hotkey.db")
    tracker = ForegroundTracker(db)
    bridge = DayflowBridge(db, tracker)

    hotkey_mgr = GlobalHotkeyManager(on_trigger=lambda: None)
    bridge.hotkey_mgr = hotkey_mgr

    updated = bridge.update_preferences({"global_hotkey_enabled": True, "global_hotkey": "Ctrl+Shift+D"})
    assert updated["global_hotkey_enabled"] is True
    assert updated["global_hotkey"] == "Ctrl+Shift+D"

    # 查库验证持久化
    prefs = db.get_preferences()
    assert prefs["global_hotkey_enabled"] is True
    assert prefs["global_hotkey"] == "Ctrl+Shift+D"

    hotkey_mgr.stop()
    db.close()


def test_quit_app_confirmation_and_cancellation(tmp_path, monkeypatch):
    """测试右键或关闭前二次确认弹窗机制：用户取消则不关闭，确认后才退出。"""
    import dayflow.tray as tray_mod

    db = UsageDatabase(tmp_path / "test_quit_confirm.db")
    tracker = ForegroundTracker(db)
    quit_calls = []
    bridge = DayflowBridge(db, tracker, on_quit=lambda: quit_calls.append(True))

    # 1. 模拟用户在确认弹窗中点击了“否 / 取消”
    monkeypatch.setattr(tray_mod, "ask_quit_confirmation", lambda *args, **kwargs: False)
    res_cancel = bridge.quit_app(confirm=True)
    assert res_cancel == {"ok": False, "cancelled": True}
    assert len(quit_calls) == 0

    # 2. 模拟用户在确认弹窗中点击了“是 / 确定”
    monkeypatch.setattr(tray_mod, "ask_quit_confirmation", lambda *args, **kwargs: True)
    res_ok = bridge.quit_app(confirm=True)
    assert res_ok == {"ok": True, "quitting": True}
    assert len(quit_calls) == 1

    # 3. 验证托盘右键退出逻辑
    tray_quits = []
    tray = TrayController(
        on_quit=lambda: tray_quits.append(True),
        confirm_quit=lambda: False,
    )
    tray._handle_quit()
    assert len(tray_quits) == 0  # 取消时不退出

    tray_ok = TrayController(
        on_quit=lambda: tray_quits.append(True),
        confirm_quit=lambda: True,
    )
    tray_ok._handle_quit()
    assert len(tray_quits) == 1  # 确认后退出

    db.close()

