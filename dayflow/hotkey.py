from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import threading
from typing import Callable

# Win32 热键修饰键常量
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

# 常见键映射
VK_MAP: dict[str, int] = {
    "F1": 0x70,
    "F2": 0x71,
    "F3": 0x72,
    "F4": 0x73,
    "F5": 0x74,
    "F6": 0x75,
    "F7": 0x76,
    "F8": 0x77,
    "F9": 0x78,
    "F10": 0x79,
    "F11": 0x7A,
    "F12": 0x7B,
    "SPACE": 0x20,
    "TAB": 0x09,
    "GRAVE": 0xC0,  # ` ~
    "`": 0xC0,
}


def parse_hotkey_string(hotkey_str: str) -> tuple[int, int] | None:
    """解析如 'Ctrl+Shift+D', 'Alt+D', 'Ctrl+Alt+D' 为 (modifiers, vk_code)。"""
    if not hotkey_str or not hotkey_str.strip():
        return None

    parts = [p.strip().upper() for p in hotkey_str.split("+") if p.strip()]
    if not parts:
        return None

    modifiers = MOD_NOREPEAT
    key_part = ""

    for p in parts:
        if p in ("CTRL", "CONTROL"):
            modifiers |= MOD_CONTROL
        elif p == "ALT":
            modifiers |= MOD_ALT
        elif p == "SHIFT":
            modifiers |= MOD_SHIFT
        elif p in ("WIN", "WINDOWS", "SUPER"):
            modifiers |= MOD_WIN
        else:
            key_part = p

    if not key_part:
        return None

    if key_part in VK_MAP:
        vk = VK_MAP[key_part]
    elif len(key_part) == 1 and (key_part.isalnum() or key_part in "`~"):
        vk = ord(key_part[0])
    else:
        return None

    return modifiers, vk


class GlobalHotkeyManager:
    """Windows 全局快捷键注册与监听管理器，运行于独立消息循环线程。"""

    def __init__(self, on_trigger: Callable[[], object] | None = None) -> None:
        self._on_trigger = on_trigger
        self._current_hotkey_str: str = "Ctrl+Shift+D"
        self._enabled: bool = True
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._running: bool = False
        self._hotkey_id: int = 1001

    def set_on_trigger(self, callback: Callable[[], object] | None) -> None:
        self._on_trigger = callback

    def update_hotkey(self, hotkey_str: str, enabled: bool = True) -> bool:
        """更新当前监听的全局快捷键及启用状态，并热重载生效。"""
        with self._lock:
            self._current_hotkey_str = hotkey_str.strip()
            self._enabled = bool(enabled)
            self._restart_worker()
            return True

    def start(self, hotkey_str: str = "Ctrl+Shift+D", enabled: bool = True) -> None:
        """启动后台热键监听消息循环。"""
        with self._lock:
            self._current_hotkey_str = hotkey_str.strip()
            self._enabled = bool(enabled)
            self._restart_worker()

    def stop(self) -> None:
        """停止并解除全局热键注册。"""
        with self._lock:
            self._running = False
            if self._thread_id and os.name == "nt":
                try:
                    ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
                except Exception:
                    pass
            self._thread_id = None
            self._thread = None

    def _restart_worker(self) -> None:
        if self._thread_id and os.name == "nt":
            try:
                ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
            self._thread_id = None

        if not self._enabled or not self._current_hotkey_str or os.name != "nt":
            return

        parsed = parse_hotkey_string(self._current_hotkey_str)
        if not parsed:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._msg_loop,
            args=(parsed[0], parsed[1]),
            name="DayflowGlobalHotkeyThread",
            daemon=True,
        )
        self._thread.start()

    def _msg_loop(self, modifiers: int, vk: int) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = int(kernel32.GetCurrentThreadId())

        # 尝试向当前线程注册热键 (hWnd=None)
        registered = user32.RegisterHotKey(None, self._hotkey_id, modifiers, vk)
        if not registered:
            return

        try:
            msg = wintypes.MSG()
            while self._running:
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res in (0, -1):
                    break
                if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                    if self._on_trigger is not None:
                        try:
                            self._on_trigger()
                        except Exception:
                            pass
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            try:
                user32.UnregisterHotKey(None, self._hotkey_id)
            except Exception:
                pass
