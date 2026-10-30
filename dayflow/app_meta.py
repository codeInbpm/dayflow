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

# 常见主流浏览器进程名集合（小写）
BROWSER_EXE_NAMES: set[str] = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "360chrome.exe",
    "360se.exe",
    "qqbrowser.exe",
    "sogouexplorer.exe",
    "liebao.exe",
    "opera.exe",
    "vivaldi.exe",
    "safari.exe",
    "centbrowser.exe",
    "yandex.exe",
}

# 浏览器网页二级智能分类关键词规则
_BROWSER_CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    # 影音娱乐 (entertainment)
    (
        "entertainment",
        (
            "bilibili", "哔哩哔哩", "youtube", "优酷", "youku", "爱奇艺", "iqiyi",
            "腾讯视频", "v.qq.com", "netflix", "twitch", "抖音", "douyin",
            "小红书", "xiaohongshu", "快手", "kuaishou", "acfun", "spotify",
            "网易云音乐", "music.163.com", "qq音乐", "y.qq.com", "斗鱼", "douyu",
            "虎牙", "huya", "steam", "steamcommunity", "mgtv", "芒果tv",
            "biliplay", "cctv", "影视", "动漫", "番剧", "直播",
        ),
    ),
    # 社交通讯 (social)
    (
        "social",
        (
            "微博", "weibo", "贴吧", "tieba", "知乎", "zhihu", "twitter", "x.com",
            "x - ", "discord", "telegram", "即刻", "jike", "reddit", "v2ex",
            "whatsapp", "facebook", "instagram", "threads", "微信", "wechat",
            "豆瓣", "douban", "hupu", "虎扑", "nga", "coolapk", "酷安",
        ),
    ),
    # 开发与创意 (creative)
    (
        "creative",
        (
            "github", "gitlab", "gitee", "stack overflow", "stackoverflow", "掘金", "juejin",
            "csdn", "博客园", "cnblogs", "segmentfault", "思否", "leetcode", "力扣",
            "chatgpt", "openai", "claude", "anthropic", "hugging face", "huggingface",
            "cursor", "figma", "codepen", "codesandbox", "npm", "pypi", "kaggle",
            "v0.dev", "gemini", "deepseek", "开发者", "developer", "devtools",
            "developer tools", "runoob", "菜鸟教程", "w3schools", "mdn", "vuejs",
            "react", "angular", "python.org", "docker hub", "aws", "azure", "aliyun",
        ),
    ),
    # 办公与效率 (productivity)
    (
        "productivity",
        (
            "飞书", "feishu", "lark", "语雀", "yuque", "腾讯文档", "docs.qq.com",
            "notion", "google docs", "google sheets", "google drive", "gmail",
            "outlook", "office.com", "microsoft 365", "百度网盘", "pan.baidu",
            "夸克网盘", "quark", "115网盘", "onedrive", "腾讯企业邮", "网易企业邮",
            "confluence", "jira", "trello", "wolai", "flomo", "draw.io",
            "processon", "金山文档", "kdocs", "石墨文档", "shimo",
        ),
    ),
]


