# Dayflow Windows Time Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一款专为 Windows 设计的桌面软件使用时间追踪与可视化工具（Dayflow），平时静默挂在系统托盘后台按“当前实际激活软件”每秒计时，点开时以 Windows 现代深色无边框圆角窗口（Vue 3 + Vite + Tailwind CSS）丝滑展示今日总时长、24 小时分色堆叠柱状图、分类汇总、带真实 EXE 图标的双列软件排行及具体使用时间段流水。

**Architecture:** 后端采用 Python 3 (`pywin32` + `psutil` + `SQLite`) 负责前台窗口探测、系统底层进程过滤、UWP 子窗口穿透、EXE 原生图标提取以及跨整点自动切分的会话存储；前端采用 `Vue 3 + Vite + Tailwind CSS` 构建纯正 Windows 现代深色桌面工具界面，打包为静态资源后由 `PyWebView` (Edge WebView2) 无边框窗口加载，并通过 `pystray` 实现系统托盘常驻控制。

**Tech Stack:** Python 3.10+, `pywebview`, `pywin32`, `psutil`, `pystray`, `Pillow`, `pytest`, SQLite3, Vue 3, Vite, Tailwind CSS, Lucide Vue Next.

**Spec:** `docs/superpowers/specs/2026-10-28-dayflow-windows-time-tracker-design.md`

## Global Constraints

- **运行平台**：Windows 10 / Windows 11（利用系统自带 Edge WebView2 渲染独立窗口）。
- **统计口径**：同一时刻只计入当前前台激活窗口所属的有界面普通软件，不重复叠加；任意 1 小时桶（`hour_bucket: 0~23`）内所有软件时长之和不超过 `3600` 秒，当天各软件时长总和与顶部今日总时长完全相等。
- **进程过滤**：自动过滤系统底层进程（如 `svchost.exe`、`SearchHost.exe`、`LockApp.exe` 等）、纯桌面背景（`Progman`/`WorkerW`）、任务栏（`Shell_TrayWnd`）及 `Dayflow` 自身窗口；但打开文件夹浏览的 `explorer.exe` (`CabinetWClass`) 正常计入“文件资源管理器”。
- **视觉定位**：纯正 **Windows 现代深色桌面系统软件**（参考图1“小智桌面”的暗夜灰无边框圆角窗口、右上角图钉置顶/最小化/关闭控制栏、微软雅黑/Segoe UI 字体层级），数据看板采用参考图2的“总时长 + 24小时分色堆叠柱状图 + 分类汇总 + 双列应用图标网格”结构，绝不绘制手机状态栏或手机外壳。

## Review Focus

1. **跨整点与跨零点连续使用切分**：当用户从 `11:59:50` 持续使用同一软件到 `12:00:10`（或跨午夜 `23:59:50` 到次日 `00:00:10`）时，必须精准切分为归属不同 `hour_bucket` / `date_str` 的两条会话记录，确保持续时长不丢失且单小时柱状图永不超 60 分钟（由 Task 1 `test_record_span_splits_across_hour_and_midnight` 覆盖）。
2. **锁屏、纯桌面与文件资源管理器区分**：当 `explorer.exe` 处于桌面背景 (`Progman`/`WorkerW`) 或任务栏 (`Shell_TrayWnd`) 时必须忽略，处于文件夹窗口 (`CabinetWClass`) 时必须正常记录；`LockApp.exe` 锁屏激活时必须停止当前软件计时（由 Task 3 `test_filter_distinguishes_desktop_and_file_explorer` 覆盖）。
3. **UWP 宿主进程穿透失败兜底**：当 `ApplicationFrameHost.exe` 在前台但枚举不到非自身子进程 PID 时，必须过滤忽略而非将 `ApplicationFrameHost.exe` 当作普通软件计入排行榜（由 Task 3 `test_uwp_frame_host_penetration_and_fallback` 覆盖）。
4. **修改软件分类或屏蔽软件后的全局数据一致性**：当用户修改某软件分类（如从 `other` 改为 `social`）或将其设为屏蔽（`is_ignored = 1`）后，当日总时长、24 小时各柱子分色时长、分类汇总及软件列表必须实时同步重算且总和严丝合缝（由 Task 1 `test_update_category_and_ignore_recalculates_summary` 覆盖）。
5. **异常路径或无版本信息 EXE 的元数据提取降级**：当 `.exe` 路径不存在、无权限访问或缺失 `FileDescription` 版本资源时，元数据与图标提取必须安静降级为内置词典名/进程名与默认透明占位图标，绝不能抛出未捕获异常中断采集线程（由 Task 2 `test_extract_app_metadata_graceful_fallback` 覆盖）。

