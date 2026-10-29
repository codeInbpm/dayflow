from __future__ import annotations

import base64
import html
import io
import os
from pathlib import Path

from PIL import Image

try:
    import win32api
    import win32con
    import win32gui
    import win32ui

    HAS_WIN32 = True
except ImportError:  # pragma: no cover
    HAS_WIN32 = False


CATEGORY_META: dict[str, dict] = {
    "social": {"key": "social", "label": "社交通讯", "color": "#3B82F6"},
    "creative": {"key": "creative", "label": "开发与创意", "color": "#06B6D4"},
    "entertainment": {"key": "entertainment", "label": "影音娱乐", "color": "#F59E0B"},
    "productivity": {"key": "productivity", "label": "办公与效率", "color": "#10B981"},
    "other": {"key": "other", "label": "其他工具", "color": "#94A3B8"},
}

# 内置 70+ 款国内常用 Windows 软件词典：小写 exe 名 -> (友好显示名称, 分类)
BUILTIN_APP_CATALOG: dict[str, tuple[str, str]] = {
    # 社交通讯 (social)
    "wechat.exe": ("微信", "social"),
    "weixin.exe": ("微信", "social"),
    "wechatappex.exe": ("微信小程序", "social"),
    "qq.exe": ("QQ", "social"),
    "tim.exe": ("TIM", "social"),
    "dingtalk.exe": ("钉钉", "social"),
    "feishu.exe": ("飞书", "social"),
    "lark.exe": ("飞书", "social"),
    "wxwork.exe": ("企业微信", "social"),
    "telegram.exe": ("Telegram", "social"),
    "discord.exe": ("Discord", "social"),
    "slack.exe": ("Slack", "social"),
    "teams.exe": ("Microsoft Teams", "social"),
    "ms-teams.exe": ("Microsoft Teams", "social"),
    "zoom.exe": ("Zoom", "social"),
    "wemeetapp.exe": ("腾讯会议", "social"),
    "aliim.exe": ("阿里旺旺", "social"),
    "qianniu.exe": ("千牛工作台", "social"),
    "yy.exe": ("YY语音", "social"),
    "kook.exe": ("KOOK", "social"),
    # 开发与创意 (creative)
    "code.exe": ("Visual Studio Code", "creative"),
    "cursor.exe": ("Cursor", "creative"),
    "windsurf.exe": ("Windsurf", "creative"),
    "antigravity.exe": ("Antigravity", "creative"),
    "trae.exe": ("Trae", "creative"),
    "idea64.exe": ("IntelliJ IDEA", "creative"),
    "idea.exe": ("IntelliJ IDEA", "creative"),
    "pycharm64.exe": ("PyCharm", "creative"),
    "pycharm.exe": ("PyCharm", "creative"),
    "webstorm64.exe": ("WebStorm", "creative"),
    "webstorm.exe": ("WebStorm", "creative"),
    "goland64.exe": ("GoLand", "creative"),
    "goland.exe": ("GoLand", "creative"),
    "clion64.exe": ("CLion", "creative"),
    "clion.exe": ("CLion", "creative"),
    "studio64.exe": ("Android Studio", "creative"),
    "devenv.exe": ("Visual Studio", "creative"),
    "git.exe": ("Git", "creative"),
    "git-bash.exe": ("Git Bash", "creative"),
    "githubdesktop.exe": ("GitHub Desktop", "creative"),
    "windowsterminal.exe": ("Windows Terminal", "creative"),
    "wt.exe": ("Windows Terminal", "creative"),
    "powershell.exe": ("PowerShell", "creative"),
    "pwsh.exe": ("PowerShell", "creative"),
    "cmd.exe": ("命令提示符", "creative"),
    "python.exe": ("Python", "creative"),
    "pythonw.exe": ("Python", "creative"),
    "node.exe": ("Node.js", "creative"),
    "photoshop.exe": ("Adobe Photoshop", "creative"),
    "illustrator.exe": ("Adobe Illustrator", "creative"),
    "adobe premiere pro.exe": ("Adobe Premiere Pro", "creative"),
    "afterfx.exe": ("Adobe After Effects", "creative"),
    "figma.exe": ("Figma", "creative"),
    "blender.exe": ("Blender", "creative"),
    "acad.exe": ("AutoCAD", "creative"),
    "capcut.exe": ("剪映专业版", "creative"),
    "jianyingpro.exe": ("剪映专业版", "creative"),
    "postman.exe": ("Postman", "creative"),
    "apifox.exe": ("Apifox", "creative"),
    "navicat.exe": ("Navicat", "creative"),
    "dbeaver.exe": ("DBeaver", "creative"),
    "docker desktop.exe": ("Docker Desktop", "creative"),
    # 办公与效率 (productivity)
    "chrome.exe": ("Google Chrome", "productivity"),
    "msedge.exe": ("Microsoft Edge", "productivity"),
    "firefox.exe": ("Mozilla Firefox", "productivity"),
    "brave.exe": ("Brave", "productivity"),
    "arc.exe": ("Arc", "productivity"),
    "wps.exe": ("WPS Office", "productivity"),
    "wpp.exe": ("WPS 演示", "productivity"),
    "et.exe": ("WPS 表格", "productivity"),
    "winword.exe": ("Microsoft Word", "productivity"),
    "excel.exe": ("Microsoft Excel", "productivity"),
    "powerpnt.exe": ("Microsoft PowerPoint", "productivity"),
    "outlook.exe": ("Microsoft Outlook", "productivity"),
    "olk.exe": ("Microsoft Outlook", "productivity"),
    "onenote.exe": ("Microsoft OneNote", "productivity"),
    "notion.exe": ("Notion", "productivity"),
    "obsidian.exe": ("Obsidian", "productivity"),
    "typora.exe": ("Typora", "productivity"),
    "xmind.exe": ("XMind", "productivity"),
    "youdaonote.exe": ("有道云笔记", "productivity"),
    "ynote.exe": ("有道云笔记", "productivity"),
    "baidunetdisk.exe": ("百度网盘", "productivity"),
    "adrive.exe": ("阿里云盘", "productivity"),
    "aliyundrive.exe": ("阿里云盘", "productivity"),
    "quark.exe": ("夸克", "productivity"),
    "thunder.exe": ("迅雷", "productivity"),
    "explorer.exe": ("文件资源管理器", "productivity"),
    "notepad.exe": ("记事本", "productivity"),
    "notepad++.exe": ("Notepad++", "productivity"),
    "acrobat.exe": ("Adobe Acrobat", "productivity"),
    "acrord32.exe": ("Adobe Acrobat Reader", "productivity"),
    "sumatrapdf.exe": ("SumatraPDF", "productivity"),
    "everything.exe": ("Everything", "productivity"),
    "utools.exe": ("uTools", "productivity"),
    "snipaste.exe": ("Snipaste", "productivity"),
    "pixpin.exe": ("PixPin", "productivity"),
    "youdaodict.exe": ("有道词典", "productivity"),
    "eudic.exe": ("欧路词典", "productivity"),
    # 影音娱乐 (entertainment)
    "douyin.exe": ("抖音", "entertainment"),
    "hongguo.exe": ("红果短剧", "entertainment"),
    "hongguoduanju.exe": ("红果短剧", "entertainment"),
    "bilibili.exe": ("哔哩哔哩", "entertainment"),
    "哔哩哔哩.exe": ("哔哩哔哩", "entertainment"),
    "cloudmusic.exe": ("网易云音乐", "entertainment"),
    "qqmusic.exe": ("QQ音乐", "entertainment"),
    "kugou.exe": ("酷狗音乐", "entertainment"),
    "kwmusic.exe": ("酷我音乐", "entertainment"),
    "qishui.exe": ("汽水音乐", "entertainment"),
    "sodamusic.exe": ("汽水音乐", "entertainment"),
    "spotify.exe": ("Spotify", "entertainment"),
    "potplayermini64.exe": ("PotPlayer", "entertainment"),
    "potplayermini.exe": ("PotPlayer", "entertainment"),
    "potplayer.exe": ("PotPlayer", "entertainment"),
    "vlc.exe": ("VLC media player", "entertainment"),
    "mpv.exe": ("mpv", "entertainment"),
    "qyclient.exe": ("爱奇艺", "entertainment"),
    "iqiyi.exe": ("爱奇艺", "entertainment"),
    "qqlive.exe": ("腾讯视频", "entertainment"),
    "youkudesktop.exe": ("优酷", "entertainment"),
    "ikuyouku.exe": ("优酷", "entertainment"),
    "steam.exe": ("Steam", "entertainment"),
    "steamwebhelper.exe": ("Steam", "entertainment"),
    "epicgameslauncher.exe": ("Epic Games", "entertainment"),
    "wegame.exe": ("WeGame", "entertainment"),
    "yuanshen.exe": ("原神", "entertainment"),
    "genshinimpact.exe": ("原神", "entertainment"),
    "starrail.exe": ("崩坏：星穹铁道", "entertainment"),
    "leagueclient.exe": ("英雄联盟", "entertainment"),
    "leagueclientux.exe": ("英雄联盟", "entertainment"),
    "league of legends.exe": ("英雄联盟", "entertainment"),
    "valorant.exe": ("无畏契约", "entertainment"),
    "cs2.exe": ("Counter-Strike 2", "entertainment"),
    "dota2.exe": ("Dota 2", "entertainment"),
    "b2.exe": ("黑神话：悟空", "entertainment"),
}

