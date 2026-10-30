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
        self.heal_brand_icons()

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
                "SELECT id, icon_base64, display_name FROM apps WHERE exe_path = ?",
                (exe_path,),
            ).fetchone()
            if row is not None:
                app_id = int(row["id"])
                # 当旧图标为空，或者传入了全新的官方矢量高清图标且旧图标非官方矢量时，自动更新图标
                should_update_icon = False
                if not row["icon_base64"] and icon_base64:
                    should_update_icon = True
                elif icon_base64 and icon_base64.startswith("data:image/svg+xml") and not str(row["icon_base64"]).startswith("data:image/svg+xml"):
                    should_update_icon = True

                if should_update_icon:
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

    def heal_brand_icons(self) -> int:
        """检查并自愈已知知名品牌应用（如 TikTok, Facebook）被错误保存的旧图标。"""
        try:
            from dayflow.app_meta import get_official_brand_icon_base64
        except ImportError:
            return 0

        healed_count = 0
        with self._lock, self._conn:
            rows = self._conn.execute(
                "SELECT id, display_name, exe_name, icon_base64 FROM apps"
            ).fetchall()
            for r in rows:
                app_id = int(r["id"])
                disp = str(r["display_name"] or "")
                official = get_official_brand_icon_base64(disp) or get_official_brand_icon_base64(str(r["exe_name"] or ""))
                if official and r["icon_base64"] != official:
                    self._conn.execute(
                        "UPDATE apps SET icon_base64 = ? WHERE id = ?",
                        (official, app_id),
                    )
                    healed_count += 1
        return healed_count

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
            old_cat: str | None = None
            norm_cat: str | None = None

            if category is not None:
                old_row = self._conn.execute(
                    "SELECT category FROM apps WHERE id = ?", (app_id,)
                ).fetchone()
                if old_row is not None:
                    old_cat = str(old_row["category"])
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
                if norm_cat is not None and norm_cat != old_cat:
                    self._conn.execute(
                        """
                        UPDATE usage_sessions
                        SET category = ?
                        WHERE app_id = ? AND (category IS NULL OR category = '' OR category = ?)
                        """,
                        (norm_cat, app_id, old_cat or ""),
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
        """获取用户偏好设置（语言、外观主题、字体缩放级别、开机自启、久坐提醒配置、空闲挂机配置）。"""
        defaults: dict[str, object] = {
            "language": "system",  # 'system' | 'zh-CN' | 'en' | 'zh-TW'
            "theme": "dark",       # 'system' | 'dark' | 'light'
            "font_scale": 1.0,     # 0.85 ~ 1.30
            "auto_start": False,
            "health_remind_enabled": True,
            "rest_remind_interval_sec": 1800,  # 默认 30 分钟 (1800秒)
            "health_remind_sound": True,
            "health_remind_dnd_game": True,
            "idle_detection_enabled": True,
            "idle_threshold_sec": 180,
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

        health_remind_enabled = raw.get("health_remind_enabled", "1") in ("1", "true", "True")

        try:
            rest_remind_interval_sec = int(raw.get("rest_remind_interval_sec", "1800"))
            rest_remind_interval_sec = max(300, min(14400, rest_remind_interval_sec))
        except Exception:
            rest_remind_interval_sec = 1800

        health_remind_sound = raw.get("health_remind_sound", "1") in ("1", "true", "True")
        health_remind_dnd_game = raw.get("health_remind_dnd_game", "1") in ("1", "true", "True")
        idle_detection_enabled = raw.get("idle_detection_enabled", "1") in ("1", "true", "True")

        try:
            idle_threshold_sec = int(raw.get("idle_threshold_sec", "180"))
            idle_threshold_sec = max(30, min(3600, idle_threshold_sec))
        except Exception:
            idle_threshold_sec = 180

        global_hotkey_enabled = raw.get("global_hotkey_enabled", "1") in ("1", "true", "True")
        global_hotkey = str(raw.get("global_hotkey", "Ctrl+Shift+D")).strip() or "Ctrl+Shift+D"

        return {
            "language": lang,
            "theme": theme,
            "font_scale": font_scale,
            "auto_start": auto_start,
            "health_remind_enabled": health_remind_enabled,
            "rest_remind_interval_sec": rest_remind_interval_sec,
            "health_remind_sound": health_remind_sound,
            "health_remind_dnd_game": health_remind_dnd_game,
            "idle_detection_enabled": idle_detection_enabled,
            "idle_threshold_sec": idle_threshold_sec,
            "global_hotkey_enabled": global_hotkey_enabled,
            "global_hotkey": global_hotkey,
        }

    def update_preferences(self, updates: dict[str, object]) -> dict[str, object]:
        """更新并保存用户偏好设置，持久化至 SQLite 数据库。"""
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
        health_remind_enabled = bool(merged.get("health_remind_enabled", True))

        try:
            rest_remind_interval_sec = int(merged.get("rest_remind_interval_sec", 1800))
            rest_remind_interval_sec = max(300, min(14400, rest_remind_interval_sec))
        except Exception:
            rest_remind_interval_sec = 1800

        health_remind_sound = bool(merged.get("health_remind_sound", True))
        health_remind_dnd_game = bool(merged.get("health_remind_dnd_game", True))
        idle_detection_enabled = bool(merged.get("idle_detection_enabled", True))

        try:
            idle_threshold_sec = int(merged.get("idle_threshold_sec", 180))
            idle_threshold_sec = max(30, min(3600, idle_threshold_sec))
        except Exception:
            idle_threshold_sec = 180

        global_hotkey_enabled = bool(merged.get("global_hotkey_enabled", True))
        global_hotkey = str(merged.get("global_hotkey", "Ctrl+Shift+D")).strip() or "Ctrl+Shift+D"

        to_store = {
            "language": lang,
            "theme": theme,
            "font_scale": str(font_scale),
            "auto_start": "1" if auto_start else "0",
            "health_remind_enabled": "1" if health_remind_enabled else "0",
            "rest_remind_interval_sec": str(rest_remind_interval_sec),
            "health_remind_sound": "1" if health_remind_sound else "0",
            "health_remind_dnd_game": "1" if health_remind_dnd_game else "0",
            "idle_detection_enabled": "1" if idle_detection_enabled else "0",
            "idle_threshold_sec": str(idle_threshold_sec),
            "global_hotkey_enabled": "1" if global_hotkey_enabled else "0",
            "global_hotkey": global_hotkey,
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

    def export_usage_csv_text(
        self, date_str: str | None = None, period: str = "day"
    ) -> str:
        """导出规范详细的 CSV 报表文本（包含 1 级、2 级分类明确模板，带 UTF-8 BOM）。"""
        import csv
        import io

        target_date = date_str or datetime.now().strftime("%Y-%m-%d")

        # 确定起止日期
        if period == "week":
            base_dt = datetime.strptime(target_date, "%Y-%m-%d")
            start_dt = base_dt - timedelta(days=base_dt.weekday())
            end_dt = start_dt + timedelta(days=6)
            start_str = start_dt.strftime("%Y-%m-%d")
            end_str = end_dt.strftime("%Y-%m-%d")
            period_label = f"周报 ({start_str} ~ {end_str})"
        elif period == "month":
            parts = [int(p) for p in target_date.split("-")]
            y, m = parts[0], parts[1]
            last_day = calendar.monthrange(y, m)[1]
            start_str = f"{y:04d}-{m:02d}-01"
            end_str = f"{y:04d}-{m:02d}-{last_day:02d}"
            period_label = f"月报 ({y}年{m}月)"
        else:
            start_str = target_date
            end_str = target_date
            period_label = f"日报 ({target_date})"

        with self._lock:
            # 1. 查询会话明细
            rows = self._conn.execute(
                """
                SELECT 
                    s.date_str,
                    s.start_time,
                    s.end_time,
                    s.duration_sec,
                    s.hour_bucket,
                    s.last_window_title,
                    a.display_name,
                    a.exe_name,
                    a.category AS base_category,
                    COALESCE(s.category, a.category) AS session_category
                FROM usage_sessions s
                JOIN apps a ON a.id = s.app_id
                WHERE s.date_str BETWEEN ? AND ? AND a.is_ignored = 0
                ORDER BY s.date_str ASC, s.hour_bucket ASC, s.start_time ASC, s.id ASC
                """,
                (start_str, end_str),
            ).fetchall()

            # 2. 查询一级分类汇总
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

        total_sec = sum(int(r["duration_sec"]) for r in rows)

        def _fmt_dur(sec: int) -> str:
            h = sec // 3600
            m = (sec % 3600) // 60
            s = sec % 60
            if h > 0:
                return f"{h}小时{m}分{s}秒"
            if m > 0:
                return f"{m}分{s}秒"
            return f"{s}秒"

        def _resolve_sub_cat(exe_name: str, window_title: str, pri_cat: str) -> str:
            low_t = (window_title or "").lower()
            low_e = (exe_name or "").lower()
            if any(k in low_t for k in ("bilibili", "哔哩哔哩", "b站")):
                return "B站视频播放 (影音娱乐)"
            if any(k in low_t for k in ("youtube", "youtu.be")):
                return "YouTube 视频流媒体 (影音娱乐)"
            if any(k in low_t for k in ("网易云音乐", "cloudmusic", "qq音乐", "kugou")):
                return "在线音乐与电台 (影音娱乐)"
            if any(k in low_t for k in ("爱奇艺", "iqiyi", "腾讯视频", "优酷", "youku", "netflix", "twitch")):
                return "影视长视频 (影音娱乐)"
            if any(k in low_e for k in ("lol", "league", "genshin", "steam", "epic", "dota", "valorant", "game")):
                return "电脑游戏客户端 (影音娱乐)"
            if any(k in low_t for k in ("github", "gitlab", "gitee")):
                return "代码托管与PR协作 (开发创意)"
            if any(k in low_t for k in ("chatgpt", "claude", "deepseek", "kimi", "openai")):
                return "AI大模型对话助手 (开发创意)"
            if any(k in low_t for k in ("stackoverflow", "v2ex", "leetcode", "掘金", "segmentfault")):
                return "技术社区与题库 (开发创意)"
            if any(k in low_t for k in ("figma", "mastergo", "pixso", "canva", "dribbble")):
                return "UI与创意设计 (开发创意)"
            if any(k in low_e for k in ("code.exe", "idea64.exe", "pycharm", "cursor.exe", "visualstudio", "devenv.exe")):
                return "IDE集成开发工具 (开发创意)"
            if any(k in low_t for k in ("飞书", "feishu", "lark")):
                return "飞书协同办公 (办公效率)"
            if any(k in low_t for k in ("语雀", "yuque", "notion", "wolai", "obsidian", "flowus")):
                return "团队与个人知识库 (办公效率)"
            if any(k in low_t for k in ("google docs", "google sheets", "腾讯文档", "金山文档", "kdocs", "office", "excel", "word")):
                return "在线协同文档 (办公效率)"
            if any(k in low_e for k in ("wps.exe", "word.exe", "excel.exe", "powerpnt.exe")):
                return "桌面办公套件 (办公效率)"
            if any(k in low_t for k in ("微博", "weibo")):
                return "微博热搜动态 (社交通讯)"
            if any(k in low_t for k in ("知乎", "zhihu")):
                return "知乎问答专栏 (社交通讯)"
            if any(k in low_t for k in ("twitter", "x.com", "reddit")):
                return "海外社交平台 (社交通讯)"
            if any(k in low_e for k in ("wechat.exe", "qq.exe", "dingtalk.exe", "telegram", "discord")):
                return "即时通讯聊天 (社交通讯)"

            fallback_labels = {
                "social": "社交通讯软件",
                "creative": "开发与设计工具",
                "entertainment": "影音娱乐通用",
                "productivity": "办公效率工具",
                "other": "日常工具与系统",
            }
            return fallback_labels.get(pri_cat, "通用软件分类")

        output = io.StringIO()
        # 写入 UTF-8 BOM 确保在 Windows Excel/WPS 打开不乱码
        output.write("\ufeff")
        writer = csv.writer(output)

        # 1. 报表头部信息
        writer.writerow(["# Dayflow 桌面屏幕使用时间明细报表"])
        writer.writerow(["# 统计周期", period_label])
        writer.writerow(["# 导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow(["# 累计时长", _fmt_dur(total_sec), f"{total_sec} 秒"])
        writer.writerow(["# 会话总数", f"{len(rows)} 条"])
        writer.writerow([])

        # 2. 一级分类分布汇总表
        writer.writerow(["【一级分类时长汇总】"])
        writer.writerow(["分类代码", "一级分类名称", "累计时长", "时长(秒)", "占比"])
        for cr in cat_rows:
            c_key = str(cr["category"])
            c_sec = int(cr["sec"])
            c_lbl = CATEGORY_LABELS.get(c_key, c_key)
            ratio = (c_sec / total_sec * 100) if total_sec > 0 else 0
            writer.writerow([c_key, c_lbl, _fmt_dur(c_sec), c_sec, f"{ratio:.1f}%"])
        writer.writerow([])

        # 3. 详细会话流水清单 (明确的 1 级、2 级分类列)
        writer.writerow(["【时段使用会话流水明细表】"])
        headers = [
            "日期",
            "开始时间",
            "结束时间",
            "小时时段",
            "使用时长",
            "时长(秒)",
            "一级主分类",
            "二级细分分类",
            "软件名称",
            "进程程序",
            "窗口/网页标题",
        ]
        writer.writerow(headers)

        for r in rows:
            pri_key = str(r["session_category"] or "other")
            pri_label = CATEGORY_LABELS.get(pri_key, "其他工具")
            exe = str(r["exe_name"] or "")
            title = str(r["last_window_title"] or "")
            sec = int(r["duration_sec"])
            sub_label = _resolve_sub_cat(exe, title, pri_key)

            writer.writerow(
                [
                    str(r["date_str"]),
                    str(r["start_time"]),
                    str(r["end_time"]),
                    f"{r['hour_bucket']:02d}:00",
                    _fmt_dur(sec),
                    sec,
                    pri_label,
                    sub_label,
                    str(r["display_name"]),
                    exe,
                    title,
                ]
            )

        return output.getvalue()

    def export_usage_excel_bytes(
        self, date_str: str | None = None, period: str = "day"
    ) -> bytes:
        """导出高度美观、自适应列宽且包含分类彩色背景标签的专业 Excel 工作簿 (.xlsx)。"""
        try:
            import openpyxl
            from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            # 优雅回退
            return self.export_usage_csv_text(date_str, period=period).encode("utf-8-sig")

        import io

        target_date = date_str or datetime.now().strftime("%Y-%m-%d")

        if period == "week":
            base_dt = datetime.strptime(target_date, "%Y-%m-%d")
            start_dt = base_dt - timedelta(days=base_dt.weekday())
            end_dt = start_dt + timedelta(days=6)
            start_str = start_dt.strftime("%Y-%m-%d")
            end_str = end_dt.strftime("%Y-%m-%d")
            period_label = f"周报 ({start_str} ~ {end_str})"
        elif period == "month":
            parts = [int(p) for p in target_date.split("-")]
            y, m = parts[0], parts[1]
            last_day = calendar.monthrange(y, m)[1]
            start_str = f"{y:04d}-{m:02d}-01"
            end_str = f"{y:04d}-{m:02d}-{last_day:02d}"
            period_label = f"月报 ({y}年{m}月)"
        else:
            start_str = target_date
            end_str = target_date
            period_label = f"日报 ({target_date})"

        with self._lock:
            rows = self._conn.execute(
                """
                SELECT 
                    s.date_str,
                    s.start_time,
                    s.end_time,
                    s.duration_sec,
                    s.hour_bucket,
                    s.last_window_title,
                    a.display_name,
                    a.exe_name,
                    a.category AS base_category,
                    COALESCE(s.category, a.category) AS session_category
                FROM usage_sessions s
                JOIN apps a ON a.id = s.app_id
                WHERE s.date_str BETWEEN ? AND ? AND a.is_ignored = 0
                ORDER BY s.date_str ASC, s.hour_bucket ASC, s.start_time ASC, s.id ASC
                """,
                (start_str, end_str),
            ).fetchall()

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

        total_sec = sum(int(r["duration_sec"]) for r in rows)

        def _fmt_dur(sec: int) -> str:
            h = sec // 3600
            m = (sec % 3600) // 60
            s = sec % 60
            if h > 0:
                return f"{h}小时{m}分{s}秒"
            if m > 0:
                return f"{m}分{s}秒"
            return f"{s}秒"

        def _resolve_sub_cat(exe_name: str, window_title: str, pri_cat: str) -> str:
            low_t = (window_title or "").lower()
            low_e = (exe_name or "").lower()
            if any(k in low_t for k in ("bilibili", "哔哩哔哩", "b站")):
                return "B站视频播放 (影音娱乐)"
            if any(k in low_t for k in ("youtube", "youtu.be")):
                return "YouTube 视频流媒体 (影音娱乐)"
            if any(k in low_t for k in ("网易云音乐", "cloudmusic", "qq音乐", "kugou")):
                return "在线音乐与电台 (影音娱乐)"
            if any(k in low_t for k in ("爱奇艺", "iqiyi", "腾讯视频", "优酷", "youku", "netflix", "twitch")):
                return "影视长视频 (影音娱乐)"
            if any(k in low_e for k in ("lol", "league", "genshin", "steam", "epic", "dota", "valorant", "game")):
                return "电脑游戏客户端 (影音娱乐)"
            if any(k in low_t for k in ("github", "gitlab", "gitee")):
                return "代码托管与PR协作 (开发创意)"
            if any(k in low_t for k in ("chatgpt", "claude", "deepseek", "kimi", "openai")):
                return "AI大模型对话助手 (开发创意)"
            if any(k in low_t for k in ("stackoverflow", "v2ex", "leetcode", "掘金", "segmentfault")):
                return "技术社区与题库 (开发创意)"
            if any(k in low_t for k in ("figma", "mastergo", "pixso", "canva", "dribbble")):
                return "UI与创意设计 (开发创意)"
            if any(k in low_e for k in ("code.exe", "idea64.exe", "pycharm", "cursor.exe", "visualstudio", "devenv.exe")):
                return "IDE集成开发工具 (开发创意)"
            if any(k in low_t for k in ("飞书", "feishu", "lark")):
                return "飞书协同办公 (办公效率)"
            if any(k in low_t for k in ("语雀", "yuque", "notion", "wolai", "obsidian", "flowus")):
                return "团队与个人知识库 (办公效率)"
            if any(k in low_t for k in ("google docs", "google sheets", "腾讯文档", "金山文档", "kdocs", "office", "excel", "word")):
                return "在线协同文档 (办公效率)"
            if any(k in low_e for k in ("wps.exe", "word.exe", "excel.exe", "powerpnt.exe")):
                return "桌面办公套件 (办公效率)"
            if any(k in low_t for k in ("微博", "weibo")):
                return "微博热搜动态 (社交通讯)"
            if any(k in low_t for k in ("知乎", "zhihu")):
                return "知乎问答专栏 (社交通讯)"
            if any(k in low_t for k in ("twitter", "x.com", "reddit")):
                return "海外社交平台 (社交通讯)"
            if any(k in low_e for k in ("wechat.exe", "qq.exe", "dingtalk.exe", "telegram", "discord")):
                return "即时通讯聊天 (社交通讯)"

            fallback_labels = {
                "social": "社交通讯软件",
                "creative": "开发与设计工具",
                "entertainment": "影音娱乐通用",
                "productivity": "办公效率工具",
                "other": "日常工具与系统",
            }
            return fallback_labels.get(pri_cat, "通用软件分类")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Dayflow_{period}"
        ws.views.sheetView[0].showGridLines = True

        # 配色与样式系统（参考图 2）
        CATEGORY_PILL_STYLES = {
            "social": {
                "fill": PatternFill(start_color="DCEBFE", end_color="DCEBFE", fill_type="solid"),
                "font": Font(name="Microsoft YaHei", size=10, bold=True, color="1E40AF"),
            },
            "creative": {
                "fill": PatternFill(start_color="CFFAFE", end_color="CFFAFE", fill_type="solid"),
                "font": Font(name="Microsoft YaHei", size=10, bold=True, color="0E7490"),
            },
            "entertainment": {
                "fill": PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid"),
                "font": Font(name="Microsoft YaHei", size=10, bold=True, color="92400E"),
            },
            "productivity": {
                "fill": PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid"),
                "font": Font(name="Microsoft YaHei", size=10, bold=True, color="065F46"),
            },
            "other": {
                "fill": PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid"),
                "font": Font(name="Microsoft YaHei", size=10, bold=True, color="475569"),
            },
        }

        thin_side = Side(border_style="thin", color="E2E8F0")
        thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        header_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        header_font = Font(name="Microsoft YaHei", size=10, bold=True, color="0F172A")
        body_font = Font(name="Microsoft YaHei", size=10, color="1E293B")
        title_font = Font(name="Microsoft YaHei", size=13, bold=True, color="0F172A")
        sub_title_font = Font(name="Microsoft YaHei", size=11, bold=True, color="1E293B")
        meta_label_font = Font(name="Microsoft YaHei", size=10, bold=True, color="64748B")

        # 1. 顶部报表概要信息
        ws["A1"] = "Dayflow 桌面屏幕使用时间明细报表"
        ws["A1"].font = title_font

        metadata_rows = [
            ("统计周期", period_label),
            ("导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("累计时长", f"{_fmt_dur(total_sec)} ({total_sec} 秒)"),
            ("会话总数", f"{len(rows)} 条"),
        ]
        curr_row = 3
        for label, val in metadata_rows:
            ws.cell(row=curr_row, column=1, value=label).font = meta_label_font
            ws.cell(row=curr_row, column=2, value=val).font = body_font
            curr_row += 1

        curr_row += 1
        # 2. 一级分类时长汇总
        ws.cell(row=curr_row, column=1, value="【一级分类时长汇总】").font = sub_title_font
        curr_row += 1

        cat_headers = ["分类代码", "一级分类名称", "累计时长", "时长(秒)", "占比"]
        for c_idx, h in enumerate(cat_headers, start=1):
            cell = ws.cell(row=curr_row, column=c_idx, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center" if c_idx != 2 else "left", vertical="center")
        curr_row += 1

        for cr in cat_rows:
            c_key = str(cr["category"])
            c_sec = int(cr["sec"])
            c_lbl = CATEGORY_LABELS.get(c_key, c_key)
            ratio = (c_sec / total_sec * 100) if total_sec > 0 else 0
            style = CATEGORY_PILL_STYLES.get(c_key, CATEGORY_PILL_STYLES["other"])

            row_vals = [c_key, c_lbl, _fmt_dur(c_sec), c_sec, f"{ratio:.1f}%"]
            for c_idx, val in enumerate(row_vals, start=1):
                cell = ws.cell(row=curr_row, column=c_idx, value=val)
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center" if c_idx in (1, 3, 5) else "right" if c_idx == 4 else "left", vertical="center")
                if c_idx == 2:
                    cell.fill = style["fill"]
                    cell.font = style["font"]
                else:
                    cell.font = body_font
            curr_row += 1

        curr_row += 1
        # 3. 时段使用会话流水明细表
        ws.cell(row=curr_row, column=1, value="【时段使用会话流水明细表】").font = sub_title_font
        curr_row += 1

        flow_headers = [
            "日期",
            "开始时间",
            "结束时间",
            "小时时段",
            "使用时长",
            "时长(秒)",
            "一级主分类",
            "详细二级分类",
            "软件名称",
            "进程程序",
            "窗口/网页标题",
        ]
        for c_idx, h in enumerate(flow_headers, start=1):
            cell = ws.cell(row=curr_row, column=c_idx, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center", vertical="center")
        curr_row += 1

        for r in rows:
            pri_key = str(r["session_category"] or "other")
            pri_label = CATEGORY_LABELS.get(pri_key, "其他工具")
            exe = str(r["exe_name"] or "")
            title = str(r["last_window_title"] or "")
            sec = int(r["duration_sec"])
            sub_label = _resolve_sub_cat(exe, title, pri_key)
            style = CATEGORY_PILL_STYLES.get(pri_key, CATEGORY_PILL_STYLES["other"])

            row_data = [
                str(r["date_str"]),
                str(r["start_time"]),
                str(r["end_time"]),
                f"{r['hour_bucket']:02d}:00",
                _fmt_dur(sec),
                sec,
                pri_label,
                sub_label,
                str(r["display_name"]),
                exe,
                title,
            ]
            for c_idx, val in enumerate(row_data, start=1):
                cell = ws.cell(row=curr_row, column=c_idx, value=val)
                cell.border = thin_border
                cell.font = body_font
                if c_idx in (1, 2, 3, 4, 5):
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif c_idx == 6:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                elif c_idx in (7, 8):
                    cell.fill = style["fill"]
                    cell.font = style["font"]
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
            curr_row += 1

        # 4. 关键：自适应安全列宽设置（确保用户双击打开时绝不会缩成一团变成 #####）
        column_widths = {
            "A": 15,  # 日期 2026-10-30
            "B": 12,  # 开始时间
            "C": 12,  # 结束时间
            "D": 12,  # 小时时段
            "E": 14,  # 使用时长
            "F": 12,  # 时长(秒)
            "G": 16,  # 一级主分类
            "H": 22,  # 详细二级分类
            "I": 20,  # 软件名称
            "J": 18,  # 进程程序
            "K": 40,  # 窗口/网页标题
        }
        for col_letter, width in column_widths.items():
            ws.column_dimensions[col_letter].width = width

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