---

## File Structure

```text
e:\workspace\useless\dayflow\
├── requirements.txt                         # Python 依赖清单
├── main.py                                  # 应用启动入口（串联 Tracker、Tray 与 PyWebView 窗口）
├── dayflow/
│   ├── __init__.py
│   ├── database.py                          # SQLite 存储、跨整点切分算法、24h 柱状图与排行聚合查询
│   ├── app_meta.py                          # 软件分类词典、友好名称解析、Win32 EXE 图标提取转 Base64
│   ├── window_filter.py                     # Win32 前台窗口获取、系统进程过滤、UWP 穿透识别
│   ├── tracker.py                           # 后台 1s 采样守护引擎与内存会话合并缓冲
│   ├── bridge.py                            # PyWebView JS-API 桥接类 (DayflowBridge)
│   └── tray.py                              # pystray 系统托盘图标与右键菜单控制
├── tests/
│   ├── test_database.py                     # 数据库与跨整点切分、统计聚合单元测试
│   ├── test_app_meta.py                     # 软件名称美化、分类词典与图标提取降级测试
│   ├── test_window_filter.py                # 窗口过滤、桌面/资源管理器区分、UWP 穿透测试
│   ├── test_tracker.py                      # 采样状态机与会话合并落盘测试
│   └── test_bridge.py                       # 前后端桥接 API 接口契约测试
└── frontend/                                # Vue 3 + Vite + Tailwind CSS 前端工程
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.js
        ├── style.css                        # Windows 11 现代暗色滚动条、毛玻璃卡片与过渡动画样式
        ├── App.vue                          # 主窗口容器（整合顶栏、核心统计卡、应用排行与详情面板）
        ├── api/
        │   └── bridge.js                    # PyWebView API 封装 + 浏览器开发态仿真数据回退
        └── components/
            ├── TitleBar.vue                 # Windows 深色无边框顶栏（拖拽、日期切换、置顶图钉、最小化、关闭）
            ├── ScreenTimeCard.vue           # 核心统计大卡片（今日总时长、与昨日对比、分类汇总栏）
            ├── HourlyBarChart.vue           # 24 小时分色堆叠柱状图（0/6/12/18时刻度、悬停详情气泡）
            ├── AppUsageGrid.vue             # 软件使用排行区（双列图标磁贴视图 / 单列进度条视图切换）
            └── AppDetailModal.vue           # 单软件使用时段流水抽屉/面板（时段列表、改分类、屏蔽开关）
```

---

### Task 1: SQLite 存储层与跨整点会话切分引擎 (`dayflow/database.py`)

