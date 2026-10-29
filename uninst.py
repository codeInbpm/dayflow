from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

RUN_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_REG_NAME = "Dayflow"

MB_YESNO = 0x00000004
MB_ICONQUESTION = 0x00000020
MB_ICONINFORMATION = 0x00000040
MB_TOPMOST = 0x00040000
IDYES = 6


def get_install_dir() -> Path:
    """获取当前卸载程序所在的安装目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def remove_auto_start_registry() -> bool:
    """移除 Windows 注册表中的 Dayflow 开机自启项。"""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_REG_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            try:
                winreg.DeleteValue(key, RUN_REG_NAME)
                return True
            except FileNotFoundError:
                return False
    except Exception:
        return False


def stop_running_dayflow() -> None:
    """终止正在运行的 Dayflow.exe 进程，释放数据库与可执行文件锁。"""
    if sys.platform != "win32":
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "Dayflow.exe", "/T"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            timeout=5,
        )
    except Exception:
        pass


def remove_path_with_retry(target: Path, retries: int = 8, delay: float = 0.25) -> bool:
    """带重试地删除文件或文件夹（等待刚退出的进程完全释放文件句柄）。"""
    for _ in range(retries):
        if not target.exists():
            return True
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            if not target.exists():
                return True
        except Exception:
            time.sleep(delay)
    return not target.exists()


def perform_uninstall_cleanup(
    install_dir: Path,
    local_appdata_dir: Path | None = None,
    stop_process: bool = True,
    clean_registry: bool = True,
) -> dict[str, bool]:
    """执行卸载清理：结束进程、清理开机自启注册表、删除本地数据库及主程序文件。"""
    if stop_process:
        stop_running_dayflow()
        time.sleep(0.35)

    reg_cleaned = remove_auto_start_registry() if clean_registry else False

    # 1. 清除同级目录下的 data/ 数据库文件夹（包含 dayflow.db, -wal, -shm 等所有使用记录）
    data_dir = install_dir / "data"
    data_removed = remove_path_with_retry(data_dir)

    # 2. 清除 %LOCALAPPDATA%/Dayflow 下的回退数据目录（如有）
    if local_appdata_dir is None:
        env_local = os.environ.get("LOCALAPPDATA")
        if env_local:
            local_appdata_dir = Path(env_local) / "Dayflow"

    appdata_removed = True
    if local_appdata_dir and local_appdata_dir.exists():
        appdata_removed = remove_path_with_retry(local_appdata_dir)

    # 3. 删除主程序 Dayflow.exe 与说明文档
    exe_removed = remove_path_with_retry(install_dir / "Dayflow.exe")
    readme_removed = remove_path_with_retry(install_dir / "使用说明.txt")

    return {
        "registry_cleaned": reg_cleaned,
        "data_removed": data_removed,
        "appdata_removed": appdata_removed,
        "exe_removed": exe_removed,
        "readme_removed": readme_removed,
    }


def schedule_self_delete(uninst_exe_path: Path) -> None:
    """在当前进程退出后异步删除 uninst.exe 自身，并在安装目录为空时清理空目录。"""
    if sys.platform != "win32" or not uninst_exe_path.is_file():
        return
    parent_dir = uninst_exe_path.parent
    # 延迟约 1 秒等待 uninst.exe 退出后删除自身；若父文件夹已空则顺带移除空壳目录
    cmd_line = (
        f'ping 127.0.0.1 -n 2 > nul & '
        f'del /f /q "{uninst_exe_path}" > nul 2>&1 & '
        f'rmdir "{parent_dir}" > nul 2>&1'
    )
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", cmd_line],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            close_fds=True,
        )
    except Exception:
        pass


def show_confirm_dialog() -> bool:
    """弹出原生 Windows 确认卸载对话框。"""
    if sys.platform != "win32":
        return True
    title = "卸载 Dayflow (Uninstall Dayflow)"
    message = (
        "确定要彻底卸载 Dayflow 桌面时长管家并清除所有本地数据吗？\n\n"
        "此操作将：\n"
        "1. 自动关闭正在运行的 Dayflow 程序；\n"
        "2. 清除开机自动启动设置；\n"
        "3. 彻底删除所有软件使用时长记录 (data 文件夹)；\n"
        "4. 移除 Dayflow.exe 及卸载程序自身。\n\n"
        "Are you sure you want to completely uninstall Dayflow and erase all usage data?"
    )
    res = ctypes.windll.user32.MessageBoxW(
        0,
        message,
        title,
        MB_YESNO | MB_ICONQUESTION | MB_TOPMOST,
    )
    return res == IDYES


def show_complete_dialog() -> None:
    """弹出原生 Windows 卸载完成提示框。"""
    if sys.platform != "win32":
        return
    title = "卸载完成 (Uninstalled)"
    message = (
        "Dayflow 及所有本地统计数据已彻底清除并完成卸载。\n\n"
        "Dayflow and all local usage data have been completely removed."
    )
    ctypes.windll.user32.MessageBoxW(
        0,
        message,
        title,
        MB_ICONINFORMATION | MB_TOPMOST,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dayflow 卸载与数据清理工具")
    parser.add_argument(
        "--yes",
        "-y",
        "--silent",
        action="store_true",
        dest="silent",
        help="静默确认卸载并清除所有数据",
    )
    parser.add_argument(
        "--target-dir",
        default="",
        help="指定要清理的安装目录（默认当前 uninst.exe 所在目录）",
    )
    args, _ = parser.parse_known_args(argv)

    if not args.silent:
        if not show_confirm_dialog():
            return 0

    install_dir = Path(args.target_dir).resolve() if args.target_dir else get_install_dir()
    perform_uninstall_cleanup(install_dir=install_dir)

    if not args.silent:
        show_complete_dialog()

    # 若当前是从打包后的 uninst.exe 启动，则在退出前触发自删除脚本
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        if exe_path.name.lower() == "uninst.exe":
            schedule_self_delete(exe_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