def resolve_browser_tab_category(exe_name: str | None, window_title: str | None) -> str | None:
    """根据浏览器进程名与窗口标题中的网页名称，二级细分该网页的实际分类。"""
    if not exe_name:
        return None
    norm_exe = exe_name.strip().lower()
    if norm_exe not in BROWSER_EXE_NAMES:
        return None
    if not window_title:
        return None

    title_lower = window_title.strip().lower()
    for cat, keywords in _BROWSER_CATEGORY_RULES:
        for kw in keywords:
            if kw in title_lower:
                return cat
    return None

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
    "tiktok.exe": ("TikTok", "entertainment"),
    "facebook.exe": ("Facebook", "social"),
    "instagram.exe": ("Instagram", "social"),
    "twitter.exe": ("Twitter", "social"),
    "x.exe": ("X", "social"),
    "threads.exe": ("Threads", "social"),
    "whatsapp.exe": ("WhatsApp", "social"),
    "hbuilder.exe": ("HBuilderX", "creative"),
    "hbuilderx.exe": ("HBuilderX", "creative"),
    "xterminal.exe": ("XTerminal", "creative"),
    "grok.exe": ("Grok", "creative"),
    "grok bot.exe": ("Grok Bot", "creative"),
    "workbuddy.exe": ("WorkBuddy", "productivity"),
    "sakurafrp.exe": ("SakuraFrp 启动器", "productivity"),
    "cc switch.exe": ("CC Switch", "productivity"),
    "ccswitch.exe": ("CC Switch", "productivity"),
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
            "facebook",
            "messenger",
            "instagram",
            "threads",
            "whatsapp",
            "twitter",
            "x - ",
            "微博",
            "weibo",
            "贴吧",
            "tieba",
            "知乎",
            "zhihu",
            "豆瓣",
            "douban",
            "line",
            "signal",
            "skype",
            "yy",
            "kook",
        ),
    ),
    (
        "creative",
        (
            "visual studio",
            "vscode",
            "code.exe",
            "cursor",
            "windsurf",
            "trae",
            "antigravity",
            "intellij",
            "idea",
            "pycharm",
            "webstorm",
            "goland",
            "clion",
            "rider",
            "datagrip",
            "android studio",
            "hbuilder",
            "xterminal",
            "terminal",
            "powershell",
            "pwsh",
            "cmd",
            "git",
            "github",
            "gitlab",
            "gitee",
            "postman",
            "apifox",
            "navicat",
            "dbeaver",
            "sqlyog",
            "docker",
            "grok",
            "chatgpt",
            "openai",
            "claude",
            "gemini",
            "deepseek",
            "copilot",
            "photoshop",
            "illustrator",
            "premiere",
            "after effects",
            "figma",
            "blender",
            "autocad",
            "剪映",
            "capcut",
            "devtools",
        ),
    ),
    (
        "entertainment",
        (
            "tiktok",
            "抖音",
            "douyin",
            "红果短剧",
            "hongguo",
            "哔哩哔哩",
            "bilibili",
            "youtube",
            "netflix",
            "twitch",
            "网易云音乐",
            "cloudmusic",
            "qq音乐",
            "qqmusic",
            "酷狗",
            "kugou",
            "酷我",
            "汽水音乐",
            "spotify",
            "potplayer",
            "vlc",
            "mpv",
            "爱奇艺",
            "iqiyi",
            "腾讯视频",
            "qqlive",
            "优酷",
            "youku",
            "芒果tv",
            "steam",
            "epic games",
            "wegame",
            "原神",
            "genshin",
            "英雄联盟",
            "league of legends",
            "music",
            "player",
            "game",
            "dota",
            "cs2",
            "valorant",
            "黑神话",
            "acfun",
            "快手",
            "kuaishou",
            "小红书",
            "xiaohongshu",
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
            "opera",
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
            "quark",
            "夸克",
            "迅雷",
            "thunder",
            "文件资源管理器",
            "explorer",
            "notepad",
            "记事本",
            "acrobat",
            "pdf",
            "everything",
            "utools",
            "snipaste",
            "pixpin",
            "workbuddy",
            "switch",
            "frp",
            "vpn",
            "v2ray",
            "clash",
            "nekoray",
        ),
    ),
]

_ICON_CACHE: dict[str, str] = {}
_META_CACHE: dict[str, dict] = {}

