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


def test_tracker_idle_detection_and_browser_sub_category(tmp_path):
    db = UsageDatabase(tmp_path / "tracker_idle.db")
    mock_idle_sec = [0.0]
    tracker = ForegroundTracker(
        db,
        poll_interval=1.0,
        flush_interval=60.0,
        idle_threshold_sec=180.0,
        idle_detector=lambda: mock_idle_sec[0],
        rest_remind_interval_sec=300.0,
    )

    chrome = ActiveWindowInfo(
        10,
        1001,
        "C:/Chrome/chrome.exe",
        "chrome.exe",
        "哔哩哔哩 (゜-゜)つロ 干杯~-bilibili - Google Chrome",
        "Chrome_WidgetWin_1",
    )

    # 1. 活跃状态 (idle = 0s)
    tracker.tick(datetime(2026, 10, 29, 14, 0, 0), window_info=chrome)
    tracker.tick(datetime(2026, 10, 29, 14, 0, 10), window_info=chrome)
    assert tracker.is_idle is False
    assert tracker.continuous_active_sec == 11.0

    # 2. 用户离开电脑，无键盘鼠标操作 200 秒 (超过 180s 阈值)
    mock_idle_sec[0] = 200.0
    tracker.tick(datetime(2026, 10, 29, 14, 3, 30), window_info=chrome)
    assert tracker.is_idle is True
    # 离开期间的数据已被封口，不计入挂机无操作时间
    active_snapshot = tracker.get_current_active()
    assert active_snapshot["is_idle"] is True
    assert active_snapshot["display_name"] == "离开电脑 (空闲)"

    # 3. 用户重新操作 (idle = 1s)，解除空闲状态
    mock_idle_sec[0] = 1.0
    tracker.tick(datetime(2026, 10, 29, 14, 10, 0), window_info=chrome)
    assert tracker.is_idle is False
    tracker.flush(datetime(2026, 10, 29, 14, 10, 5))

    # 4. 验证数据库中，B站网页被精准分类为 entertainment (影音娱乐) 而不是单纯 productivity
    summary = db.get_daily_summary("2026-10-29")
    cat_map = {c["category"]: c["total_sec"] for c in summary["category_totals"]}
    assert cat_map.get("entertainment", 0) > 0


def test_tracker_health_focus_guard_reminder(tmp_path):
    db = UsageDatabase(tmp_path / "tracker_health.db")
    tracker = ForegroundTracker(
        db,
        poll_interval=1.0,
        idle_threshold_sec=300.0,
        idle_detector=lambda: 0.0,
        rest_remind_interval_sec=10.0,  # 设为 10 秒测试疲劳提醒
    )

    code = ActiveWindowInfo(
        20, 2001, "C:/VSCode/Code.exe", "Code.exe", "main.py", "Chrome_WidgetWin_1"
    )

    tracker.tick(datetime(2026, 10, 29, 9, 0, 0), window_info=code)
    assert tracker.check_and_consume_health_remind() is False

    # 连续专注使用 12 秒，触发健康提醒
    tracker.tick(datetime(2026, 10, 29, 9, 0, 12), window_info=code)
    assert tracker.check_and_consume_health_remind() is True
    # 再次读取时已经被 consume，返回 False 避免频繁打扰
    assert tracker.check_and_consume_health_remind() is False


def test_tracker_game_dnd_and_system_notification_callback(tmp_path):
    db = UsageDatabase(tmp_path / "tracker_dnd.db")
    mock_fullscreen = [True]  # 模拟用户当前处于全屏游戏或演示中
    remind_callbacks = []

    tracker = ForegroundTracker(
        db,
        poll_interval=1.0,
        idle_threshold_sec=300.0,
        idle_detector=lambda: 0.0,
        rest_remind_interval_sec=10.0,
        health_remind_dnd_game=True,
        fullscreen_checker=lambda: mock_fullscreen[0],
        on_health_remind=lambda sec: remind_callbacks.append(sec),
    )

    game = ActiveWindowInfo(
        100, 5001, "C:/Games/LOL/LeagueClient.exe", "LeagueClient.exe", "英雄联盟", "RiotWindowClass"
    )

    tracker.tick(datetime(2026, 10, 29, 20, 0, 0), window_info=game)
    # 连续专注超过 15 秒，但由于处于全屏游戏中 (mock_fullscreen == True)，免打扰生效，不弹窗！
    tracker.tick(datetime(2026, 10, 29, 20, 0, 15), window_info=game)
    assert len(remind_callbacks) == 0
    assert tracker._health_remind_pending is False

    # 用户打完这把游戏，切出全屏游戏 (mock_fullscreen == False)
    mock_fullscreen[0] = False
    tracker.tick(datetime(2026, 10, 29, 20, 0, 16), window_info=game)
    # 退出全屏后立刻温柔推送！
    assert len(remind_callbacks) == 1
    assert remind_callbacks[0] >= 16.0
    assert tracker._health_remind_pending is True


def test_tracker_registers_pwa_as_standalone_app(tmp_path):
    db = UsageDatabase(tmp_path / "tracker_pwa.db")
    tracker = ForegroundTracker(db, flush_interval=60.0)

    # 1. 模拟打开桌面 Facebook 本地应用（Edge 托管，标题 Facebook，无 Edge 后缀）
    fb_pwa = ActiveWindowInfo(
        101,
        5001,
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        "msedge.exe",
        "Facebook - 登录或注册",
        "Chrome_WidgetWin_1",
    )
    # 2. 模拟打开任务栏 TikTok 本地应用（Chrome 托管，标题 TikTok）
    tiktok_pwa = ActiveWindowInfo(
        102,
        5002,
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "chrome.exe",
        "TikTok - Make Your Day",
        "Chrome_WidgetWin_1",
    )

    tracker.tick(datetime(2026, 10, 30, 9, 0, 0), window_info=fb_pwa)
    tracker.tick(datetime(2026, 10, 30, 9, 0, 30), window_info=fb_pwa)
    tracker.tick(datetime(2026, 10, 30, 9, 0, 30), window_info=tiktok_pwa)
    tracker.tick(datetime(2026, 10, 30, 9, 1, 0), window_info=tiktok_pwa)
    tracker.flush(datetime(2026, 10, 30, 9, 1, 0))

    summary = db.get_daily_summary("2026-10-30")
    apps_by_name = {a["display_name"]: a for a in summary["apps"]}

    # 验证作为独立本地应用被记录，而不是被吃进 Edge 或 Chrome！
    assert "Facebook" in apps_by_name
    assert apps_by_name["Facebook"]["category"] == "social"
    assert apps_by_name["Facebook"]["total_sec"] == 30

    assert "TikTok" in apps_by_name
    assert apps_by_name["TikTok"]["category"] == "entertainment"
    assert apps_by_name["TikTok"]["total_sec"] == 30