_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "social",
        (
            "微信",
            "wechat",
            "qq",
            "tim",
            "钉钉",
            "dingtalk",
            "飞书",
            "feishu",
            "lark",
            "企业微信",
            "wxwork",
            "telegram",
            "discord",
            "slack",
            "teams",
            "会议",
            "zoom",
            "旺旺",
            "千牛",
        ),
    ),
    (
        "creative",
        (
            "visual studio",
            "vscode",
            "cursor",
            "windsurf",
            "intellij",
            "pycharm",
            "webstorm",
            "goland",
            "clion",
            "android studio",
            "photoshop",
            "illustrator",
            "premiere",
            "after effects",
            "figma",
            "blender",
            "autocad",
            "剪映",
            "capcut",
            "terminal",
            "powershell",
            "git",
            "postman",
            "apifox",
            "navicat",
            "dbeaver",
            "docker",
        ),
    ),
    (
        "entertainment",
        (
            "抖音",
            "douyin",
            "红果短剧",
            "hongguo",
            "哔哩哔哩",
            "bilibili",
            "网易云音乐",
            "cloudmusic",
            "qq音乐",
            "qqmusic",
            "酷狗",
            "kugou",
            "汽水音乐",
            "potplayer",
            "vlc",
            "爱奇艺",
            "iqiyi",
            "腾讯视频",
            "qqlive",
            "优酷",
            "youku",
            "steam",
            "epic games",
            "wegame",
            "原神",
            "genshin",
            "英雄联盟",
            "league of legends",
            "spotify",
            "music",
            "player",
            "game",
        ),
    ),
    (
        "productivity",
        (
            "chrome",
            "edge",
            "firefox",
            "brave",
            "arc",
            "wps",
            "word",
            "excel",
            "powerpoint",
            "outlook",
            "onenote",
            "notion",
            "obsidian",
            "typora",
            "xmind",
            "有道云笔记",
            "百度网盘",
            "阿里云盘",
            "文件资源管理器",
            "explorer",
            "notepad",
            "记事本",
            "acrobat",
            "pdf",
            "everything",
            "utools",
            "snipaste",
        ),
    ),
]