# 核心知名独立 Web / 桌面应用官方原版品牌矢量图标库
OFFICIAL_BRAND_SVG_ICONS: dict[str, str] = {
    "tiktok": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">'
        '<rect width="48" height="48" rx="10" fill="#010101"/>'
        '<path fill="#25F4EE" d="M29.5 10c1.2 2.8 3.5 4.8 6.5 5.2v4.8c-2.4 0-4.6-.8-6.5-2.2v11.7c0 5.8-4.7 10.5-10.5 10.5S8.5 35.3 8.5 29.5c0-5.4 4.1-9.9 9.4-10.4v5.1c-2.6.4-4.5 2.6-4.5 5.3 0 3 2.4 5.4 5.4 5.4s5.4-2.4 5.4-5.4V10h5.2z" opacity="0.95"/>'
        '<path fill="#FE2C55" d="M30.5 11c1.2 2.8 3.5 4.8 6.5 5.2v4.8c-2.4 0-4.6-.8-6.5-2.2v11.7c0 5.8-4.7 10.5-10.5 10.5S9.5 36.3 9.5 30.5c0-5.4 4.1-9.9 9.4-10.4v5.1c-2.6.4-4.5 2.6-4.5 5.3 0 3 2.4 5.4 5.4 5.4s5.4-2.4 5.4-5.4V11h5.2z" opacity="0.95"/>'
        '<path fill="#FFFFFF" d="M30 10.5c1.2 2.8 3.5 4.8 6.5 5.2v4.8c-2.4 0-4.6-.8-6.5-2.2v11.7c0 5.8-4.7 10.5-10.5 10.5S9 35.8 9 30c0-5.4 4.1-9.9 9.4-10.4v5.1c-2.6.4-4.5 2.6-4.5 5.3 0 3 2.4 5.4 5.4 5.4s5.4-2.4 5.4-5.4V10.5H30z"/>'
        '</svg>'
    ),
    "facebook": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">'
        '<rect width="48" height="48" rx="10" fill="#1877F2"/>'
        '<path fill="#FFFFFF" d="M31.2 26.5l.9-6.1h-5.8v-4c0-1.7.8-3.3 3.4-3.3h2.6V7.9s-2.4-.4-4.7-.4c-4.8 0-8 2.9-8 8.2v4.7h-5.4v6.1h5.4V41c1.1.2 2.2.3 3.3.3 1.1 0 2.2-.1 3.3-.3V26.5h4.7z"/>'
        '</svg>'
    ),
    "youtube": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">'
        '<rect width="48" height="48" rx="10" fill="#FF0000"/>'
        '<path fill="#FFFFFF" d="M20 16l12 8-12 8V16z"/>'
        '</svg>'
    ),
    "twitter": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">'
        '<rect width="48" height="48" rx="10" fill="#000000"/>'
        '<path fill="#FFFFFF" d="M28.4 12h3.4l-7.4 8.5 8.7 11.5h-6.8l-5.3-7-6.1 7H11.5l7.9-9.1L11 12h7l4.8 6.4L28.4 12zm-1.2 18h1.9L17.2 13.9h-2L27.2 30z"/>'
        '</svg>'
    ),
    "x": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">'
        '<rect width="48" height="48" rx="10" fill="#000000"/>'
        '<path fill="#FFFFFF" d="M28.4 12h3.4l-7.4 8.5 8.7 11.5h-6.8l-5.3-7-6.1 7H11.5l7.9-9.1L11 12h7l4.8 6.4L28.4 12zm-1.2 18h1.9L17.2 13.9h-2L27.2 30z"/>'
        '</svg>'
    ),
    "instagram": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">'
        '<defs><radialGradient id="ig" cx="20%" cy="100%" r="120%"><stop offset="0%" stop-color="#FFDD55"/><stop offset="25%" stop-color="#FF5D3B"/><stop offset="50%" stop-color="#FF0069"/><stop offset="75%" stop-color="#D300C5"/><stop offset="100%" stop-color="#7638FA"/></radialGradient></defs>'
        '<rect width="48" height="48" rx="10" fill="url(#ig)"/>'
        '<path fill="none" stroke="#FFFFFF" stroke-width="3" d="M16 11h16a5 5 0 0 1 5 5v16a5 5 0 0 1-5 5H16a5 5 0 0 1-5-5V16a5 5 0 0 1 5-5z"/>'
        '<circle cx="24" cy="24" r="6" fill="none" stroke="#FFFFFF" stroke-width="3"/>'
        '<circle cx="32" cy="16" r="1.5" fill="#FFFFFF"/>'
        '</svg>'
    ),
    "github": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">'
        '<rect width="48" height="48" rx="10" fill="#24292F"/>'
        '<path fill="#FFFFFF" d="M24 8C15.2 8 8 15.2 8 24c0 7.1 4.6 13.1 11 15.2.8.1 1.1-.3 1.1-.8v-2.8c-4.5 1-5.4-2.2-5.4-2.2-.7-1.8-1.8-2.3-1.8-2.3-1.5-1 .1-1 .1-1 1.6.1 2.5 1.7 2.5 1.7 1.4 2.5 3.8 1.8 4.7 1.4.1-1.1.6-1.8 1-2.2-3.6-.4-7.3-1.8-7.3-8 0-1.8.6-3.2 1.7-4.3-.2-.4-.7-2.1.2-4.3 0 0 1.4-.4 4.5 1.7 1.3-.4 2.7-.5 4.1-.5s2.8.2 4.1.5c3.1-2.1 4.5-1.7 4.5-1.7.9 2.2.4 3.9.2 4.3 1.1 1.1 1.7 2.5 1.7 4.3 0 6.2-3.8 7.6-7.4 8 .6.5 1.1 1.5 1.1 3v4.4c0 .5.3.9 1.1.8C35.4 37.1 40 31.1 40 24c0-8.8-7.2-16-16-16z"/>'
        '</svg>'
    ),
}