**Files:**
- Create: `requirements.txt`
- Create: `dayflow/__init__.py`
- Create: `dayflow/database.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Produces:
  - `class UsageDatabase(db_path: str | Path)`
  - `UsageDatabase.upsert_app(exe_path: str, exe_name: str, display_name: str, category: str, icon_base64: str = "") -> int`
  - `UsageDatabase.record_usage_span(app_id: int, start_dt: datetime, end_dt: datetime, window_title: str = "", merge_gap_sec: int = 5) -> list[int]`
  - `UsageDatabase.get_daily_summary(date_str: str) -> dict` (返回 `date_str`, `total_sec`, `yesterday_total_sec`, `hourly_buckets`: 长度 24 的列表，每项含 `hour`, `total_sec`, `categories: dict[str, int]`, `category_totals: list[dict]`, `apps: list[dict]`)
  - `UsageDatabase.get_app_daily_sessions(app_id: int, date_str: str) -> dict` (返回软件信息与当天按时间倒序/正序排列的 `sessions: list[dict]`)
  - `UsageDatabase.update_app_settings(app_id: int, category: str | None = None, display_name: str | None = None, is_ignored: bool | None = None) -> dict`
  - `UsageDatabase.get_recent_dates(days: int = 7, ref_date: str | None = None) -> list[dict]`

- [ ] **Step 1: 创建 `requirements.txt` 与包初始化文件 `dayflow/__init__.py`**

在 `requirements.txt` 中声明：`pywebview>=5.0`, `pywin32>=306`, `psutil>=5.9`, `pystray>=0.19`, `Pillow>=10.0`, `pytest>=8.0`。

- [ ] **Step 2: 编写 `tests/test_database.py` 失败测试（覆盖跨整点/跨天切分、相近会话合并及分类/屏蔽重算）**

```python
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
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_database.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'dayflow.database'`)

- [ ] **Step 4: 实现 `dayflow/database.py`**

在 `dayflow/database.py` 中实现 `UsageDatabase`：
- 创建 `apps` 与 `usage_sessions` 两张表及 `(date_str, hour_bucket)`、`(app_id, date_str)` 索引。
- `record_usage_span` 按整点边界（每个小时的 `XX:00:00`）循环切分 `[start_dt, end_dt]` 为若干子区间；若同一小时桶内最后一条属于该 `app_id` 的记录其 `end_time` 与当前 `start_dt` 间隔 `<= merge_gap_sec`，则直接合并延长该记录的 `end_time`、`duration_sec` 与 `last_window_title`（同时确保单桶内单条合并后严格处于同一小时内）。
- `get_daily_summary` 过滤掉 `apps.is_ignored = 1` 的应用，聚合出 24 个小时桶、5 大预设分类（`social`, `creative`, `entertainment`, `productivity`, `other`）的时长、应用排行列表以及前一天总时长。

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_database.py -v`
Expected: PASS

---

### Task 2: Windows 软件元数据、分类词典与 EXE 图标提取器 (`dayflow/app_meta.py`)

**Files:**
- Create: `dayflow/app_meta.py`
- Test: `tests/test_app_meta.py`

**Interfaces:**
- Produces:
  - `CATEGORY_META: dict[str, dict]` (定义 `social`, `creative`, `entertainment`, `productivity`, `other` 的中文标签与主题色值)
  - `resolve_app_metadata(exe_path: str, exe_name: str | None = None) -> dict` (返回 `exe_path`, `exe_name`, `display_name`, `category`, `icon_base64`)
  - `classify_app(exe_name: str, display_name: str = "", exe_path: str = "") -> str`
  - `extract_exe_icon_base64(exe_path: str) -> str`

- [ ] **Step 1: 编写 `tests/test_app_meta.py` 失败测试**

```python
import sys
from dayflow.app_meta import classify_app, resolve_app_metadata, CATEGORY_META


def test_builtin_dictionary_classifies_common_windows_apps():
    assert classify_app("WeChat.exe", "微信") == "social"
    assert classify_app("Code.exe", "Visual Studio Code") == "creative"
    assert classify_app("chrome.exe", "Google Chrome") == "productivity"
    assert classify_app("cloudmusic.exe", "网易云音乐") == "entertainment"
    assert set(CATEGORY_META.keys()) == {"social", "creative", "entertainment", "productivity", "other"}


def test_extract_app_metadata_graceful_fallback():
    # 不存在的路径必须优雅降级，返回去后缀友好名与默认 SVG/PNG Data URL 图标
    meta = resolve_app_metadata("C:/NonExistentDir/MyCoolApp.exe")
    assert meta["exe_name"] == "MyCoolApp.exe"
    assert meta["display_name"] == "MyCoolApp"
    assert meta["category"] == "other"
    assert meta["icon_base64"].startswith("data:image/")

    # 真实存在的系统 python.exe 能够提取出有效元数据与图标
    real_meta = resolve_app_metadata(sys.executable)
    assert real_meta["display_name"] != ""
    assert real_meta["icon_base64"].startswith("data:image/")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_app_meta.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'dayflow.app_meta'`)

- [ ] **Step 3: 实现 `dayflow/app_meta.py`**

