from __future__ import annotations

from pathlib import Path

from uninst import main as uninst_main, perform_uninstall_cleanup


def test_perform_uninstall_cleanup_removes_data_and_binaries(tmp_path: Path) -> None:
    install_dir = tmp_path / "DayflowInstall"
    data_dir = install_dir / "data"
    data_dir.mkdir(parents=True)

    # 创建模拟数据库文件与主程序文件
    (data_dir / "dayflow.db").write_bytes(b"sqlite-data")
    (data_dir / "dayflow.db-wal").write_bytes(b"wal-data")
    (data_dir / "dayflow.db-shm").write_bytes(b"shm-data")
    (install_dir / "Dayflow.exe").write_bytes(b"MZ-fake-exe")
    (install_dir / "使用说明.txt").write_text("readme", encoding="utf-8")

    # 创建模拟 %LOCALAPPDATA%/Dayflow 回退数据目录
    appdata_dir = tmp_path / "LocalAppData" / "Dayflow"
    (appdata_dir / "data").mkdir(parents=True)
    (appdata_dir / "data" / "dayflow.db").write_bytes(b"fallback-db")

    res = perform_uninstall_cleanup(
        install_dir=install_dir,
        local_appdata_dir=appdata_dir,
        stop_process=False,
        clean_registry=False,
    )

    assert res["data_removed"] is True
    assert res["appdata_removed"] is True
    assert res["exe_removed"] is True
    assert res["readme_removed"] is True

    assert not data_dir.exists()
    assert not appdata_dir.exists()
    assert not (install_dir / "Dayflow.exe").exists()
    assert not (install_dir / "使用说明.txt").exists()


def test_uninst_cli_silent_mode(tmp_path: Path) -> None:
    install_dir = tmp_path / "SilentInstall"
    (install_dir / "data").mkdir(parents=True)
    (install_dir / "data" / "dayflow.db").write_text("db", encoding="utf-8")
    (install_dir / "Dayflow.exe").write_text("exe", encoding="utf-8")

    exit_code = uninst_main(["--yes", f"--target-dir={install_dir}"])
    assert exit_code == 0
    assert not (install_dir / "data").exists()
    assert not (install_dir / "Dayflow.exe").exists()