def get_official_brand_icon_base64(name: str | None) -> str | None:
    """根据应用名称或别名，获取官方原版 100% 精确的彩色矢量 Logo Data URL。"""
    if not name:
        return None
    key = name.strip().lower()
    if key in OFFICIAL_BRAND_SVG_ICONS:
        svg = OFFICIAL_BRAND_SVG_ICONS[key]
        b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{b64}"
    stem = Path(key).stem.lower()
    if stem in OFFICIAL_BRAND_SVG_ICONS:
        svg = OFFICIAL_BRAND_SVG_ICONS[stem]
        b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{b64}"
    return None


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


def extract_window_icon_base64(hwnd: int) -> str | None:
    """直接从运行中的前台窗口句柄 (HWND) 提取真实运行图标（兼容 PWA 及动态窗口）。"""
    if not HAS_WIN32 or not hwnd or hwnd <= 0:
        return None
    try:
        # 1. 尝试 WM_GETICON (ICON_BIG, ICON_SMALL2, ICON_SMALL)
        for icon_type in (win32con.ICON_BIG, 2, win32con.ICON_SMALL):
            try:
                res, hicon = win32gui.SendMessageTimeout(
                    hwnd,
                    win32con.WM_GETICON,
                    icon_type,
                    0,
                    win32con.SMTO_ABORTIFHUNG,
                    150,
                )
                if res and hicon:
                    data_url = _hicon_to_png_data_url(int(hicon), size=32)
                    if data_url:
                        return data_url
            except Exception:
                pass

        # 2. 尝试 GetClassLong (GCL_HICON, GCL_HICONSM)
        for flag in (win32con.GCL_HICON, getattr(win32con, "GCL_HICONSM", -34)):
            try:
                hicon = win32gui.GetClassLong(hwnd, flag)
                if hicon:
                    data_url = _hicon_to_png_data_url(int(hicon), size=32)
                    if data_url:
                        return data_url
            except Exception:
                pass
    except Exception:
        pass
    return None


_BROWSER_SUFFIXES = (
    " - google chrome",
    " - chrome",
    " - microsoft edge",
    " - microsoft​ edge",
    " - edge",
    " — mozilla firefox",
    " - mozilla firefox",
    " - firefox",
    " - brave",
    " - vivaldi",
    " - 360安全浏览器",
    " - 360极速浏览器",
    " - qq浏览器",
    " - 搜狗高速浏览器",
)

# 常见独立本地 PWA / Web 桌面应用别名映射表（小写关键词 -> 友好官方名称与分类）
KNOWN_PWA_APPS: list[tuple[str, str, str]] = [
    ("facebook", "Facebook", "social"),
    ("tiktok", "TikTok", "entertainment"),
    ("youtube", "YouTube", "entertainment"),
    ("instagram", "Instagram", "social"),
    ("threads", "Threads", "social"),
    ("twitter", "X", "social"),
    ("x.com", "X", "social"),
    ("reddit", "Reddit", "social"),
    ("whatsapp", "WhatsApp", "social"),
    ("telegram", "Telegram", "social"),
    ("discord", "Discord", "social"),
    ("slack", "Slack", "social"),
    ("notion", "Notion", "productivity"),
    ("figma", "Figma", "creative"),
    ("canva", "Canva", "creative"),
    ("chatgpt", "ChatGPT", "creative"),
    ("claude", "Claude", "creative"),
    ("github", "GitHub", "creative"),
    ("bilibili", "哔哩哔哩", "entertainment"),
    ("spotify", "Spotify", "entertainment"),
    ("netflix", "Netflix", "entertainment"),
]


def clean_standalone_title(title: str) -> str:
    """从独立窗口标题中提取出核心应用品牌/名称。"""
    t = (title or "").strip()
    if not t:
        return ""
    t_lower = t.lower()
    for kw, friendly, _ in KNOWN_PWA_APPS:
        if kw in t_lower:
            return friendly

    # 通用截取：例如 "TikTok - Make Your Day" -> "TikTok"
    for sep in (" - ", " — ", " | ", " · "):
        if sep in t:
            parts = [p.strip() for p in t.split(sep) if p.strip()]
            if parts:
                return parts[0]
    return t


