from __future__ import annotations

from itertools import product
from math import ceil, log
from time import time
from typing import TYPE_CHECKING

from hints.backends.exceptions import AccessibleChildrenNotFoundError
from hints.constants import KEYBOARD_ZONES
from hints.utils import HintsConfig, load_config
from hints.window_systems.exceptions import WindowSystemNotSupported
from hints.window_systems.window_system import WindowSystem
from hints.window_systems.window_system_type import (
    SupportedWindowSystems,
    WindowSystemType,
    get_window_system_type,
)

if TYPE_CHECKING:
    from typing import Any, Iterable, Type

    from hints.child import Child
    from hints.window_systems.window_system import WindowSystem


class _LazyLogger:
    """Proxy that defers ``import logging`` (~5 ms) until first use."""

    __slots__ = ()

    def __getattr__(self, name: str):
        import logging

        real = logging.getLogger(__name__)
        # Replace the module-level name so subsequent calls are direct.
        globals()["logger"] = real
        return getattr(real, name)


logger = _LazyLogger()  # type: ignore[assignment]


def display_gtk_window(
    window_system: WindowSystem,
    gtk_window,
    x: int,
    y: int,
    width: int,
    height: int,
    gkt_window_args: Iterable[Any] | None = None,
    gtk_window_kwargs: dict[str, Any] | None = None,
    overlay_x_offset: int = 0,
    overlay_y_offset: int = 0,
):
    """Setup and Display gtk window.

    :param window_system: The window system.
    :param gtk_window: The Gtk Window class to display.
    :param x: X position for window.
    :param y: Y position for window.
    :param width: Width for window.
    :param height: Height for window.
    :param gkt_window_args: The positional argument for the window
        instance.
    :param gtk_widnow_kwargs: The keyword arguments for the window
        instance.
    :param overlay_x_offset: X offset position for the window.
    :param overlay_y_offset: Y offset position for the window.
    """
    from gi import require_version

    require_version("Gtk", "3.0")
    require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gtk

    window_x_pos = x + overlay_x_offset
    window_y_pos = y + overlay_y_offset

    window = gtk_window(
        window_x_pos,
        window_y_pos,
        width,
        height,
        *(gkt_window_args or []),
        **(gtk_window_kwargs or {}),
    )

    if window_system.window_system_name == "gnome":
        from hints.gnome_overlay import init_overlay_window
        init_overlay_window(window, window_system, window_x_pos, window_y_pos)
    elif window_system.window_system_type == WindowSystemType.WAYLAND:
        require_version("GtkLayerShell", "0.1")
        from gi.repository import GtkLayerShell

        GtkLayerShell.init_for_window(window)

        # On sway (unknow about other wayland compositors as of now), the
        # compositor cannot be relied on to put a window on the correct monitor,
        # so we are setting the monitor and treating the window as relative to
        # that monitor to position hints.
        expected_monitor = Gdk.Display.get_monitor_at_point(
            Gdk.Display.get_default(), window_x_pos, window_y_pos
        )
        expected_monitor_geometry = expected_monitor.get_geometry()
        GtkLayerShell.set_monitor(window, expected_monitor)

        GtkLayerShell.set_margin(
            window, GtkLayerShell.Edge.LEFT, window_x_pos - expected_monitor_geometry.x
        )
        GtkLayerShell.set_margin(
            window, GtkLayerShell.Edge.TOP, window_y_pos - expected_monitor_geometry.y
        )
        GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_layer(window, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(window, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        GtkLayerShell.set_namespace(
            window, "hints"
        )  # Allows for compositor layer rules

    window.show_all()
    Gtk.main()


def _get_zone(rx: float, ry: float, width: float, height: float) -> tuple[int, int]:
    """Map a child's relative position to a 3x3 screen zone.

    :param rx: Relative x position of the child.
    :param ry: Relative y position of the child.
    :param width: Window width.
    :param height: Window height.
    :return: (row, col) zone indices, each in 0..2.
    """
    nx = max(0.0, min(1.0, rx / width)) if width > 0 else 0.5
    ny = max(0.0, min(1.0, ry / height)) if height > 0 else 0.5
    col = min(int(nx * 3), 2)
    row = min(int(ny * 3), 2)
    return (row, col)


def get_hints(
    children: list[Child],
    alphabet: str,
    window_size: tuple[float, float] | None = None,
) -> dict[str, Child]:
    """Get hints with spatial zone-based keyboard assignment.

    The screen is split into a 3x3 grid that mirrors the keyboard layout:
      Left keys   (q/w/e, a/s/d, z/x/c)  → left third of screen
      Center keys (r/t/y, f/g/h, v/b/n)  → center third
      Right keys  (u/i/o/p, j/k/l, m)    → right third
    Keyboard rows (top/home/bottom) map to screen rows (top/mid/bottom).

    Within each zone, children are sorted top-to-bottom, left-to-right and
    assigned the zone's keys sequentially.  If a zone has more children
    than single keys, multi-character hints are generated from that zone's
    key set.

    :param children: The children elements of window that indicate the
        absolute position of those elements.
    :param alphabet: The alphabet used to create hints.
    :param window_size: Optional (width, height) for spatial mapping.
    :return: The hints. Ex {"ag": Child, "sh": Child}
    """
    hints: dict[str, Child] = {}

    if len(children) == 0:
        return hints

    # Fall back to sequential assignment when spatial mapping isn't possible.
    if window_size is None:
        n_chars = ceil(log(len(children)) / log(len(alphabet)))
        for child, hint in zip(
            children,
            product(alphabet, repeat=n_chars),
        ):
            hints["".join(hint)] = child
        return hints

    width, height = window_size

    # Bucket children into their 3x3 screen zone.
    zone_buckets: dict[tuple[int, int], list[Child]] = {}
    for child in children:
        rx, ry = child.relative_position
        zone = _get_zone(rx, ry, width, height)
        zone_buckets.setdefault(zone, []).append(child)

    # Redistribute overflow: when a zone has more children than its 2-char
    # hint capacity (zone_keys × alphabet_size), spill excess children to
    # the nearest neighboring zone(s) with spare room.  Children closest
    # to the neighbor are moved first to preserve spatial coherence.
    def _zone_cap(r: int, c: int) -> int:
        return len(KEYBOARD_ZONES[r][c]) * len(alphabet)

    def _zone_center_px(r: int, c: int) -> tuple[float, float]:
        return ((c + 0.5) / 3 * width, (r + 0.5) / 3 * height)

    def _neighbors(r: int, c: int) -> list[tuple[int, int]]:
        """Adjacent zones sorted by grid distance (cardinal first)."""
        nbrs = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr <= 2 and 0 <= nc <= 2:
                    nbrs.append((nr, nc))
        nbrs.sort(key=lambda z: (z[0] - r) ** 2 + (z[1] - c) ** 2)
        return nbrs

    for _ in range(9):  # at most 9 zones; converges quickly
        moved_any = False
        for zone in list(zone_buckets):
            cap = _zone_cap(*zone)
            bucket = zone_buckets[zone]
            if len(bucket) <= cap:
                continue
            excess = len(bucket) - cap
            for nbr in _neighbors(*zone):
                nbr_cap = _zone_cap(*nbr)
                nbr_bucket = zone_buckets.setdefault(nbr, [])
                space = nbr_cap - len(nbr_bucket)
                if space <= 0:
                    continue
                # Sort by distance to neighbor center; move the closest.
                ncx, ncy = _zone_center_px(*nbr)
                bucket.sort(
                    key=lambda ch, _cx=ncx, _cy=ncy: (
                        (ch.relative_position[0] - _cx) ** 2
                        + (ch.relative_position[1] - _cy) ** 2
                    )
                )
                to_move = min(space, excess)
                zone_buckets[nbr] = nbr_bucket + bucket[:to_move]
                bucket = bucket[to_move:]
                zone_buckets[zone] = bucket
                excess -= to_move
                moved_any = True
                if excess <= 0:
                    break
        if not moved_any:
            break

    # Sort each bucket top-to-bottom, left-to-right after redistribution.
    for bucket in zone_buckets.values():
        bucket.sort(key=lambda c: (c.relative_position[1], c.relative_position[0]))

    # Assign hints per zone using that zone's keyboard keys.
    # The first character comes from the zone's own keys (spatial meaning),
    # subsequent characterzs use the full alphabet (maximizes 2-char coverage).
    for (row, col), zone_children in zone_buckets.items():
        zone_keys = KEYBOARD_ZONES[row][col]
        n = len(zone_children)

        if n <= len(zone_keys):
            # Few enough children — single-char hints from the zone keys.
            for child, key in zip(zone_children, zone_keys):
                hints[key] = child
        else:
            # Multi-char: first char = zone key, rest = full alphabet.
            hint_labels = []
            for first in zone_keys:
                for rest in product(alphabet, repeat=1):
                    hint_labels.append(first + "".join(rest))
                    if len(hint_labels) >= n:
                        break
                if len(hint_labels) >= n:
                    break

            # If still not enough (very dense zone), extend to 3 chars.
            if len(hint_labels) < n:
                hint_labels = []
                for first in zone_keys:
                    for rest in product(alphabet, repeat=2):
                        hint_labels.append(first + "".join(rest))
                        if len(hint_labels) >= n:
                            break
                    if len(hint_labels) >= n:
                        break

            for child, label in zip(zone_children, hint_labels):
                hints[label] = child

    return hints


def _preload_gtk_modules():
    """Pre-import GTK and overlay modules in a background thread.

    Started from hint_mode() right after the atspi backend import (so
    ``gi`` is already cached).  The Gdk + Gtk + overlay imports (~30 ms)
    overlap with the atspi tree walk (get_children), so they are free.
    """
    try:
        from gi import require_version

        require_version("Gtk", "3.0")
        require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gtk  # noqa: F811, F401
        from hints.huds.overlay import OverlayWindow  # noqa: F401
    except Exception:
        pass  # failures are benign; the main thread will import again


# Background-thread bookkeeping shared between main() and hint_mode().
_gtk_preload_thread: object | None = None


def _start_preloads():
    """Kick off GTK preload in a daemon thread.

    Called from hint_mode() after the atspi backend is imported (so gi
    is already cached).  The thread pre-imports Gdk + Gtk + overlay
    while the main thread does the atspi tree walk.
    """
    import threading

    global _gtk_preload_thread
    _gtk_preload_thread = threading.Thread(
        target=_preload_gtk_modules, daemon=True,
    )
    _gtk_preload_thread.start()


def _wait_gtk_preload():
    """Block until the GTK preload thread has finished (if it was started)."""
    global _gtk_preload_thread
    thread = _gtk_preload_thread
    if thread is not None:
        thread.join()  # type: ignore[union-attr]
        _gtk_preload_thread = None


def hint_mode(config: HintsConfig, window_system: WindowSystem):
    """Hint mode to interact with hints on screen.

    :param config: Hints config.
    :param window_system: Window System for the session.
    :param mouse: Mouse device for mouse actions.
    """

    window_extents = None
    hints = {}

    backends = config["backends"]["enable"]

    for backend in backends:

        start = time()
        # Lazy-import backends so we only pay the import cost (especially
        # OpenCV ~130 ms) when that backend is actually needed.
        if backend == "atspi":
            from hints.backends.atspi import AtspiBackend
            current_backend = AtspiBackend(config, window_system)
        elif backend == "opencv":
            from hints.backends.opencv import OpenCV
            current_backend = OpenCV(config, window_system)
        else:
            logger.warning("Unknown backend '%s', skipping.", backend)
            continue
        logger.debug(
            "Attempting to get accessible children using the '%s' backend.",
            backend,
        )

        # Pre-import GTK + overlay in a background thread while the tree
        # walk runs.  gi is already cached from the atspi import above,
        # so the thread only needs to load Gdk + Gtk typelibs (~30 ms).
        _start_preloads()

        try:
            children = current_backend.get_children()
            window_extents = current_backend.window_system.focused_window_extents

            logger.debug("Gathering hints took %f seconds", time() - start)
            logger.debug("Gathered %d hints", len(children))

            hints = get_hints(
                children,
                alphabet=config["alphabet"],
                window_size=(
                    window_extents[2], window_extents[3]
                )
                if window_extents
                else None,
            )

        except AccessibleChildrenNotFoundError:
            logger.debug(
                "No acceessible children found with the '%s' backend.",
                backend,
            )

        if window_extents and hints:
            mouse_action: dict[str, Any] = {}
            x, y, width, height = window_extents

            # Ensure GTK preload finished before touching the overlay.
            _wait_gtk_preload()
            from hints.huds.overlay import OverlayWindow

            display_gtk_window(
                window_system,
                OverlayWindow,
                x,
                y,
                width,
                height,
                gkt_window_args=(
                    config,
                    hints,
                    mouse_action,
                ),
                gtk_window_kwargs={
                    "is_wayland": window_system.window_system_type
                    == WindowSystemType.WAYLAND,
                },
                overlay_x_offset=config["overlay_x_offset"],
                overlay_y_offset=config["overlay_y_offset"],
            )

            if mouse_action:

                from hints.huds.interceptor import InterceptorWindow
                from hints.mouse import click
                from hints.mouse_enums import MouseButton, MouseButtonState

                mouse_x_offset = 0
                mouse_y_offset = 0

                match window_system.window_system_name:
                    case "sway":
                        mouse_y_offset = window_system.bar_height

                logger.debug("performing '%s'", mouse_action)

                match mouse_action["action"]:
                    case "click":
                        click(
                            mouse_action["x"] + mouse_x_offset,
                            mouse_action["y"] + mouse_y_offset,
                            mouse_action["button"],
                            (MouseButtonState.DOWN, MouseButtonState.UP),
                            mouse_action["repeat"],
                        )
                    case "hover":
                        click(
                            mouse_action["x"] + mouse_x_offset,
                            mouse_action["y"] + mouse_y_offset,
                            MouseButton.LEFT,
                            (),
                        )
                    case "grab":
                        click(
                            mouse_action["x"] + mouse_x_offset,
                            mouse_action["y"] + mouse_y_offset,
                            MouseButton.LEFT,
                            (MouseButtonState.DOWN,),
                        )

                        display_gtk_window(
                            window_system,
                            InterceptorWindow,
                            x,
                            y,
                            1,
                            1,
                            gkt_window_args=({"action": "grab"}, config),
                            gtk_window_kwargs={
                                "is_wayland": window_system.window_system_type
                                == WindowSystemType.WAYLAND,
                            },
                        )

            # no need to use the next backend if the current one succeeded
            break


def get_window_system_class(
    window_system_id: SupportedWindowSystems | str,
) -> Type[WindowSystem] | None:
    """Get the window system class for the window system id.

    :param window_system_id: A string identifying the supported window
        system.
    :return: The window system class.
    """

    window_system: Type[WindowSystem] | None = None

    match window_system_id:
        case "x11":
            from hints.window_systems.x11 import X11 as window_system
        case "sway":
            from hints.window_systems.sway import Sway as window_system
        case "hyprland":
            from hints.window_systems.hyprland import Hyprland as window_system
        case "plasmashell":
            from hints.window_systems.plasmashell import Plasmashell as window_system
        case "gnome-shell":
            from hints.window_systems.gnome import Gnome as window_system

    return window_system


def get_window_system(window_system_id: str = "") -> Type[WindowSystem]:
    """Get window system.

    :param window_system_id: The window system id to use (see
        get_window_system_class), otherwise, try to find the best match.
    :return: The window system for the current system.
    """

    if not window_system_id:

        window_system_type = get_window_system_type()

        if window_system_type == WindowSystemType.X11:
            window_system_id = "x11"
        if window_system_type == WindowSystemType.WAYLAND:

            # add new wayland wms here, then add a match case below to import the class
            supported_wayland_wms = {"sway", "Hyprland", "plasmashell", "gnome-shell"}

            # Detect the running compositor by scanning /proc directly.
            # This avoids spawning ps + grep subprocesses (~50 ms saving).
            from os import listdir
            from os.path import isdir, join

            for pid_dir in listdir("/proc"):
                if not pid_dir.isdigit():
                    continue
                try:
                    comm_path = join("/proc", pid_dir, "comm")
                    with open(comm_path) as f:
                        comm = f.read().strip()
                    if comm in supported_wayland_wms:
                        window_system_id = comm.lower()
                        break
                except (OSError, PermissionError):
                    continue

    window_system = get_window_system_class(window_system_id)

    if not window_system:
        from typing import get_args

        raise WindowSystemNotSupported(get_args(SupportedWindowSystems))

    return window_system


def main():
    """Hints entry point."""

    # gi._gi (C extension) imports several heavy stdlib modules solely for
    # optional GLib integration that hints never uses.  Pre-populating
    # sys.modules with minimal stubs avoids those bootstrap costs:
    #
    #   asyncio  (~23 ms) — GLib/asyncio event-loop bridge
    #   socket   (~ 2 ms) — GLib.IOChannel Win32 socket path (never hit on Linux)
    #   selectors, ipaddress — pulled in transitively by socket
    #   gi._option / optparse (~3 ms) — GLib option-parsing integration
    #
    # Each stub provides only the symbols the gi C extension actually accesses
    # at import time.  Any accidental use of real functionality will fail loudly
    # because the stubs are intentionally minimal.
    import sys as _sys
    if "asyncio" not in _sys.modules:
        from types import ModuleType as _MT

        class _AsyncioStub(_MT):
            class InvalidStateError(Exception):
                pass

            @staticmethod
            def _get_running_loop():
                return None

            @staticmethod
            def get_event_loop():
                return None

        _sys.modules["asyncio"] = _AsyncioStub("asyncio")

        # socket — gi/overrides/GLib.py: `isinstance(ch, socket.socket)` in a
        # Win32-only branch.  The stub's socket class ensures isinstance returns
        # False without triggering selectors/ipaddress.
        class _SocketStub(_MT):
            class socket:
                pass

        _sys.modules["socket"] = _SocketStub("socket")
        _sys.modules["selectors"] = _MT("selectors")
        _sys.modules["ipaddress"] = _MT("ipaddress")

        # gi._option / optparse — GLib option-parsing extension exposed as
        # GLib.option; hints never uses it.  Stubbing gi._option directly avoids
        # loading optparse (~3 ms).
        _opt = _MT("gi._option")
        for _n in (
            "OptParseError", "OptionError", "OptionValueError",
            "BadOptionError", "OptionConflictError", "Option",
            "OptionGroup", "OptionContext", "make_option", "OptionParser",
        ):
            setattr(_opt, _n, type(_n, (Exception if "Error" in _n else object,), {}))
        _sys.modules["gi._option"] = _opt
        _sys.modules["optparse"] = _MT("optparse")

    config = load_config()

    from argparse import ArgumentParser

    parser = ArgumentParser(
        prog="Hints",
        description="Hints lets you navigate GUI applications in Linux without"
        ' your mouse by displaying "hints" you can type on your keyboard to'
        " interact with GUI elements.",
    )
    parser.add_argument(
        "-m",
        "--mode",
        type=str,
        default="hint",
        choices=["hint", "scroll"],
        help="mode to use",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Set verbosity of output. Useful for debugging and seeing the"
        " output of accessible elements (roles, states, application name, ect)"
        " for setting up configuration.",
    )

    args = parser.parse_args()

    import logging

    custom_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    if args.verbose >= 1:
        logging.basicConfig(level=logging.DEBUG, format=custom_format)
    else:
        logging.basicConfig(level=logging.INFO, format=custom_format)

    window_system = get_window_system(config["window_system"])()

    match args.mode:
        case "hint":
            hint_mode(config, window_system)
        case "scroll":
            from hints.huds.interceptor import InterceptorWindow

            display_gtk_window(
                window_system,
                InterceptorWindow,
                0,
                0,
                1,
                1,
                gkt_window_args=({"action": "scroll"}, config),
                gtk_window_kwargs={
                    "is_wayland": window_system.window_system_type
                    == WindowSystemType.WAYLAND,
                },
            )

if __name__ == "__main__":
    main()