在 `dayflow/app_meta.py` 中实现：
- 内置 60+ 款国内常用 Windows 软件的中文名称美化词典（如 `WeChat.exe` / `Weixin.exe` -> `微信`, `QQ.exe` -> `QQ`, `DingTalk.exe` -> `钉钉`, `feishu.exe` -> `飞书`, `chrome.exe` -> `Google Chrome`, `msedge.exe` -> `Microsoft Edge`, `Code.exe` -> `VS Code`, `idea64.exe` -> `IntelliJ IDEA`, `pycharm64.exe` -> `PyCharm`, `wps.exe` -> `WPS Office`, `WINWORD.EXE` -> `Microsoft Word`, `EXCEL.EXE` -> `Microsoft Excel`, `POWERPNT.EXE` -> `PowerPoint`, `cloudmusic.exe` -> `网易云音乐`, `QQMusic.exe` -> `QQ音乐`, `Douyin.exe` -> `抖音`, `bilibili.exe` -> `哔哩哔哩`, `PotPlayerMini64.exe` -> `PotPlayer`, `steam.exe` -> `Steam`, `explorer.exe` -> `文件资源管理器` 等）及分类匹配规则。
- 通过 `win32api.GetFileVersionInfo` 读取 `FileDescription` / `ProductName` 补充未知软件的友好名称。
- 通过 `win32gui.ExtractIconEx` + `win32ui.CreateDCFromHandle` + `CreateBitmap` 提取 32x32/48x48 BGRA 像素缓冲并用 `Pillow` (`Image.frombuffer`) 转为透明 PNG Base64 Data URL；若提取失败或无图标，生成带软件首字母与柔和渐变底色的 SVG Data URL 作为兜底图标。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_app_meta.py -v`
Expected: PASS

---

### Task 3: Win32 前台窗口探测、系统进程过滤与 1 秒采样追踪器 (`dayflow/window_filter.py` & `dayflow/tracker.py`)

**Files:**
- Create: `dayflow/window_filter.py`
- Create: `dayflow/tracker.py`
- Test: `tests/test_window_filter.py`
- Test: `tests/test_tracker.py`

**Interfaces:**
- Consumes:
  - `UsageDatabase` from `dayflow.database`
  - `resolve_app_metadata` from `dayflow.app_meta`
- Produces:
  - `@dataclass class ActiveWindowInfo(hwnd: int, pid: int, exe_path: str, exe_name: str, window_title: str, window_class: str)`
  - `should_track_window(info: ActiveWindowInfo, self_pid: int | None = None) -> bool`
  - `get_foreground_window_info(self_pid: int | None = None) -> ActiveWindowInfo | None`
  - `class ForegroundTracker(db: UsageDatabase, poll_interval: float = 1.0, flush_interval: float = 10.0)`
  - `ForegroundTracker.tick(now: datetime | None = None, window_info: ActiveWindowInfo | None = ...) -> None`
  - `ForegroundTracker.flush(now: datetime | None = None) -> None`
  - `ForegroundTracker.start() -> None` / `ForegroundTracker.stop() -> None`

- [ ] **Step 1: 编写 `tests/test_window_filter.py` 与 `tests/test_tracker.py` 失败测试**

```python
from datetime import datetime
from dayflow.window_filter import ActiveWindowInfo, should_track_window, resolve_uwp_child_pid
from dayflow.database import UsageDatabase
from dayflow.tracker import ForegroundTracker


def test_filter_distinguishes_desktop_and_file_explorer():
    # 纯桌面 Progman / WorkerW / 任务栏 Shell_TrayWnd 必须过滤
    desktop = ActiveWindowInfo(1, 100, "C:/Windows/explorer.exe", "explorer.exe", "", "Progman")
    taskbar = ActiveWindowInfo(2, 100, "C:/Windows/explorer.exe", "explorer.exe", "", "Shell_TrayWnd")
    # 正常打开的文件夹窗口 CabinetWClass 必须保留
    folder = ActiveWindowInfo(3, 100, "C:/Windows/explorer.exe", "explorer.exe", "dayflow - 文件资源管理器", "CabinetWClass")
    # 锁屏界面 LockApp.exe 必须过滤
    lock_screen = ActiveWindowInfo(4, 200, "C:/Windows/SystemApps/LockApp.exe", "LockApp.exe", "Windows 默认锁屏界面", "Windows.UI.Core.CoreWindow")

    assert should_track_window(desktop) is False
    assert should_track_window(taskbar) is False
    assert should_track_window(folder) is True
    assert should_track_window(lock_screen) is False