def inspect_pwa_or_standalone_app(
    exe_name: str | None,
    window_title: str | None,
    window_class: str | None = None,
    pid: int | None = None,
) -> tuple[bool, str, str, str, str]:
    """
    检查前台窗口是否为由浏览器等宿主承载的独立本地 PWA / Web App 应用。
    返回 (is_pwa, display_name, exe_name, exe_path, category)
    """
    if not exe_name:
        return False, "", "", "", ""
    norm_exe = exe_name.strip().lower()
    is_browser_host = (norm_exe in BROWSER_EXE_NAMES) or (norm_exe in ("msedge_proxy.exe", "chrome_proxy.exe"))
    if not is_browser_host:
        return False, "", "", "", ""

    title = (window_title or "").strip()
    if not title:
        return False, "", "", "", ""

    title_lower = title.lower()
    has_browser_suffix = any(title_lower.endswith(sfx) or sfx in title_lower for sfx in _BROWSER_SUFFIXES)

    is_app_mode = False
    if pid and pid > 0:
        try:
            import psutil
            proc = psutil.Process(pid)
            cmdline = proc.cmdline()
            for arg in cmdline:
                if arg.startswith("--app-id=") or arg.startswith("--app="):
                    is_app_mode = True
                    break
        except Exception:
            pass

    # 判定为独立应用：
    # 1. 明确带有 --app-id 或 --app 命令行参数（Chrome/Edge PWA 核心特征）
    if is_app_mode:
        for kw, friendly, cat in KNOWN_PWA_APPS:
            if kw in title_lower:
                return True, friendly, f"{friendly}.exe", f"PWA:{friendly}", cat
        cleaned = clean_standalone_title(title)
        if cleaned and len(cleaned) <= 30 and cleaned.lower() not in ("new tab", "about:blank"):
            cat = classify_app(cleaned, cleaned, "")
            return True, cleaned, f"{cleaned}.exe", f"PWA:{cleaned}", cat

    # 2. 或者完全不包含浏览器宿主后缀（如 " - Google Chrome", " - Chrome" 等），
    #    且标题明确以独立桌面应用名开头或完全等于独立应用名（如 "Facebook", "Facebook - 登录或注册", "TikTok", "TikTok - Make Your Day"）
    if not has_browser_suffix and (window_class == "Chrome_WidgetWin_1" or not window_class):
        for kw, friendly, cat in KNOWN_PWA_APPS:
            if title_lower == kw or title_lower.startswith(f"{kw} ") or title_lower.startswith(f"{kw}-") or title_lower.startswith(f"{kw} -"):
                return True, friendly, f"{friendly}.exe", f"PWA:{friendly}", cat

    return False, "", "", "", ""


def resolve_app_metadata(
    exe_path: str,
    exe_name: str | None = None,
    window_title: str | None = None,
    hwnd: int | None = None,
    override_display_name: str | None = None,
    override_category: str | None = None,
) -> dict:
    """解析应用完整元数据：exe_path, exe_name, display_name, category, icon_base64。"""
    raw_path = (exe_path or "").strip()
    resolved_exe_name = _normalize_exe_name(exe_name or "", raw_path)

    cache_key = f"{raw_path.lower()}|{resolved_exe_name.lower()}"
    if not hwnd and not override_display_name and cache_key in _META_CACHE:
        return dict(_META_CACHE[cache_key])

    if override_display_name:
        display_name = override_display_name
        category = override_category or classify_app(resolved_exe_name, display_name, raw_path)
    else:
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
            haystack = f"{display_name} {window_title or ''}".strip()
            category = classify_app(resolved_exe_name, haystack, raw_path)

    icon_base64 = ""
    # 1. 优先检查官方原版品牌矢量 Logo（如 TikTok, Facebook, YouTube 等），绝对保证图案 100% 真实纯正！
    official_icon = get_official_brand_icon_base64(display_name) or get_official_brand_icon_base64(resolved_exe_name)
    if official_icon:
        icon_base64 = official_icon

    # 2. 其次若未匹配官方矢量且有运行中前台 HWND，尝试从运行时窗口抓取图标
    if not icon_base64 and hwnd and hwnd > 0:
        icon_base64 = extract_window_icon_base64(hwnd) or ""

    # 3. 再次从 EXE 本地提取或 SVG 兜底
    if not icon_base64:
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
