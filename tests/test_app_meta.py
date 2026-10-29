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