def test_uwp_frame_host_penetration_and_fallback():
    # 若子窗口全部仍是宿主 PID，则返回 None，且 ApplicationFrameHost 本身不计入排行
    assert resolve_uwp_child_pid(host_pid=500, child_pids=[500, 500]) is None
    assert resolve_uwp_child_pid(host_pid=500, child_pids=[500, 888]) == 888

    unpenetrated_uwp = ActiveWindowInfo(
        5, 500, "C:/Windows/System32/ApplicationFrameHost.exe", "ApplicationFrameHost.exe", "设置", "ApplicationFrameWindow"
    )
    assert should_track_window(unpenetrated_uwp) is False


def test_tracker_merges_ticks_and_flushes_on_switch(tmp_path):
    db = UsageDatabase(tmp_path / "tracker.db")
    tracker = ForegroundTracker(db, flush_interval=60.0)

    chrome = ActiveWindowInfo(10, 1001, "C:/Program Files/Google/Chrome/Application/chrome.exe", "chrome.exe", "GitHub - Chrome", "Chrome_WidgetWin_1")
    wechat = ActiveWindowInfo(20, 1002, "C:/Program Files/Tencent/WeChat/WeChat.exe", "WeChat.exe", "微信", "WeChatMainWndForPC")

    tracker.tick(datetime(2026, 10, 29, 14, 0, 0), window_info=chrome)
    tracker.tick(datetime(2026, 10, 29, 14, 0, 5), window_info=chrome)
    # 切换到微信，自动将 Chrome 的 10 秒落盘
    tracker.tick(datetime(2026, 10, 29, 14, 0, 10), window_info=wechat)
    tracker.tick(datetime(2026, 10, 29, 14, 0, 25), window_info=None)  # 锁屏/切到桌面

    summary = db.get_daily_summary("2026-10-29")
    assert summary["total_sec"] == 25
    by_name = {a["exe_name"]: a["total_sec"] for a in summary["apps"]}
    assert by_name["chrome.exe"] == 10
    assert by_name["WeChat.exe"] == 15
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_window_filter.py tests/test_tracker.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `dayflow/window_filter.py` 与 `dayflow/tracker.py`**

- 在 `dayflow/window_filter.py` 中：
  - 定义系统底层黑名单 `SYSTEM_EXE_BLACKLIST`（含 `svchost.exe`, `searchhost.exe`, `searchapp.exe`, `startmenuexperiencehost.exe`, `shellexperiencehost.exe`, `textinputhost.exe`, `lockapp.exe`, `logonui.exe`, `dwm.exe`, `conhost.exe`, `dllhost.exe`, `sihost.exe`, `taskhostw.exe`, `ctfmon.exe`, `applicationframehost.exe`, `widgets.exe`, `gamebar.exe` 等）。
  - 当 `exe_name.lower() == "explorer.exe"` 时，仅允许 `window_class in ("CabinetWClass", "ExploreWClass")` 且窗口标题非空。
  - 当检测到 `ApplicationFrameHost.exe` 时，通过 `win32gui.EnumChildWindows` 收集子窗口 PID 并调用 `resolve_uwp_child_pid` 替换为真实 UWP 进程路径与名称。
