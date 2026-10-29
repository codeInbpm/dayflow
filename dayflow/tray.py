from __future__ import annotations

import threading
from typing import Callable

from PIL import Image, ImageDraw

try:
    import pystray

    HAS_PYSTRAY = True
except ImportError:  # pragma: no cover
    pystray = None  # type: ignore[assignment]
    HAS_PYSTRAY = False


def create_tray_icon_image(size: int = 64) -> Image.Image:
    """使用 Pillow 动态生成高清深色圆角彩色柱状图图标。"""
    scale = 2
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 深色圆角底座 (#18181B) 与微光边框
    pad = int(canvas_size * 0.06)
    radius = int(canvas_size * 0.24)
    draw.rounded_rectangle(
        [pad, pad, canvas_size - pad - 1, canvas_size - pad - 1],
        radius=radius,
        fill=(24, 24, 27, 255),
        outline=(63, 63, 70, 255),
        width=max(2, scale),
    )

    # 四根彩色圆角柱子（蓝、青、绿、橙）
    bars = [
        ((59, 130, 246, 255), 0.45),   # 社交通讯蓝 #3B82F6
        ((6, 182, 212, 255), 0.78),    # 开发与创意青 #06B6D4
        ((16, 185, 129, 255), 0.60),   # 办公与效率绿 #10B981
        ((245, 158, 11, 255), 0.90),   # 影音娱乐橙 #F59E0B
    ]

    inner_left = int(canvas_size * 0.20)
    inner_right = int(canvas_size * 0.80)
    bottom_y = int(canvas_size * 0.78)
    max_bar_h = int(canvas_size * 0.54)

    total_w = inner_right - inner_left
    bar_count = len(bars)
    gap = int(total_w * 0.08)
    bar_w = max(4, (total_w - gap * (bar_count - 1)) // bar_count)

    for idx, (color, ratio) in enumerate(bars):
        x0 = inner_left + idx * (bar_w + gap)
        x1 = x0 + bar_w
        bar_h = max(int(bar_w), int(max_bar_h * ratio))
        y0 = bottom_y - bar_h
        y1 = bottom_y
        draw.rounded_rectangle(
            [x0, y0, x1, y1],
            radius=max(2, bar_w // 2),
            fill=color,
        )

    return img.resize((size, size), Image.Resampling.LANCZOS)


def ask_quit_confirmation(parent_hwnd: int = 0, lang: str = "zh-CN") -> bool:
    """在用户右键退出或关闭应用前，弹出 Windows 原生模态确认提示框。

    返回 True 表示用户确认退出；返回 False 表示用户取消退出。
    """
    import os
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("DAYFLOW_NO_PROMPT"):
        return True

    try:
        import ctypes

        MB_YESNO = 0x00000004
        MB_ICONQUESTION = 0x00000020
        MB_TOPMOST = 0x00040000
        MB_SETFOREGROUND = 0x00010000
        MB_DEFBUTTON2 = 0x00000100  # 默认焦点在“否”上，防止误回车直接关闭
        IDYES = 6

        norm_lang = str(lang or "zh-CN").lower()
        if "en" in norm_lang:
            title = "Dayflow - Exit Confirmation"
            message = "Are you sure you want to exit Dayflow?\n\nTracking your screen time will be paused."
        elif "tw" in norm_lang or "hk" in norm_lang:
            title = "Dayflow - 退出確認"
            message = "確定要結束並退出 Dayflow 嗎？\n\n退出後將暫停記錄桌面應用使用時長。"
        else:
            title = "Dayflow - 退出确认"
            message = "确定要退出 Dayflow 吗？\n\n退出后将暂停记录桌面应用使用时长。"

        hwnd = int(parent_hwnd) if parent_hwnd else 0
        res = ctypes.windll.user32.MessageBoxW(
            hwnd,
            message,
            title,
            MB_YESNO | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND | MB_DEFBUTTON2,
        )
        return res == IDYES
    except Exception:
        return True


class TrayController:
    """Windows 系统托盘控制器，支持面板唤醒、置顶切换与退出应用。"""

    def __init__(
        self,
        on_show: Callable[[], object] | None = None,
        on_toggle_top: Callable[[], object] | None = None,
        is_on_top: Callable[[], bool] | None = None,
        on_quit: Callable[[], object] | None = None,
        confirm_quit: Callable[[], bool] | None = None,
    ) -> None:
        self._on_show = on_show
        self._on_toggle_top = on_toggle_top
        self._is_on_top = is_on_top or (lambda: False)
        self._on_quit = on_quit
        self._confirm_quit = confirm_quit
        self._icon: object | None = None
        self._thread: threading.Thread | None = None

    def _handle_show(self, icon: object = None, item: object = None) -> None:
        if self._on_show is not None:
            try:
                self._on_show()
            except Exception:
                pass

    def _handle_toggle_top(self, icon: object = None, item: object = None) -> None:
        if self._on_toggle_top is not None:
            try:
                self._on_toggle_top()
            except Exception:
                pass

    def _handle_quit(self, icon: object = None, item: object = None) -> None:
        if self._confirm_quit is not None:
            try:
                if not self._confirm_quit():
                    return
            except Exception:
                pass
        elif not ask_quit_confirmation():
            return

        self.stop()
        if self._on_quit is not None:
            try:
                self._on_quit()
            except Exception:
                pass

    def _build_icon(self) -> object | None:
        if not HAS_PYSTRAY or pystray is None:
            return None

        menu = pystray.Menu(
            pystray.MenuItem(
                "打开 Dayflow 统计面板",
                self._handle_show,
                default=True,
            ),
            pystray.MenuItem(
                "窗口置顶",
                self._handle_toggle_top,
                checked=lambda _item: bool(self._is_on_top()),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "退出 Dayflow",
                self._handle_quit,
            ),
        )
        return pystray.Icon(
            "dayflow",
            create_tray_icon_image(64),
            "Dayflow - 桌面使用时间统计",
            menu,
        )

    def start(self) -> None:
        """在后台守护线程中启动系统托盘图标。"""
        if not HAS_PYSTRAY:
            return
        if self._thread is not None and self._thread.is_alive():
            return

        self._icon = self._build_icon()
        if self._icon is None:
            return

        self._thread = threading.Thread(
            target=self._icon.run,  # type: ignore[attr-defined]
            name="DayflowSystemTray",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """停止并移除系统托盘图标。"""
        icon = self._icon
        self._icon = None
        if icon is not None:
            try:
                icon.stop()  # type: ignore[attr-defined]
            except Exception:
                pass

    def notify(self, title: str, message: str) -> bool:
        """向 Windows 系统托盘/操作中心发送系统级原生通知。"""
        if self._icon is not None:
            try:
                self._icon.notify(message, title)  # type: ignore[attr-defined]
                return True
            except Exception:
                pass
        return False