_ICON_CACHE: dict[str, str] = {}
_META_CACHE: dict[str, dict] = {}


def _normalize_exe_name(exe_name: str, exe_path: str = "") -> str:
    raw = (exe_name or "").strip()
    if not raw and exe_path:
        raw = os.path.basename(exe_path.replace("\\", "/"))
    if not raw:
        return "unknown.exe"
    return raw


def _lookup_catalog(exe_name: str) -> tuple[str, str] | None:
    lower = exe_name.strip().lower()
    if not lower:
        return None
    if lower in BUILTIN_APP_CATALOG:
        return BUILTIN_APP_CATALOG[lower]
    if not lower.endswith(".exe") and f"{lower}.exe" in BUILTIN_APP_CATALOG:
        return BUILTIN_APP_CATALOG[f"{lower}.exe"]
    return None


def classify_app(exe_name: str, display_name: str = "", exe_path: str = "") -> str:
    """根据内置词典与关键词规则将应用归类到 social/creative/entertainment/productivity/other。"""
    entry = _lookup_catalog(exe_name)
    if entry is not None:
        return entry[1]

    if exe_path:
        path_entry = _lookup_catalog(os.path.basename(exe_path.replace("\\", "/")))
        if path_entry is not None:
            return path_entry[1]

    haystack = f"{exe_name} {display_name} {exe_path}".lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in haystack:
                return category

    return "other"