- 在 `dayflow/tracker.py` 中：
  - 维护当前活跃内存会话 `_active`；每次 `tick()` 计算与上一次采样的时间差 `delta`（若电脑休眠唤醒导致单次 `delta > 15` 秒，自动截断为 `1` 秒避免将睡眠时间误算进软件），当软件切换、进入锁屏/桌面空闲、达到 `flush_interval` 或前端主动请求最新数据时，调用 `db.record_usage_span` 落盘。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_window_filter.py tests/test_tracker.py -v`
Expected: PASS

---

### Task 4: PyWebView 前后端桥接 API、系统托盘与主程序入口 (`dayflow/bridge.py`, `dayflow/tray.py`, `main.py`)

**Files:**
- Create: `dayflow/bridge.py`
- Create: `dayflow/tray.py`
- Create: `main.py`
- Test: `tests/test_bridge.py`

**Interfaces:**
- Consumes:
  - `UsageDatabase` from `dayflow.database`
  - `ForegroundTracker` from `dayflow.tracker`
- Produces:
  - `class DayflowBridge(db: UsageDatabase, tracker: ForegroundTracker, window_Getter: Callable | None = None)`
  - `DayflowBridge.get_dashboard_data(date_str: str | None = None) -> dict`
  - `DayflowBridge.get_app_detail(app_id: int, date_str: str | None = None) -> dict`
  - `DayflowBridge.update_app(app_id: int, category: str | None = None, display_name: str | None = None, is_ignored: bool | None = None) -> dict`
  - `DayflowBridge.get_ignored_apps() -> list[dict]`
  - `DayflowBridge.toggle_always_on_top() -> dict`
  - `DayflowBridge.minimize_window() -> dict`
  - `DayflowBridge.hide_to_tray() -> dict`

- [ ] **Step 1: 编写 `tests/test_bridge.py` 失败测试**

```python
from datetime import datetime
from dayflow.database import UsageDatabase
from dayflow.tracker import ForegroundTracker
from dayflow.bridge import DayflowBridge
from dayflow.window_filter import ActiveWindowInfo


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

    app_id = data["apps"][0]["id"]
    detail = bridge.get_app_detail(app_id, "2026-10-29")
    assert len(detail["sessions"]) == 1
    assert detail["sessions"][0]["duration_sec"] == 120
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_bridge.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `dayflow/bridge.py`, `dayflow/tray.py` 与 `main.py`**

- `DayflowBridge.get_dashboard_data` 先调用 `self.tracker.flush()` 将内存中未满 10 秒的最新实时秒数刷入 SQLite，再返回当日概览、`recent_dates`（近 7 天日期及每日总秒数）、`category_meta` 以及当前正在使用的软件状态。
- `dayflow/tray.py` 使用 `Pillow` 动态绘制高清深色圆角彩色柱状图托盘图标，提供“打开 Dayflow 面板”、“窗口置顶/取消置顶”、“退出程序”菜单。
- `main.py` 启动后台 `ForegroundTracker` 守护线程与 `pystray` 托盘线程，创建 `430 × 760` 的无边框 `pywebview` 独立窗口（支持加载 `frontend/dist/index.html` 或 `--dev` 模式下连接 `http://localhost:5173`）。

- [ ] **Step 4: 运行全部后端测试确认通过**

Run: `pytest -v`
Expected: All tests PASS

---

### Task 5: Vue 3 + Vite + Tailwind CSS 工程初始化与 Windows 深色顶栏 / 24小时堆叠柱状图看板 (`frontend/`)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`
- Create: `frontend/src/style.css`
- Create: `frontend/src/api/bridge.js`
- Create: `frontend/src/components/TitleBar.vue`
- Create: `frontend/src/components/HourlyBarChart.vue`
- Create: `frontend/src/components/ScreenTimeCard.vue`

**Interfaces:**
- Consumes:
  - `window.pywebview.api` (`get_dashboard_data`, `toggle_always_on_top`, `minimize_window`, `hide_to_tray`)
- Produces:
  - `fetchDashboardData(dateStr)` in `frontend/src/api/bridge.js`
  - `TitleBar.vue`, `HourlyBarChart.vue`, `ScreenTimeCard.vue`

- [ ] **Step 1: 创建 `frontend/` 配置文件并安装前端依赖**

在 `frontend/package.json` 中配置 `vue@^3.4.0`, `lucide-vue-next@^0.400.0`, `vite@^5.3.0`, `@vitejs/plugin-vue@^5.0.0`, `tailwindcss@^3.4.0`, `postcss`, `autoprefixer`，配置 `vite.config.js` 使用 `base: './'` 确保 `PyWebView` 本地文件路径加载正常。

- [ ] **Step 2: 实现 `frontend/src/api/bridge.js` 与 `TitleBar.vue`（参考图1“小智桌面”风格的 Windows 顶栏）**

