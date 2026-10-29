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
        "--exclude-module=pytest",
        "--exclude-module=unittest",
        f"--distpath={root_dir / 'release'}",
        f"--workpath={root_dir / 'build' / 'pyinstaller'}",
        f"--specpath={root_dir / 'build'}",
        str(root_dir / "main.py"),
    ]
    PyInstaller.__main__.run(args)
    exe_file = root_dir / "release" / "Dayflow.exe"
    if exe_file.is_file():
        size_mb = exe_file.stat().st_size / (1024 * 1024)
        print(f"\n[Dayflow Build] SUCCESS! Standalone executable created:")
        print(f"  -> {exe_file} ({size_mb:.2f} MB)")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
