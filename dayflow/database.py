from __future__ import annotations

import calendar
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

CATEGORIES: tuple[str, ...] = (
    "social",
    "creative",
    "entertainment",
    "productivity",
    "other",
)

CATEGORY_LABELS: dict[str, str] = {
    "social": "社交通讯",
    "creative": "创意与开发",
    "entertainment": "影音娱乐",
    "productivity": "办公与效率",
    "other": "其他",
}

WEEKDAY_NAMES: tuple[str, ...] = (
    "周一",
    "周二",
    "周三",
    "周四",
    "周五",
    "周六",
    "周日",
)


def _parse_session_end_dt(date_str: str, hour_bucket: int, end_time_str: str) -> datetime:
    """Parse stored session (date_str, hour_bucket, end_time) back into a datetime."""
    if end_time_str == "24:00:00" or (hour_bucket == 23 and end_time_str == "00:00:00"):
        return datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
    return datetime.strptime(f"{date_str} {end_time_str}", "%Y-%m-%d %H:%M:%S")


class UsageDatabase:
    """SQLite storage layer with hour-boundary session splitting and aggregation."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS apps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exe_path TEXT UNIQUE NOT NULL,
                    exe_name TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'other',
                    icon_base64 TEXT NOT NULL DEFAULT '',
                    is_ignored INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_id INTEGER NOT NULL REFERENCES apps(id),
                    date_str TEXT NOT NULL,
                    hour_bucket INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    duration_sec INTEGER NOT NULL,
                    last_window_title TEXT NOT NULL DEFAULT ''
                );
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_date_hour ON usage_sessions(date_str, hour_bucket);"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_app_date ON usage_sessions(app_id, date_str);"
            )
            try:
                self._conn.execute("ALTER TABLE usage_sessions ADD COLUMN category TEXT;")
            except Exception:
                pass
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def upsert_app(
        self,
        exe_path: str,
        exe_name: str,
        display_name: str,
        category: str,
        icon_base64: str = "",
    ) -> int:
        """Insert a new app or return existing app_id without overwriting user-modified fields."""
        norm_category = category if category in CATEGORIES else "other"
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT id, icon_base64 FROM apps WHERE exe_path = ?",
                (exe_path,),
            ).fetchone()
            if row is not None:
                app_id = int(row["id"])
                if not row["icon_base64"] and icon_base64:
                    self._conn.execute(
                        "UPDATE apps SET icon_base64 = ? WHERE id = ?",
                        (icon_base64, app_id),
                    )
                return app_id

            cur = self._conn.execute(
                """
                INSERT INTO apps (exe_path, exe_name, display_name, category, icon_base64, is_ignored)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (exe_path, exe_name, display_name or exe_name, norm_category, icon_base64 or ""),
            )
            return int(cur.lastrowid)

    def record_usage_span(
        self,
        app_id: int,
        start_dt: datetime,
        end_dt: datetime,
        window_title: str = "",
        merge_gap_sec: int = 5,
        category: str | None = None,
    ) -> list[int]:
        """Split [start_dt, end_dt] across hour boundaries and merge adjacent sessions in same hour."""
        if end_dt <= start_dt:
            return []

        session_ids: list[int] = []
        cur_start = start_dt

        with self._lock, self._conn:
            while cur_start < end_dt:
                hour_end = cur_start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                seg_end = min(end_dt, hour_end)
                seg_sec = int(round((seg_end - cur_start).total_seconds()))

                if seg_sec > 0:
                    date_str = cur_start.strftime("%Y-%m-%d")
                    hour_bucket = cur_start.hour
                    start_time_str = cur_start.strftime("%H:%M:%S")
                    if seg_end == hour_end and hour_bucket == 23:
                        end_time_str = "24:00:00"
                    else:
                        end_time_str = seg_end.strftime("%H:%M:%S")

                    last_row = self._conn.execute(
                        """
                        SELECT id, start_time, end_time, duration_sec, last_window_title, category
                        FROM usage_sessions
                        WHERE app_id = ? AND date_str = ? AND hour_bucket = ?
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (app_id, date_str, hour_bucket),
                    ).fetchone()

                    merged = False
                    if last_row is not None:
                        try:
                            last_end_dt = _parse_session_end_dt(
                                date_str, hour_bucket, str(last_row["end_time"])
                            )
                            gap = (cur_start - last_end_dt).total_seconds()
                            # 仅在时间连续且细分分类一致时合并
                            old_cat = last_row["category"]
                            cat_compatible = (not category) or (not old_cat) or (old_cat == category)
                            if -1.0 <= gap <= merge_gap_sec and cat_compatible:
                                sid = int(last_row["id"])
                                new_duration = min(3600, int(last_row["duration_sec"]) + seg_sec)
                                new_title = window_title if window_title else str(last_row["last_window_title"])
                                final_cat = category or old_cat
                                self._conn.execute(
                                    """
                                    UPDATE usage_sessions
                                    SET end_time = ?, duration_sec = ?, last_window_title = ?, category = ?
                                    WHERE id = ?
                                    """,
                                    (end_time_str, new_duration, new_title, final_cat, sid),
                                )
                                session_ids.append(sid)
                                merged = True
                        except ValueError:
                            merged = False

                    if not merged:
                        capped_sec = min(3600, seg_sec)
                        cur = self._conn.execute(
                            """
                            INSERT INTO usage_sessions (
                                app_id, date_str, hour_bucket, start_time, end_time, duration_sec, last_window_title, category
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                app_id,
                                date_str,
                                hour_bucket,
                                start_time_str,
                                end_time_str,
                                capped_sec,
                                window_title or "",
                                category,
                            ),
                        )
                        session_ids.append(int(cur.lastrowid))

                cur_start = seg_end

        return session_ids

    def _get_day_total_sec(self, date_str: str) -> int:
        row = self._conn.execute(
            """
            SELECT COALESCE(SUM(s.duration_sec), 0) AS total_sec
            FROM usage_sessions s
            JOIN apps a ON a.id = s.app_id
            WHERE s.date_str = ? AND a.is_ignored = 0
            """,
            (date_str,),
        ).fetchone()
        return int(row["total_sec"]) if row else 0

    def get_daily_summary(self, date_str: str) -> dict:
        """Aggregate 24-hour buckets, category totals, and app rankings for a given date."""
        with self._lock:
            hourly_buckets: list[dict] = [
                {
                    "hour": h,
                    "total_sec": 0,
                    "categories": {cat: 0 for cat in CATEGORIES},
                }
                for h in range(24)
            ]
            cat_totals_map: dict[str, int] = {cat: 0 for cat in CATEGORIES}

            bucket_rows = self._conn.execute(
                """
                SELECT s.hour_bucket, COALESCE(s.category, a.category) AS category, SUM(s.duration_sec) AS sec
                FROM usage_sessions s
                JOIN apps a ON a.id = s.app_id
                WHERE s.date_str = ? AND a.is_ignored = 0
                GROUP BY s.hour_bucket, COALESCE(s.category, a.category)
                """,
                (date_str,),
            ).fetchall()

            total_sec = 0
            for r in bucket_rows:
                h = int(r["hour_bucket"])
                if 0 <= h < 24:
                    cat = str(r["category"])
                    if cat not in CATEGORIES:
                        cat = "other"
                    sec = int(r["sec"])
                    hourly_buckets[h]["categories"][cat] += sec
                    hourly_buckets[h]["total_sec"] = min(
                        3600, hourly_buckets[h]["total_sec"] + sec
                    )
                    cat_totals_map[cat] += sec
                    total_sec += sec

            category_totals = [
                {
                    "category": cat,
                    "label": CATEGORY_LABELS.get(cat, cat),
                    "total_sec": cat_totals_map[cat],
                }
                for cat in CATEGORIES
            ]

            app_rows = self._conn.execute(
                """
                SELECT
                    a.id,
                    a.exe_path,
                    a.exe_name,
                    a.display_name,
                    a.category,
                    a.icon_base64,
                    SUM(s.duration_sec) AS total_sec,
                    COUNT(s.id) AS session_count,
                    (
                        SELECT s2.last_window_title
                        FROM usage_sessions s2
                        WHERE s2.app_id = a.id AND s2.date_str = ?
                        ORDER BY s2.id DESC
                        LIMIT 1
                    ) AS last_window_title
                FROM usage_sessions s
                JOIN apps a ON a.id = s.app_id
                WHERE s.date_str = ? AND a.is_ignored = 0
                GROUP BY a.id
                HAVING SUM(s.duration_sec) > 0
                ORDER BY total_sec DESC, a.id ASC
                """,
                (date_str, date_str),
            ).fetchall()

            apps = [
                {
                    "id": int(r["id"]),
                    "exe_path": str(r["exe_path"]),
                    "exe_name": str(r["exe_name"]),
                    "display_name": str(r["display_name"]),
                    "category": str(r["category"]),
                    "icon_base64": str(r["icon_base64"] or ""),
                    "total_sec": int(r["total_sec"]),
                    "session_count": int(r["session_count"]),
                    "last_window_title": str(r["last_window_title"] or ""),
                }
                for r in app_rows
            ]

            try:
                yesterday_str = (
                    datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
                ).strftime("%Y-%m-%d")
                yesterday_total_sec = self._get_day_total_sec(yesterday_str)
            except ValueError:
                yesterday_total_sec = 0

            return {
                "date_str": date_str,
                "total_sec": total_sec,
                "yesterday_total_sec": yesterday_total_sec,
                "hourly_buckets": hourly_buckets,
                "category_totals": category_totals,
                "apps": apps,
            }

    def get_app_daily_sessions(self, app_id: int, date_str: str) -> dict:
        """Return app metadata, 24-hour distribution array, and session list for a specific date."""
        with self._lock:
            app_row = self._conn.execute(
                """
                SELECT id, exe_path, exe_name, display_name, category, icon_base64, is_ignored
                FROM apps
                WHERE id = ?
                """,
                (app_id,),
            ).fetchone()

            if app_row is None:
                app_info = {
                    "id": app_id,
                    "exe_path": "",
                    "exe_name": "",
                    "display_name": "",
                    "category": "other",
                    "icon_base64": "",
                    "is_ignored": False,
                }
            else:
                app_info = {
                    "id": int(app_row["id"]),
                    "exe_path": str(app_row["exe_path"]),
                    "exe_name": str(app_row["exe_name"]),
                    "display_name": str(app_row["display_name"]),
                    "category": str(app_row["category"]),
                    "icon_base64": str(app_row["icon_base64"] or ""),
                    "is_ignored": bool(app_row["is_ignored"]),
                }

            session_rows = self._conn.execute(
                """
                SELECT id, start_time, end_time, duration_sec, hour_bucket, last_window_title
                FROM usage_sessions
                WHERE app_id = ? AND date_str = ?
                ORDER BY hour_bucket ASC, start_time ASC, id ASC
                """,
                (app_id, date_str),
            ).fetchall()

            hourly_sec = [0] * 24
            sessions: list[dict] = []
            total_sec = 0

            for r in session_rows:
                hb = int(r["hour_bucket"])
                dur = int(r["duration_sec"])
                if 0 <= hb < 24:
                    hourly_sec[hb] = min(3600, hourly_sec[hb] + dur)
                total_sec += dur
                sessions.append(
                    {
                        "id": int(r["id"]),
                        "start_time": str(r["start_time"]),
                        "end_time": str(r["end_time"]),
                        "duration_sec": dur,
                        "hour_bucket": hb,
                        "last_window_title": str(r["last_window_title"] or ""),
                    }
                )

            return {
                **app_info,
                "app": app_info,
                "date_str": date_str,
                "total_sec": total_sec,
                "hourly_sec": hourly_sec,
                "sessions": sessions,
            }

    def update_app_settings(
        self,
        app_id: int,
        category: str | None = None,
        display_name: str | None = None,
        is_ignored: bool | None = None,
    ) -> dict:
        """Update category, display_name, or is_ignored flag for an app."""
        with self._lock, self._conn:
            updates: list[str] = []
            params: list[object] = []

            if category is not None:
                norm_cat = category if category in CATEGORIES else "other"
                updates.append("category = ?")
                params.append(norm_cat)
            if display_name is not None:
                updates.append("display_name = ?")
                params.append(display_name)
            if is_ignored is not None:
                updates.append("is_ignored = ?")
                params.append(1 if is_ignored else 0)

            if updates:
                params.append(app_id)
                self._conn.execute(
                    f"UPDATE apps SET {', '.join(updates)} WHERE id = ?",
                    tuple(params),
                )

            row = self._conn.execute(
                """
                SELECT id, exe_path, exe_name, display_name, category, icon_base64, is_ignored
                FROM apps
                WHERE id = ?
                """,
                (app_id,),
            ).fetchone()

            if row is None:
                return {
                    "id": app_id,
                    "exe_path": "",
                    "exe_name": "",
                    "display_name": display_name or "",
                    "category": category or "other",
                    "icon_base64": "",
                    "is_ignored": bool(is_ignored),
                }

            return {
                "id": int(row["id"]),
                "exe_path": str(row["exe_path"]),
                "exe_name": str(row["exe_name"]),
                "display_name": str(row["display_name"]),
                "category": str(row["category"]),
                "icon_base64": str(row["icon_base64"] or ""),
                "is_ignored": bool(row["is_ignored"]),
            }

    def get_ignored_apps(self) -> list[dict]:
        """Return all apps marked as is_ignored = 1."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, exe_path, exe_name, display_name, category, icon_base64, is_ignored
                FROM apps
                WHERE is_ignored = 1
                ORDER BY id ASC
                """
            ).fetchall()
            return [
                {
                    "id": int(r["id"]),
                    "exe_path": str(r["exe_path"]),
                    "exe_name": str(r["exe_name"]),
                    "display_name": str(r["display_name"]),
                    "category": str(r["category"]),
                    "icon_base64": str(r["icon_base64"] or ""),
                    "is_ignored": True,
                }
                for r in rows
            ]

    def get_recent_dates(
        self,
        days: int = 7,
        ref_date: str | None = None,
        today_str: str | None = None,
    ) -> list[dict]:
        """Return daily totals for the trailing `days` ending at `ref_date` (inclusive).
        Labels '今日' / '昨日' are always computed relative to actual `today_str` (not `ref_date`).
        """
        actual_today_dt = (
            datetime.strptime(today_str, "%Y-%m-%d")
            if today_str
            else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        )
        if ref_date:
            base_dt = datetime.strptime(ref_date, "%Y-%m-%d")
        else:
            base_dt = actual_today_dt

        # If ref_date is within the last `days` of actual_today_dt, anchor window end at actual_today_dt
        # so the user can always navigate forward back to today.
        count = max(1, days)
        if (actual_today_dt.date() - base_dt.date()).days < count and base_dt.date() <= actual_today_dt.date():
            window_end_dt = actual_today_dt
        else:
            window_end_dt = base_dt

        start_dt = window_end_dt - timedelta(days=count - 1)
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = window_end_dt.strftime("%Y-%m-%d")

        with self._lock:
            rows = self._conn.execute(
                """
                SELECT s.date_str, COALESCE(SUM(s.duration_sec), 0) AS total_sec
                FROM usage_sessions s
                JOIN apps a ON a.id = s.app_id
                WHERE s.date_str BETWEEN ? AND ? AND a.is_ignored = 0
                GROUP BY s.date_str
                """,
                (start_str, end_str),
            ).fetchall()
            totals_by_date = {str(r["date_str"]): int(r["total_sec"]) for r in rows}

        results: list[dict] = []
        for idx in range(count):
            cur_dt = start_dt + timedelta(days=idx)
            d_str = cur_dt.strftime("%Y-%m-%d")
            offset_from_today = (actual_today_dt.date() - cur_dt.date()).days
            if offset_from_today == 0:
                label = "今日"
            elif offset_from_today == 1:
                label = "昨日"
            else:
                label = cur_dt.strftime("%m-%d")

            results.append(
                {
                    "date_str": d_str,
                    "label": label,
                    "weekday": WEEKDAY_NAMES[cur_dt.weekday()],
                    "total_sec": totals_by_date.get(d_str, 0),
                }
            )
        return results

    def _query_range_apps_and_categories(
        self, start_str: str, end_str: str
    ) -> tuple[int, dict[str, int], list[dict], list[dict]]:
        """Helper to aggregate total_sec, category_totals, and app rankings across [start_str, end_str]."""
        cat_totals_map: dict[str, int] = {cat: 0 for cat in CATEGORIES}
        cat_rows = self._conn.execute(
            """
            SELECT COALESCE(s.category, a.category) AS category, COALESCE(SUM(s.duration_sec), 0) AS sec
            FROM usage_sessions s
            JOIN apps a ON a.id = s.app_id
            WHERE s.date_str BETWEEN ? AND ? AND a.is_ignored = 0
            GROUP BY COALESCE(s.category, a.category)
            """,
            (start_str, end_str),
        ).fetchall()

        total_sec = 0
        for r in cat_rows:
            cat = str(r["category"])
            if cat not in CATEGORIES:
                cat = "other"
            sec = int(r["sec"])
            cat_totals_map[cat] += sec
            total_sec += sec

        category_totals = [
            {
                "category": cat,
                "label": CATEGORY_LABELS.get(cat, cat),
                "total_sec": cat_totals_map[cat],
            }
            for cat in CATEGORIES
        ]

        app_rows = self._conn.execute(
            """
            SELECT
                a.id,
                a.exe_path,
                a.exe_name,
                a.display_name,
                a.category,
                a.icon_base64,
                SUM(s.duration_sec) AS total_sec,
                COUNT(s.id) AS session_count,
                (
                    SELECT s2.last_window_title
                    FROM usage_sessions s2
                    WHERE s2.app_id = a.id AND s2.date_str BETWEEN ? AND ?
                    ORDER BY s2.date_str DESC, s2.id DESC
                    LIMIT 1
                ) AS last_window_title
            FROM usage_sessions s
            JOIN apps a ON a.id = s.app_id
            WHERE s.date_str BETWEEN ? AND ? AND a.is_ignored = 0
            GROUP BY a.id
            HAVING SUM(s.duration_sec) > 0
            ORDER BY total_sec DESC, a.id ASC
            """,
            (start_str, end_str, start_str, end_str),
        ).fetchall()

        apps = [
            {
                "id": int(r["id"]),
                "exe_path": str(r["exe_path"]),
                "exe_name": str(r["exe_name"]),
                "display_name": str(r["display_name"]),
                "category": str(r["category"]),
                "icon_base64": str(r["icon_base64"] or ""),
                "total_sec": int(r["total_sec"]),
                "session_count": int(r["session_count"]),
                "last_window_title": str(r["last_window_title"] or ""),
            }
            for r in app_rows
        ]
        return total_sec, cat_totals_map, category_totals, apps

    def _get_range_total_sec(self, start_str: str, end_str: str) -> int:
        row = self._conn.execute(
            """
            SELECT COALESCE(SUM(s.duration_sec), 0) AS total_sec
            FROM usage_sessions s
            JOIN apps a ON a.id = s.app_id
            WHERE s.date_str BETWEEN ? AND ? AND a.is_ignored = 0
            """,
            (start_str, end_str),
        ).fetchone()
        return int(row["total_sec"]) if row else 0

    def get_period_summary(
        self,
        date_str: str,
        period: str = "day",
        today_str: str | None = None,
    ) -> dict:
        """Return aggregated summary for `period` in ('day', 'week', 'month') anchored at `date_str`."""
        norm_period = period if period in ("day", "week", "month") else "day"
        actual_today_str = today_str or datetime.now().strftime("%Y-%m-%d")
        today_dt = datetime.strptime(actual_today_str, "%Y-%m-%d")
        target_dt = datetime.strptime(date_str, "%Y-%m-%d")

        if norm_period == "day":
            summary = self.get_daily_summary(date_str)
            prev_dt = target_dt - timedelta(days=1)
            next_dt = target_dt + timedelta(days=1)
            prev_date_str = prev_dt.strftime("%Y-%m-%d")
            next_date_str = (
                next_dt.strftime("%Y-%m-%d") if target_dt.date() < today_dt.date() else None
            )

            offset_days = (today_dt.date() - target_dt.date()).days
            wk_name = WEEKDAY_NAMES[target_dt.weekday()]
            if offset_days == 0:
                period_label = f"{target_dt.month}月{target_dt.day}日 今日 · {wk_name}"
            elif offset_days == 1:
                period_label = f"{target_dt.month}月{target_dt.day}日 昨日 · {wk_name}"
            else:
                period_label = f"{target_dt.month}月{target_dt.day}日 · {wk_name}"

            return {
                **summary,
                "period": "day",
                "today_str": actual_today_str,
                "start_date_str": date_str,
                "end_date_str": date_str,
                "prev_date_str": prev_date_str,
                "next_date_str": next_date_str,
                "can_go_next": next_date_str is not None,
                "period_label": period_label,
                "avg_daily_sec": summary["total_sec"],
                "active_days_count": 1 if summary["total_sec"] > 0 else 0,
                "chart_buckets": [
                    {
                        "index": b["hour"],
                        "hour": b["hour"],
                        "label": f"{b['hour']}时",
                        "short_label": f"{b['hour']}时" if b["hour"] in (0, 6, 12, 18) else "",
                        "total_sec": b["total_sec"],
                        "max_sec": 3600,
                        "categories": b["categories"],
                    }
                    for b in summary["hourly_buckets"]
                ],
            }

        with self._lock:
            if norm_period == "week":
                # Monday = 0 .. Sunday = 6
                week_start_dt = target_dt - timedelta(days=target_dt.weekday())
                week_end_dt = week_start_dt + timedelta(days=6)
                start_str = week_start_dt.strftime("%Y-%m-%d")
                end_str = week_end_dt.strftime("%Y-%m-%d")

                prev_week_dt = week_start_dt - timedelta(days=7)
                next_week_dt = week_start_dt + timedelta(days=7)
                prev_date_str = prev_week_dt.strftime("%Y-%m-%d")
                if week_end_dt.date() < today_dt.date():
                    next_date_str = min(today_dt, next_week_dt).strftime("%Y-%m-%d")
                else:
                    next_date_str = None

                is_this_week = week_start_dt.date() <= today_dt.date() <= week_end_dt.date()
                range_text = f"{week_start_dt.month}月{week_start_dt.day}日 - {week_end_dt.month}月{week_end_dt.day}日"
                period_label = f"{range_text} · 本周" if is_this_week else range_text

                total_sec, _, category_totals, apps = self._query_range_apps_and_categories(
                    start_str, end_str
                )
                prev_start_str = prev_week_dt.strftime("%Y-%m-%d")
                prev_end_str = (prev_week_dt + timedelta(days=6)).strftime("%Y-%m-%d")
                prev_total_sec = self._get_range_total_sec(prev_start_str, prev_end_str)

                day_cat_rows = self._conn.execute(
                    """
                    SELECT s.date_str, COALESCE(s.category, a.category) AS category, COALESCE(SUM(s.duration_sec), 0) AS sec
                    FROM usage_sessions s
                    JOIN apps a ON a.id = s.app_id
                    WHERE s.date_str BETWEEN ? AND ? AND a.is_ignored = 0
                    GROUP BY s.date_str, COALESCE(s.category, a.category)
                    """,
                    (start_str, end_str),
                ).fetchall()

                day_map: dict[str, dict[str, int]] = {}
                for i in range(7):
                    d = (week_start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
                    day_map[d] = {cat: 0 for cat in CATEGORIES}

                for r in day_cat_rows:
                    d = str(r["date_str"])
                    cat = str(r["category"])
                    if cat not in CATEGORIES:
                        cat = "other"
                    if d in day_map:
                        day_map[d][cat] += int(r["sec"])

                chart_buckets: list[dict] = []
                active_days = 0
                for i in range(7):
                    cur_d = week_start_dt + timedelta(days=i)
                    d_str = cur_d.strftime("%Y-%m-%d")
                    cats = day_map[d_str]
                    d_total = sum(cats.values())
                    if d_total > 0:
                        active_days += 1
                    chart_buckets.append(
                        {
                            "index": i,
                            "date_str": d_str,
                            "label": f"{WEEKDAY_NAMES[i]} ({cur_d.month}/{cur_d.day})",
                            "short_label": WEEKDAY_NAMES[i],
                            "total_sec": d_total,
                            "categories": cats,
                        }
                    )

                divisor = max(1, active_days if active_days > 0 else (today_dt.weekday() + 1 if is_this_week else 7))
                avg_daily_sec = int(round(total_sec / divisor))

                return {
                    "period": "week",
                    "date_str": date_str,
                    "today_str": actual_today_str,
                    "start_date_str": start_str,
                    "end_date_str": end_str,
                    "prev_date_str": prev_date_str,
                    "next_date_str": next_date_str,
                    "can_go_next": next_date_str is not None,
                    "period_label": period_label,
                    "total_sec": total_sec,
                    "yesterday_total_sec": prev_total_sec,
                    "avg_daily_sec": avg_daily_sec,
                    "active_days_count": active_days,
                    "hourly_buckets": chart_buckets,
                    "chart_buckets": chart_buckets,
                    "category_totals": category_totals,
                    "apps": apps,
                }

            # norm_period == "month"
            year, month = target_dt.year, target_dt.month
            _, days_in_month = calendar.monthrange(year, month)
            month_start_dt = datetime(year, month, 1)
            month_end_dt = datetime(year, month, days_in_month)
            start_str = month_start_dt.strftime("%Y-%m-%d")
            end_str = month_end_dt.strftime("%Y-%m-%d")

            prev_month_end_dt = month_start_dt - timedelta(days=1)
            prev_month_start_dt = prev_month_end_dt.replace(day=1)
            prev_date_str = prev_month_start_dt.strftime("%Y-%m-%d")

            if (year, month) < (today_dt.year, today_dt.month):
                next_month_start_dt = month_end_dt + timedelta(days=1)
                next_date_str = min(today_dt, next_month_start_dt).strftime("%Y-%m-%d")
            else:
                next_date_str = None

            is_this_month = (year, month) == (today_dt.year, today_dt.month)
            period_label = f"{year}年{month}月 · 本月" if is_this_month else f"{year}年{month}月"

            total_sec, _, category_totals, apps = self._query_range_apps_and_categories(
                start_str, end_str
            )
            prev_total_sec = self._get_range_total_sec(
                prev_month_start_dt.strftime("%Y-%m-%d"),
                prev_month_end_dt.strftime("%Y-%m-%d"),
            )

            day_cat_rows = self._conn.execute(
                """
                SELECT s.date_str, COALESCE(s.category, a.category) AS category, COALESCE(SUM(s.duration_sec), 0) AS sec
                FROM usage_sessions s
                JOIN apps a ON a.id = s.app_id
                WHERE s.date_str BETWEEN ? AND ? AND a.is_ignored = 0
                GROUP BY s.date_str, COALESCE(s.category, a.category)
                """,
                (start_str, end_str),
            ).fetchall()

            day_map = {}
            for d_num in range(1, days_in_month + 1):
                d_str = f"{year:04d}-{month:02d}-{d_num:02d}"
                day_map[d_str] = {cat: 0 for cat in CATEGORIES}

            for r in day_cat_rows:
                d = str(r["date_str"])
                cat = str(r["category"])
                if cat not in CATEGORIES:
                    cat = "other"
                if d in day_map:
                    day_map[d][cat] += int(r["sec"])

            chart_buckets = []
            active_days = 0
            for d_num in range(1, days_in_month + 1):
                d_str = f"{year:04d}-{month:02d}-{d_num:02d}"
                cats = day_map[d_str]
                d_total = sum(cats.values())
                if d_total > 0:
                    active_days += 1
                show_tick = d_num in (1, 8, 15, 22, days_in_month)
                chart_buckets.append(
                    {
                        "index": d_num - 1,
                        "day": d_num,
                        "date_str": d_str,
                        "label": f"{month}月{d_num}日",
                        "short_label": f"{d_num}日" if show_tick else "",
                        "total_sec": d_total,
                        "categories": cats,
                    }
                )

            divisor = max(1, active_days if active_days > 0 else (today_dt.day if is_this_month else days_in_month))
            avg_daily_sec = int(round(total_sec / divisor))

            return {
                "period": "month",
                "date_str": date_str,
                "today_str": actual_today_str,
                "start_date_str": start_str,
                "end_date_str": end_str,
                "prev_date_str": prev_date_str,
                "next_date_str": next_date_str,
                "can_go_next": next_date_str is not None,
                "period_label": period_label,
                "total_sec": total_sec,
                "yesterday_total_sec": prev_total_sec,
                "avg_daily_sec": avg_daily_sec,
                "active_days_count": active_days,
                "hourly_buckets": chart_buckets,
                "chart_buckets": chart_buckets,
                "category_totals": category_totals,
                "apps": apps,
            }

    def get_preferences(self) -> dict[str, object]:
        """获取用户偏好设置（语言、外观主题、字体缩放级别、开机自启标记）。"""
        defaults: dict[str, object] = {
            "language": "system",  # 'system' | 'zh-CN' | 'en' | 'zh-TW'
            "theme": "dark",       # 'system' | 'dark' | 'light'
            "font_scale": 1.0,     # 0.92 ~ 1.20
            "auto_start": False,
        }
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM user_preferences").fetchall()
            raw = {str(r["key"]): str(r["value"]) for r in rows}

        lang = raw.get("language", str(defaults["language"]))
        if lang not in ("system", "zh-CN", "en", "zh-TW"):
            lang = "system"

        theme = raw.get("theme", str(defaults["theme"]))
        if theme not in ("system", "dark", "light"):
            theme = "dark"

        try:
            font_scale = float(raw.get("font_scale", "1.0"))
            font_scale = max(0.85, min(1.30, round(font_scale, 2)))
        except Exception:
            font_scale = 1.0

        auto_start = raw.get("auto_start", "0") in ("1", "true", "True")
        return {
            "language": lang,
            "theme": theme,
            "font_scale": font_scale,
            "auto_start": auto_start,
        }

    def update_preferences(self, updates: dict[str, object]) -> dict[str, object]:
        """更新并保存用户偏好设置。"""
        current = self.get_preferences()
        merged = {**current, **(updates or {})}

        lang = str(merged.get("language", "system"))
        if lang not in ("system", "zh-CN", "en", "zh-TW"):
            lang = "system"

        theme = str(merged.get("theme", "dark"))
        if theme not in ("system", "dark", "light"):
            theme = "dark"

        try:
            font_scale = float(merged.get("font_scale", 1.0))
            font_scale = max(0.85, min(1.30, round(font_scale, 2)))
        except Exception:
            font_scale = 1.0

        auto_start = bool(merged.get("auto_start", False))

        to_store = {
            "language": lang,
            "theme": theme,
            "font_scale": str(font_scale),
            "auto_start": "1" if auto_start else "0",
        }
        with self._lock, self._conn:
            for k, v in to_store.items():
                self._conn.execute(
                    """
                    INSERT INTO user_preferences (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (k, v),
                )
        return self.get_preferences()
