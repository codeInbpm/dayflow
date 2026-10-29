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
    recent = db.get_recent_dates(days=7, ref_date="2026-10-29", today_str="2026-10-29")
    assert len(recent) == 7
    assert recent[-1]["date_str"] == "2026-10-29"
    assert recent[-1]["label"] == "今日"
    assert recent[-1]["total_sec"] == 60
    assert recent[-2]["date_str"] == "2026-10-28"
    assert recent[-2]["label"] == "昨日"
    assert recent[-2]["total_sec"] == 180

    # 回归验证：当用户切换到昨日 (2026-10-28) 时，recent_dates 依然包含今日 (2026-10-29)，可以切回今日
    recent_when_viewing_yesterday = db.get_recent_dates(
        days=7, ref_date="2026-10-28", today_str="2026-10-29"
    )
    assert recent_when_viewing_yesterday[-1]["date_str"] == "2026-10-29"
    assert recent_when_viewing_yesterday[-1]["label"] == "今日"
    assert recent_when_viewing_yesterday[-2]["date_str"] == "2026-10-28"
    assert recent_when_viewing_yesterday[-2]["label"] == "昨日"


def test_get_period_summary_day_week_month_and_navigation(tmp_path):
    db = UsageDatabase(tmp_path / "period.db")
    app_id = db.upsert_app("C:/Code.exe", "Code.exe", "VS Code", "creative", "")

    # 2026-10-27 (周二): 1800s, 2026-10-28 (周三): 3600s, 2026-10-29 (周四, 今日): 600s
    db.record_usage_span(app_id, datetime(2026, 10, 27, 9, 0, 0), datetime(2026, 10, 27, 9, 30, 0), "Day 1")
    db.record_usage_span(app_id, datetime(2026, 10, 28, 10, 0, 0), datetime(2026, 10, 28, 11, 0, 0), "Day 2")
    db.record_usage_span(app_id, datetime(2026, 10, 29, 14, 0, 0), datetime(2026, 10, 29, 14, 10, 0), "Day 3")

    # 1. 每日汇总：查看昨日 (2026-10-28) 时，可以切去前一天 (2026-10-27) 也可以切回后一天 (2026-10-29)
    day_summary = db.get_period_summary("2026-10-28", period="day", today_str="2026-10-29")
    assert day_summary["period"] == "day"
    assert day_summary["total_sec"] == 3600
    assert day_summary["prev_date_str"] == "2026-10-27"
    assert day_summary["next_date_str"] == "2026-10-29"
    assert day_summary["can_go_next"] is True
    assert len(day_summary["chart_buckets"]) == 24

    # 2. 每周汇总：2026-10-26 (周一) ~ 2026-11-01 (周日)
    week_summary = db.get_period_summary("2026-10-29", period="week", today_str="2026-10-29")
    assert week_summary["period"] == "week"
    assert week_summary["start_date_str"] == "2026-10-26"
    assert week_summary["end_date_str"] == "2026-11-01"
    assert week_summary["total_sec"] == 1800 + 3600 + 600
    assert week_summary["active_days_count"] == 3
    assert len(week_summary["chart_buckets"]) == 7
    assert week_summary["chart_buckets"][1]["date_str"] == "2026-10-27"
    assert week_summary["chart_buckets"][1]["total_sec"] == 1800
    assert week_summary["can_go_next"] is False
    assert week_summary["prev_date_str"] == "2026-10-19"

    # 切换到上一周后，can_go_next 应为 True
    prev_week = db.get_period_summary("2026-10-19", period="week", today_str="2026-10-29")
    assert prev_week["can_go_next"] is True
    assert prev_week["next_date_str"] == "2026-10-26"

    # 3. 每月汇总：2026-10-01 ~ 2026-10-31 (31天)
    month_summary = db.get_period_summary("2026-10-29", period="month", today_str="2026-10-29")
    assert month_summary["period"] == "month"
    assert month_summary["start_date_str"] == "2026-10-01"
    assert month_summary["end_date_str"] == "2026-10-31"
    assert month_summary["total_sec"] == 6000
    assert len(month_summary["chart_buckets"]) == 31
    assert month_summary["prev_date_str"] == "2026-09-01"
    assert month_summary["can_go_next"] is False
    db.close()
