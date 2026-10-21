"""Move the player views' windows to other places on the screen.

The engine tiles each view once, when its window opens (GAMENIGHT_COUCH_SEAT
and GAMENIGHT_COUCH_PLAYERS). When players change places on the couch during a
match, the views trade the rectangles they already cover, so nobody reconnects
and the layout stays exactly what the engine chose. Windows only; elsewhere the
views are not tiled and there is nothing to move.
"""

import sys


def windows_by_pid(pids):
    """The SDL game window of each process, or None when it has none yet."""
    if sys.platform != "win32":
        return {}
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found = {}
    wanted = set(pids)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in wanted and pid.value not in found:
            name = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, name, 64)
            if name.value == "SDL_app":
                found[pid.value] = hwnd
        return True

    _physical_pixels(user32)
    user32.EnumWindows(visit, 0)
    return found


def rect(hwnd):
    import ctypes
    from ctypes import wintypes

    r = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def place(hwnd, area):
    import ctypes

    swp_nozorder, swp_noactivate, swp_noownerzorder = 0x0004, 0x0010, 0x0200
    x, y, w, h = area
    ctypes.windll.user32.SetWindowPos(
        hwnd, None, x, y, w, h, swp_nozorder | swp_noactivate | swp_noownerzorder
    )


def _physical_pixels(user32):
    # Read and write real pixels, whatever scaling the display uses, so a
    # rectangle moves from one window to another without rounding.
    try:
        user32.SetThreadDpiAwarenessContext(-4)  # per-monitor aware v2
    except (AttributeError, OSError):
        pass


def trade(pids, current, wanted):
    """Give view i the rectangle that the view in slot wanted[i] covers now.
    False when a window is missing, so the caller tries again later."""
    windows = windows_by_pid(pids)
    if len(windows) != len(pids):
        return False
    areas = {current[i]: rect(windows[pid]) for i, pid in enumerate(pids)}
    if set(areas) != set(wanted):
        return False
    for i, pid in enumerate(pids):
        if wanted[i] != current[i]:
            place(windows[pid], areas[wanted[i]])
    return True
