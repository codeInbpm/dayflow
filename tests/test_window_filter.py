from dayflow.window_filter import (
    SYSTEM_EXE_BLACKLIST,
    ActiveWindowInfo,
    get_foreground_window_info,
    resolve_uwp_child_pid,
    should_track_window,
)


def test_filter_distinguishes_desktop_and_file_explorer():
    desktop = ActiveWindowInfo(
        1, 100, "C:/Windows/explorer.exe", "explorer.exe", "", "Progman"
    )
    taskbar = ActiveWindowInfo(
        2, 100, "C:/Windows/explorer.exe", "explorer.exe", "", "Shell_TrayWnd"
    )
    workerw = ActiveWindowInfo(
        21, 100, "C:/Windows/explorer.exe", "explorer.exe", "FolderView", "WorkerW"
    )
    empty_title_folder = ActiveWindowInfo(
        22, 100, "C:/Windows/explorer.exe", "explorer.exe", "   ", "CabinetWClass"
    )
    folder = ActiveWindowInfo(
        3,
        100,
        "C:/Windows/explorer.exe",
        "explorer.exe",
        "dayflow - 文件资源管理器",
        "CabinetWClass",
    )
    explore_cls = ActiveWindowInfo(
        31,
        100,
        "C:/Windows/explorer.exe",
        "Explorer.EXE",
        "下载",
        "ExploreWClass",
    )
    lock_screen = ActiveWindowInfo(
        4,
        200,
        "C:/Windows/SystemApps/LockApp.exe",
        "LockApp.exe",
        "Windows 默认锁屏界面",
        "Windows.UI.Core.CoreWindow",
    )

    assert should_track_window(desktop) is False
    assert should_track_window(taskbar) is False
    assert should_track_window(workerw) is False
    assert should_track_window(empty_title_folder) is False
    assert should_track_window(folder) is True
    assert should_track_window(explore_cls) is True
    assert should_track_window(lock_screen) is False


def test_uwp_frame_host_penetration_and_fallback():
    assert resolve_uwp_child_pid(host_pid=500, child_pids=[500, 500]) is None
    assert resolve_uwp_child_pid(host_pid=500, child_pids=[500, 888]) == 888
    assert resolve_uwp_child_pid(host_pid=500, child_pids=[0, -1, 500, 999]) == 999

    unpenetrated_uwp = ActiveWindowInfo(
        5,
        500,
        "C:/Windows/System32/ApplicationFrameHost.exe",
        "ApplicationFrameHost.exe",
        "设置",
        "ApplicationFrameWindow",
    )
    assert should_track_window(unpenetrated_uwp) is False


def test_self_pid_and_system_blacklist_filtering():
    normal_app = ActiveWindowInfo(
        10,
        4321,
        "C:/Program Files/WeChat/WeChat.exe",
        "WeChat.exe",
        "微信",
        "WeChatMainWndForPC",
    )
    assert should_track_window(normal_app, self_pid=9999) is True
    assert should_track_window(normal_app, self_pid=4321) is False

    for sys_exe in ("SearchHost.exe", "StartMenuExperienceHost.exe", "dwm.exe", "svchost.exe"):
        assert sys_exe.lower() in SYSTEM_EXE_BLACKLIST
        info = ActiveWindowInfo(11, 555, f"C:/Windows/System32/{sys_exe}", sys_exe, "Title", "Cls")
        assert should_track_window(info) is False


def test_get_foreground_window_info_smoke():
    # 在真实或沙箱 Win32 环境下调用不抛异常，返回 ActiveWindowInfo 或 None
    res = get_foreground_window_info(self_pid=-1)
    assert res is None or isinstance(res, ActiveWindowInfo)
