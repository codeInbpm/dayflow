from datetime import datetime
from dayflow.database import UsageDatabase


def test_record_span_splits_across_hour_and_midnight(tmp_path):
    db = UsageDatabase(tmp_path / "test.db")
    app_id = db.upsert_app("C:/Program Files/WeChat/WeChat.exe", "WeChat.exe", "微信", "social", "data:image/png;base64,AAA")

    # 11:50:00 -> 12:10:00 (跨越 12:00 整点)
    db.record_usage_span(
        app_id,
        datetime(2026, 10, 29, 11, 50, 0),
        datetime(2026, 10, 29, 12, 10, 0),
        "微信 - 聊天",
    )
    summary = db.get_daily_summary("2026-10-29")
    assert summary["total_sec"] == 1200
    assert summary["hourly_buckets"][11]["total_sec"] == 600
    assert summary["hourly_buckets"][11]["categories"]["social"] == 600
    assert summary["hourly_buckets"][12]["total_sec"] == 600
    assert summary["hourly_buckets"][12]["categories"]["social"] == 600

    # 23:55:00 -> 次日 00:05:00 (跨越午夜零点)
    db.record_usage_span(
        app_id,
        datetime(2026, 10, 29, 23, 55, 0),
        datetime(2026, 10, 30, 0, 5, 0),
        "微信 - 朋友圈",
    )
    day1 = db.get_daily_summary("2026-10-29")
    day2 = db.get_daily_summary("2026-10-30")
    assert day1["hourly_buckets"][23]["total_sec"] == 300
    assert day2["hourly_buckets"][0]["total_sec"] == 300


def test_update_category_and_ignore_recalculates_summary(tmp_path):
    db = UsageDatabase(tmp_path / "test.db")
    wechat_id = db.upsert_app("C:/WeChat.exe", "WeChat.exe", "微信", "other", "")
    code_id = db.upsert_app("C:/Code.exe", "Code.exe", "VS Code", "creative", "")

    db.record_usage_span(wechat_id, datetime(2026, 10, 29, 9, 0, 0), datetime(2026, 10, 29, 9, 30, 0), "微信")
    db.record_usage_span(code_id, datetime(2026, 10, 29, 9, 30, 0), datetime(2026, 10, 29, 10, 0, 0), "dayflow - VS Code")

    # 修改分类 other -> social
    db.update_app_settings(wechat_id, category="social")
    summary = db.get_daily_summary("2026-10-29")
    assert summary["hourly_buckets"][9]["categories"]["social"] == 1800
    assert summary["hourly_buckets"][9]["categories"].get("other", 0) == 0

    # 屏蔽微信后，总时长与柱状图不再包含微信
    db.update_app_settings(wechat_id, is_ignored=True)
    summary_after_ignore = db.get_daily_summary("2026-10-29")
    assert summary_after_ignore["total_sec"] == 1800
    assert len(summary_after_ignore["apps"]) == 1
    assert summary_after_ignore["apps"][0]["display_name"] == "VS Code"

    ignored = db.get_ignored_apps()
    assert len(ignored) == 1
    assert ignored[0]["id"] == wechat_id
    assert ignored[0]["is_ignored"] is True


def test_session_merge_and_app_daily_sessions_and_recent_dates(tmp_path):
    db = UsageDatabase(tmp_path / "test.db")
    app_id = db.upsert_app("C:/Chrome.exe", "chrome.exe", "Chrome", "productivity", "")
    # 二次 upsert 仅在原 icon_base64 为空时补全图标，且不覆盖已有自定义设置
    db.update_app_settings(app_id, display_name="Google Chrome", category="creative")
    same_id = db.upsert_app("C:/Chrome.exe", "chrome.exe", "Chrome", "productivity", "data:image/png;base64,ICON")
    assert same_id == app_id

    # 相邻间隔 <= 5s 自动合并
    db.record_usage_span(app_id, datetime(2026, 10, 28, 10, 0, 0), datetime(2026, 10, 28, 10, 1, 0), "Tab 1")
    db.record_usage_span(app_id, datetime(2026, 10, 28, 10, 1, 3), datetime(2026, 10, 28, 10, 2, 3), "Tab 2")
    # 间隔 > 5s 新开一条会话
    db.record_usage_span(app_id, datetime(2026, 10, 28, 10, 5, 0), datetime(2026, 10, 28, 10, 6, 0), "Tab 3")

    detail = db.get_app_daily_sessions(app_id, "2026-10-28")
    assert detail["app"]["display_name"] == "Google Chrome"
    assert detail["app"]["category"] == "creative"
    assert detail["app"]["icon_base64"] == "data:image/png;base64,ICON"
    assert len(detail["sessions"]) == 2
    assert detail["sessions"][0]["duration_sec"] == 120
    assert detail["sessions"][0]["last_window_title"] == "Tab 2"
    assert detail["hourly_sec"][10] == 180

    # 验证 yesterday_total_sec 与 get_recent_dates
    db.record_usage_span(app_id, datetime(2026, 10, 29, 14, 0, 0), datetime(2026, 10, 29, 14, 1, 0), "Tab 4")
    summary_29 = db.get_daily_summary("2026-10-29")
    assert summary_29["yesterday_total_sec"] == 180
    recent = db.get_recent_dates(days=7, ref_date="2026-10-29")
    assert len(recent) == 7
    assert recent[-1]["date_str"] == "2026-10-29"
    assert recent[-1]["total_sec"] == 60
    assert recent[-2]["date_str"] == "2026-10-28"
    assert recent[-2]["total_sec"] == 180
