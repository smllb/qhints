"""Linux X11 window system — lightweight ctypes-based implementation.

Uses ctypes to call Xlib directly, avoiding the heavy gi + Wnck typelib
import (~59 ms) while providing the same window information.
"""

import ctypes
import ctypes.util
from ctypes import POINTER, Structure, byref, c_int, c_uint, c_ulong, c_void_p

from hints.window_systems.window_system import WindowSystem

# X11 atom type constants
_XA_CARDINAL = 6
_XA_STRING = 31
_XA_WINDOW = 33


def _load_xlib():
    """Load and configure the Xlib shared library."""
    path = ctypes.util.find_library("X11")
    if not path:
        raise OSError("Could not find libX11")
    xlib = ctypes.cdll.LoadLibrary(path)
    xlib.XOpenDisplay.restype = c_void_p
    xlib.XInternAtom.restype = c_ulong
    xlib.XDefaultRootWindow.restype = c_ulong
    return xlib


def _get_window_property(xlib, display, window, atom, expected_type, length=1):
    """Read an X11 window property and return (nitems, data_ptr)."""
    actual_type = c_ulong()
    actual_format = c_int()
    nitems = c_ulong()
    bytes_after = c_ulong()
    data = c_void_p()

    xlib.XGetWindowProperty(
        display, window, atom,
        0, length, False, c_ulong(expected_type),
        byref(actual_type), byref(actual_format),
        byref(nitems), byref(bytes_after), byref(data),
    )
    return nitems.value, data


class X11(WindowSystem):
    """Linux X11 window system using direct Xlib calls via ctypes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        xlib = _load_xlib()
        self._display = xlib.XOpenDisplay(None)
        if not self._display:
            raise OSError("Could not open X11 display")

        root = xlib.XDefaultRootWindow(self._display)

        # Intern the atoms we need.
        net_active = xlib.XInternAtom(self._display, b"_NET_ACTIVE_WINDOW", False)
        net_wm_pid = xlib.XInternAtom(self._display, b"_NET_WM_PID", False)
        wm_class = xlib.XInternAtom(self._display, b"WM_CLASS", False)

        # Active window ID
        nitems, data = _get_window_property(
            xlib, self._display, root, net_active, _XA_WINDOW,
        )
        if nitems == 0 or not data.value:
            xlib.XCloseDisplay(self._display)
            raise OSError("No active window found")
        self._active_win = ctypes.cast(data.value, POINTER(c_ulong))[0]
        xlib.XFree(data)

        # Window geometry (translated to root coordinates).
        root_ret = c_ulong()
        x_ret, y_ret = c_int(), c_int()
        w_ret, h_ret = c_uint(), c_uint()
        border_ret, depth_ret = c_uint(), c_uint()
        xlib.XGetGeometry(
            self._display, self._active_win, byref(root_ret),
            byref(x_ret), byref(y_ret), byref(w_ret), byref(h_ret),
            byref(border_ret), byref(depth_ret),
        )
        abs_x, abs_y = c_int(), c_int()
        child_ret = c_ulong()
        xlib.XTranslateCoordinates(
            self._display, self._active_win, root, 0, 0,
            byref(abs_x), byref(abs_y), byref(child_ret),
        )
        self._geometry = (abs_x.value, abs_y.value, w_ret.value, h_ret.value)

        # PID
        nitems, data = _get_window_property(
            xlib, self._display, self._active_win, net_wm_pid, _XA_CARDINAL,
        )
        self._pid = (
            ctypes.cast(data.value, POINTER(c_ulong))[0] if nitems > 0 and data.value else 0
        )
        if data.value:
            xlib.XFree(data)

        # WM_CLASS (instance name)
        nitems, data = _get_window_property(
            xlib, self._display, self._active_win, wm_class, _XA_STRING, 1024,
        )
        if nitems > 0 and data.value:
            raw = ctypes.string_at(data.value, nitems)
            parts = raw.split(b"\x00")
            self._class_instance = parts[0].decode(errors="replace") if parts else ""
            xlib.XFree(data)
        else:
            self._class_instance = ""

        xlib.XCloseDisplay(self._display)

    @property
    def window_system_name(self) -> str:
        """Get the name of the window syste.

        This is useful for performing logic specific to a window system.

        :return: The window system name
        """
        return "x11"

    @property
    def focused_window_extents(self) -> tuple[int, int, int, int]:
        """Get active window extents.

        :return: Active window extents (x, y, width, height).
        """
        return self._geometry

    @property
    def focused_window_pid(self) -> int:
        """Get Process ID corresponding to the focused widnow.

        :return: Process ID of focused window.
        """
        return self._pid

    @property
    def focused_applicaiton_name(self) -> str:
        """Get focused application name.

        This name is the name used to identify applications for per-
        application rules.

        :return: Focused application name.
        """
        return self._class_instance
