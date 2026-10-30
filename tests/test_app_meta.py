import sys
from dayflow.app_meta import (
    CATEGORY_META,
    classify_app,
    extract_exe_icon_base64,
    resolve_app_metadata,
)


def test_builtin_dictionary_classifies_common_windows_apps():
    assert classify_app("WeChat.exe", "微信") == "social"
    assert classify_app("Code.exe", "Visual Studio Code") == "creative"
    assert classify_app("chrome.exe", "Google Chrome") == "productivity"
    assert classify_app("cloudmusic.exe", "网易云音乐") == "entertainment"
    assert set(CATEGORY_META.keys()) == {
        "social",
        "creative",
        "entertainment",
        "productivity",
        "other",
    }
    for key, val in CATEGORY_META.items():
        assert val["key"] == key
        assert isinstance(val["label"], str) and val["label"]
        assert val["color"].startswith("#")


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


def test_known_apps_display_name_and_case_insensitivity():
    wechat_meta = resolve_app_metadata("C:/Program Files/Tencent/WeChat/wechat.exe")
    assert wechat_meta["display_name"] == "微信"
    assert wechat_meta["category"] == "social"

    douyin_meta = resolve_app_metadata("D:/Apps/douyin.exe")
    assert douyin_meta["display_name"] == "抖音"
    assert douyin_meta["category"] == "entertainment"

    explorer_meta = resolve_app_metadata("C:/Windows/explorer.exe")
    assert explorer_meta["display_name"] == "文件资源管理器"
    assert explorer_meta["category"] == "productivity"


def test_extract_exe_icon_base64_directly():
    fallback_icon = extract_exe_icon_base64("C:/NonExistentDir/NoSuchApp.exe")
    assert fallback_icon.startswith("data:image/svg+xml;base64,")

    real_icon = extract_exe_icon_base64(sys.executable)
    assert real_icon.startswith("data:image/")


def test_win32_version_info_and_png_icon_on_system_binary():
    import os

    regedit_path = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "regedit.exe")
    if os.path.isfile(regedit_path):
        meta = resolve_app_metadata(regedit_path)
        assert meta["exe_name"].lower() == "regedit.exe"
        assert meta["display_name"] != ""
        assert meta["icon_base64"].startswith("data:image/png;base64,")


def test_resolve_browser_tab_category() -> None:
    from dayflow.app_meta import resolve_browser_tab_category

    # 1. 影音娱乐识别
    assert (
        resolve_browser_tab_category("chrome.exe", "【4K】2026最新大片 - 哔哩哔哩_bilibili")
        == "entertainment"
    )
    assert resolve_browser_tab_category("msedge.exe", "YouTube - Home") == "entertainment"

    # 2. 社交通讯识别
    assert (
        resolve_browser_tab_category("chrome.exe", "微博 – 随时随地发现新鲜事")
        == "social"
    )
    assert resolve_browser_tab_category("firefox.exe", "知乎 - 有问题就会有答案") == "social"

    # 3. 开发与创意识别
    assert (
        resolve_browser_tab_category("msedge.exe", "codeInbpm/dayflow: Desktop usage tracker - GitHub")
        == "creative"
    )
    assert resolve_browser_tab_category("chrome.exe", "ChatGPT - OpenAI") == "creative"

    # 4. 办公与效率识别
    assert (
        resolve_browser_tab_category("chrome.exe", "产品设计文档 - 飞书云文档")
        == "productivity"
    )

    # 5. 非浏览器或普通页面返回 None 回退为主分类
    assert resolve_browser_tab_category("notepad.exe", "bilibili") is None
    assert resolve_browser_tab_category("chrome.exe", "新标签页") is None