def _read_win32_version_display_name(exe_path: str) -> str:
    """通过 win32api.GetFileVersionInfo 读取 FileDescription 或 ProductName。"""
    if not HAS_WIN32 or not exe_path or not os.path.isfile(exe_path):
        return ""

    try:
        translations = win32api.GetFileVersionInfo(
            exe_path, r"\VarFileInfo\Translation"
        )
    except Exception:
        translations = None

    codepages: list[tuple[int, int]] = []
    if translations:
        for lang, cp in translations:
            codepages.append((int(lang), int(cp)))
    # 常见中英文代码页兜底
    for fallback_pair in ((0x0804, 1200), (0x0409, 1200), (0x0409, 1252), (0x0000, 1200)):
        if fallback_pair not in codepages:
            codepages.append(fallback_pair)

    for prop_name in ("FileDescription", "ProductName"):
        for lang, cp in codepages:
            str_path = f"\\StringFileInfo\\{lang:04x}{cp:04x}\\{prop_name}"
            try:
                val = win32api.GetFileVersionInfo(exe_path, str_path)
            except Exception:
                continue
            if isinstance(val, str):
                cleaned = val.strip().rstrip("\x00").strip()
                if cleaned:
                    return cleaned
    return ""


def _build_svg_fallback_data_url(label: str, category: str = "other") -> str:
    """生成带软件首字母与柔和主题色的 SVG Data URL 兜底图标。"""
    clean_label = (label or "?").strip()
    first_char = clean_label[0].upper() if clean_label else "?"
    escaped_char = html.escape(first_char)
    color = CATEGORY_META.get(category, CATEGORY_META["other"])["color"]

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
        f'<rect width="48" height="48" rx="12" fill="{color}" fill-opacity="0.18"/>'
        f'<rect x="1" y="1" width="46" height="46" rx="11" fill="none" stroke="{color}" stroke-opacity="0.45" stroke-width="1.5"/>'
        f'<text x="50%" y="54%" dominant-baseline="middle" text-anchor="middle" '
        f'fill="{color}" font-family="system-ui, -apple-system, Microsoft YaHei, sans-serif" '
        f'font-size="22" font-weight="700">{escaped_char}</text>'
        "</svg>"
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def _hicon_to_png_data_url(hicon: int, size: int = 32) -> str | None:
    """将 Windows HICON 句柄渲染为 32x32/48x48 BGRA 缓冲并转换为透明 PNG Data URL。"""
    hdc_screen = 0
    hdc = None
    hbmp = None
    try:
        hdc_screen = win32gui.GetDC(0)
        hdc = win32ui.CreateDCFromHandle(hdc_screen)
        mem_dc = hdc.CreateCompatibleDC()
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, size, size)
        old_bmp = mem_dc.SelectObject(hbmp)
        try:
            win32gui.DrawIconEx(
                mem_dc.GetSafeHdc(),
                0,
                0,
                hicon,
                size,
                size,
                0,
                0,
                win32con.DI_NORMAL,
            )
            bmp_bytes = hbmp.GetBitmapBits(True)
        finally:
            mem_dc.SelectObject(old_bmp)
            mem_dc.DeleteDC()

        img = Image.frombuffer("RGBA", (size, size), bmp_bytes, "raw", "BGRA", 0, 1).copy()
        extrema = img.getextrema()
        # 如果 alpha 通道全为 0，检查 RGB 是否有非零像素（兼容无 alpha 通道的旧式 GDI 图标）
        if extrema[3][1] == 0:
            if any(ch[1] > 0 for ch in extrema[:3]):
                img.putalpha(255)
            else:
                return None

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None
    finally:
        if hbmp is not None:
            try:
                win32gui.DeleteObject(hbmp.GetHandle())
            except Exception:
                pass
        if hdc is not None:
            try:
                hdc.DeleteDC()
            except Exception:
                pass
        if hdc_screen:
            try:
                win32gui.ReleaseDC(0, hdc_screen)
            except Exception:
                pass


