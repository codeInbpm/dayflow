from __future__ import annotations

import dis
import sys
from pathlib import Path

# 修复 Python 3.10.0 标准库 dis._get_const_info 在处理 EXTENDED_ARG 字节码时的越界 Bug (bpo-45757)
_orig_get_const_info = dis._get_const_info


def _safe_get_const_info(const_index: int, const_list: tuple | list | None):
    try:
        return _orig_get_const_info(const_index, const_list)
    except IndexError:
        return const_index, repr(const_index)


dis._get_const_info = _safe_get_const_info


def main() -> int:
    root_dir = Path(__file__).resolve().parent.parent
    icon_path = root_dir / "assets" / "dayflow.ico"
    icon_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. 生成多尺寸高清 ICO 图标
    sys.path.insert(0, str(root_dir))
    from dayflow.tray import create_tray_icon_image

    img = create_tray_icon_image(256)
    img.save(
        icon_path,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"[Dayflow Build] Icon ready: {icon_path}")

    # 2. 调用 PyInstaller 打包独立单文件 Dayflow.exe
    import PyInstaller.__main__

    dist_frontend = root_dir / "frontend" / "dist"
    if not (dist_frontend / "index.html").is_file():
        print(f"[ERROR] Missing frontend build at {dist_frontend}", file=sys.stderr)
        return 1

    args = [
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=Dayflow",
        f"--icon={icon_path}",
        f"--add-data={dist_frontend};frontend/dist",
        f"--add-data={icon_path};assets",
        "--hidden-import=win32com",
        "--hidden-import=win32com.client",
        "--exclude-module=pytest",
        "--exclude-module=unittest",
        f"--distpath={root_dir / 'release'}",
        f"--workpath={root_dir / 'build' / 'pyinstaller'}",
        f"--specpath={root_dir / 'build'}",
        str(root_dir / "main.py"),
    ]
    PyInstaller.__main__.run(args)
    exe_file = root_dir / "release" / "Dayflow.exe"

    # 3. 调用 PyInstaller 打包轻量级卸载程序 uninst.exe（双击一键卸载程序并彻底清除本地数据）
    uninst_args = [
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=uninst",
        f"--icon={icon_path}",
        "--exclude-module=webview",
        "--exclude-module=PIL",
        "--exclude-module=psutil",
        "--exclude-module=pystray",
        "--exclude-module=sqlite3",
        "--exclude-module=clr",
        "--exclude-module=pythonnet",
        "--exclude-module=pytest",
        "--exclude-module=unittest",
        f"--distpath={root_dir / 'release'}",
        f"--workpath={root_dir / 'build' / 'pyinstaller_uninst'}",
        f"--specpath={root_dir / 'build'}",
        str(root_dir / "uninst.py"),
    ]
    PyInstaller.__main__.run(uninst_args)
    uninst_file = root_dir / "release" / "uninst.exe"

    if exe_file.is_file() and uninst_file.is_file():
        size_mb = exe_file.stat().st_size / (1024 * 1024)
        uninst_mb = uninst_file.stat().st_size / (1024 * 1024)
        print(f"\n[Dayflow Build] SUCCESS! Standalone executables created:")
        print(f"  -> {exe_file} ({size_mb:.2f} MB)")
        print(f"  -> {uninst_file} ({uninst_mb:.2f} MB)")

        # 4. 自动生成便于微信/QQ直接分享的 ZIP 发行包（包含 Dayflow.exe、uninst.exe、使用说明.txt）
        import zipfile

        readme_text = (
            "Dayflow 桌面时长管家 (v1.0.1 - Windows 绿色免安装版)\n"
            "==================================================\n\n"
            "【使用方法】\n"
            "1. 将本压缩包解压到任意文件夹（建议放在 D 盘或常用软件目录）；\n"
            "2. 直接双击运行 Dayflow.exe 即可开始自动记录桌面软件使用时长；\n"
            "3. 所有统计数据均保存在同级自动生成的 data\\dayflow.db 本地数据库中，100% 本地隐私存储；\n"
            "4. 点击右上角齿轮【设置】可切换深色/浅色模式、调节字体大小、切换语言、开启开机自启或配置挂机与久坐健康提醒；\n"
            "5. 【彻底卸载】如需卸载本软件，直接双击同级目录下的 uninst.exe，即可一键关闭程序、清除开机自启项、彻底删除 data 数据文件夹及主程序。\n"
        )
        readme_path = root_dir / "release" / "使用说明.txt"
        readme_path.write_text(readme_text, encoding="utf-8")

        zip_path = root_dir / "release" / "Dayflow-Windows-v1.0.1.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(exe_file, arcname="Dayflow/Dayflow.exe")
            zf.write(uninst_file, arcname="Dayflow/uninst.exe")
            zf.write(readme_path, arcname="Dayflow/使用说明.txt")

        zip_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"  -> {zip_path} ({zip_mb:.2f} MB)")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