def test_pwa_and_local_app_dynamic_detection() -> None:
    from dayflow.app_meta import inspect_pwa_or_standalone_app

    # 1. 独立窗口 Facebook PWA（无浏览器后缀）
    is_pwa, name, exe_name, exe_path, cat = inspect_pwa_or_standalone_app(
        exe_name="msedge.exe",
        window_title="Facebook - 登录或注册",
        window_class="Chrome_WidgetWin_1",
    )
    assert is_pwa is True
    assert name == "Facebook"
    assert exe_name == "Facebook.exe"
    assert exe_path == "PWA:Facebook"
    assert cat == "social"

    # 2. 独立窗口 TikTok PWA（无浏览器后缀）
    is_pwa, name, exe_name, exe_path, cat = inspect_pwa_or_standalone_app(
        exe_name="chrome.exe",
        window_title="TikTok - Make Your Day",
        window_class="Chrome_WidgetWin_1",
    )
    assert is_pwa is True
    assert name == "TikTok"
    assert exe_name == "TikTok.exe"
    assert exe_path == "PWA:TikTok"
    assert cat == "entertainment"

    # 3. 普通浏览器标签页（带浏览器后缀，应放行给浏览器二级分类处理，不当独立应用）
    is_pwa_tab, _, _, _, _ = inspect_pwa_or_standalone_app(
        exe_name="chrome.exe",
        window_title="TikTok - Make Your Day - Google Chrome",
        window_class="Chrome_WidgetWin_1",
    )
    assert is_pwa_tab is False

    is_edge_tab, _, _, _, _ = inspect_pwa_or_standalone_app(
        exe_name="msedge.exe",
        window_title="Facebook - 个人 - Microsoft Edge",
        window_class="Chrome_WidgetWin_1",
    )
    assert is_edge_tab is False

    # 4. 本地独立软件的动态 1 级分类
    assert classify_app("HBuilderX.exe", "HBuilderX") == "creative"
    assert classify_app("xterminal.exe", "XTerminal") == "creative"
    assert classify_app("Grok Bot.exe", "Grok Bot") == "creative"
    assert classify_app("WorkBuddy.exe", "WorkBuddy") == "productivity"


def test_official_brand_icons_and_database_healing(tmp_path):
    from dayflow.app_meta import get_official_brand_icon_base64
    from dayflow.database import UsageDatabase

    # 1. 验证 TikTok 与 Facebook 拥有官方高清矢量 Logo
    tiktok_icon = get_official_brand_icon_base64("TikTok")
    assert tiktok_icon is not None
    assert tiktok_icon.startswith("data:image/svg+xml;base64,")

    fb_icon = get_official_brand_icon_base64("Facebook")
    assert fb_icon is not None
    assert fb_icon.startswith("data:image/svg+xml;base64,")

    # 2. 验证元数据解析优先使用官方真实 Logo 而非普通图标
    meta_tiktok = resolve_app_metadata("PWA:TikTok", "TikTok.exe", override_display_name="TikTok")
    assert meta_tiktok["icon_base64"] == tiktok_icon

    meta_fb = resolve_app_metadata("PWA:Facebook", "Facebook.exe", override_display_name="Facebook")
    assert meta_fb["icon_base64"] == fb_icon

    # 3. 验证数据库旧数据自愈：之前存入 Edge 图标的记录，启动时自动更新为官方真实 Logo！
    db = UsageDatabase(tmp_path / "heal_test.db")
    fake_edge_icon = "data:image/png;base64,FAKE_EDGE_ICON"
    db.upsert_app("PWA:TikTok", "TikTok.exe", "TikTok", "entertainment", fake_edge_icon)
    db.upsert_app("PWA:Facebook", "Facebook.exe", "Facebook", "social", fake_edge_icon)

    healed = db.heal_brand_icons()
    assert healed == 2

    with db._lock, db._conn:
        row_tk = db._conn.execute("SELECT icon_base64 FROM apps WHERE display_name = 'TikTok'").fetchone()
        assert row_tk["icon_base64"] == tiktok_icon

        row_fb = db._conn.execute("SELECT icon_base64 FROM apps WHERE display_name = 'Facebook'").fetchone()
        assert row_fb["icon_base64"] == fb_icon