def extract_exe_icon_base64(
    exe_path: str,
    display_name: str = "",
    category: str = "other",
) -> str:
    """提取 EXE 图标为 Base64 Data URL；失败或文件不存在时返回 SVG 首字母兜底图标。"""
    norm_path = os.path.normpath(exe_path) if exe_path else ""
    fallback_label = display_name
    if not fallback_label:
        stem = Path(exe_path).stem if exe_path else "App"
        fallback_label = stem or "App"

    if category not in CATEGORY_META:
        category = classify_app(os.path.basename(exe_path or ""), fallback_label, exe_path or "")

    if not HAS_WIN32 or not norm_path or not os.path.isfile(norm_path):
        return _build_svg_fallback_data_url(fallback_label, category)

    cached = _ICON_CACHE.get(norm_path)
    if cached:
        return cached

    large_icons: list[int] = []
    small_icons: list[int] = []
    try:
        large_icons, small_icons = win32gui.ExtractIconEx(norm_path, 0, 1)
        hicon = 0
        if large_icons and large_icons[0]:
            hicon = int(large_icons[0])
        elif small_icons and small_icons[0]:
            hicon = int(small_icons[0])

        if hicon:
            png_url = _hicon_to_png_data_url(hicon, size=32)
            if png_url:
                _ICON_CACHE[norm_path] = png_url
                return png_url
    except Exception:
        pass
    finally:
        for h in list(large_icons) + list(small_icons):
            if h:
                try:
                    win32gui.DestroyIcon(h)
                except Exception:
                    pass

    return _build_svg_fallback_data_url(fallback_label, category)


def resolve_app_metadata(exe_path: str, exe_name: str | None = None) -> dict:
    """解析应用完整元数据：exe_path, exe_name, display_name, category, icon_base64。"""
    raw_path = (exe_path or "").strip()
    resolved_exe_name = _normalize_exe_name(exe_name or "", raw_path)

    cache_key = f"{raw_path.lower()}|{resolved_exe_name.lower()}"
    if cache_key in _META_CACHE:
        return dict(_META_CACHE[cache_key])

    catalog_entry = _lookup_catalog(resolved_exe_name)
    if catalog_entry is not None:
        display_name, category = catalog_entry
    else:
        win32_desc = _read_win32_version_display_name(raw_path)
        if win32_desc:
            display_name = win32_desc
        else:
            stem = Path(resolved_exe_name).stem
            display_name = stem if stem else resolved_exe_name
        category = classify_app(resolved_exe_name, display_name, raw_path)

    icon_base64 = extract_exe_icon_base64(
        raw_path,
        display_name=display_name,
        category=category,
    )

    result = {
        "exe_path": raw_path,
        "exe_name": resolved_exe_name,
        "display_name": display_name,
        "category": category,
        "icon_base64": icon_base64,
    }
    _META_CACHE[cache_key] = dict(result)
    return result