- `bridge.js` 自动检测 `window.pywebview?.api`，在已就绪时调用真实 Python 后端，在未就绪或普通浏览器预览时提供结构完全一致的 Windows 软件仿真数据（微信、Google Chrome、VS Code、抖音、红果短剧等）。
- `TitleBar.vue` 采用 `pywebview-drag-region` 类名支持无边框窗口拖拽，左侧显示四色品牌图标与胶囊导航标签（`总览`、`排行`、`时段明细`、`屏蔽管理`），右侧提供与参考图1一致的 **图钉置顶按钮（激活时高亮翠绿/蓝色）**、**最小化按钮**、**关闭至托盘按钮**。

- [ ] **Step 3: 实现 `HourlyBarChart.vue` 与 `ScreenTimeCard.vue`（24小时分色堆叠柱状图与分类汇总大卡片）**

- `ScreenTimeCard.vue` 顶部提供近 7 天快速日期切换胶囊条与今日累计总时长大字（如 `18小时 57分钟`）及昨日对比角标。
- `HourlyBarChart.vue` 渲染 0~23 时共 24 根分色圆角堆叠柱子：
  - 虚线水平参考线与右侧刻度（`2小时`/`1小时`、`30分钟`、`0`）及底部横轴时间刻度（`0时`、`6时`、`12时`、`18时`）；
  - 每根柱子按该小时内各分类秒数占 3600 秒的比例堆叠高度（社交通讯 `#3B82F6`、创意开发 `#06B6D4`、影音娱乐 `#F59E0B`、办公效率 `#10B981`、其他 `#71717A`），带 CSS `cubic-bezier(0.22, 1, 0.36, 1)` 生长过渡动画与鼠标悬停详情气泡，点击任意柱子可筛选该小时使用的软件。
- 柱状图下方横向展示前 3~4 大分类的彩色标题与各自累计时长。

---

### Task 6: 双列软件图标网格、时间段流水明细面板与前后端联调构建 (`frontend/src/components/AppUsageGrid.vue`, `AppDetailModal.vue`, `App.vue`)

**Files:**
- Create: `frontend/src/components/AppUsageGrid.vue`
- Create: `frontend/src/components/AppDetailModal.vue`
- Create: `frontend/src/App.vue`

**Interfaces:**
- Consumes:
  - `get_app_detail(appId, dateStr)`, `update_app(appId, payload)`, `get_ignored_apps()` from `frontend/src/api/bridge.js`
- Produces:
  - 完整构建产物 `frontend/dist/index.html` 供 `main.py` 直接加载。

- [ ] **Step 1: 实现 `AppUsageGrid.vue`（双列图标磁贴视图 & 单列进度条排行切换）**

- 默认展示参考图2同款的 **双列图标网格**：左侧 38x38 圆角软件真实图标（从 EXE 提取的透明 PNG），右侧上方白色软件名（如 `微信`、`Google Chrome`、`VS Code`），下方灰色累计时长（如 `4小时`、`1小时 16分钟`），当前正在前台计时的软件带有呼吸绿点指示。
- 右上角支持一键切换为 **单列进度条详细视图**（显示占比百分比、启动会话次数与分类色标）。

- [ ] **Step 2: 实现 `AppDetailModal.vue` 与 `App.vue`（单软件使用时间段流水与分类修改面板）**

- 点击任意软件卡片弹出丝滑详情面板 `AppDetailModal.vue`：
  - 展示该软件当天的 24 小时微型分布柱状图；
  - 展示按时间排列的 **具体使用时间段流水列表**（例如 `14:10:05 - 14:53:20 · 43分钟 · 窗口标题`），直接回答“哪个时间使用了哪个软件”；
  - 提供 5 大分类标签按钮（点击即改分类并立即刷新主面板柱状图颜色）与“忽略/不统计此软件”开关。
- `App.vue` 每 `3 秒` 静默轮询刷新当日实时计时数据，支持在顶部导航标签间丝滑切换。

- [ ] **Step 3: 执行前端生产构建并运行全量冒烟验证**

Run: `npm --prefix frontend run build` and `pytest -v`
Expected: `frontend/dist/index.html` 生成成功，所有后端与桥接测试全部 PASS，运行 `python main.py --smoke-test` 验证真实 Windows 前台窗口采集、图标提取与看板数据输出正常。
