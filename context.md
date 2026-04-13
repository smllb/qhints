# spatial-hints — Development Context

## Goal
Optimize startup time further before adding new features. Current target: reduce time-to-hints-visible below 100ms.

## Branch
`spatial-position-based-letters` on [github.com/smllb/spatial-hints](https://github.com/smllb/spatial-hints)

Forked from [AlfredoSequeida/hints](https://github.com/AlfredoSequeida/hints). Upstream remote is `upstream`.

## Commits (oldest → newest)

### 1. `cd83783` feat: letters on hints based on spatial position
*(pre-existing before this session)*

### 2. `011a456` feat: better spatial positioning
*(pre-existing before this session)*

### 3. `950eb85` feat: Vimium-style hints with zone-based layout, overlap filtering, and per-character rendering
**Files:** `hints/constants.py`, `hints/huds/overlay.py`

- Replaced `KEYBOARD_POSITIONS` (per-key normalized coordinates) with `KEYBOARD_ZONES` — a 3×3 grid mapping screen regions to keyboard regions so hint letters spatially match their screen position.
- Vimium-style appearance: monospace font, rounded corners (`hint_corner_radius: 6`), border, drop shadow, compact sizing (`hint_height: 20`, `hint_font_size: 14`).
- Red first-letter emphasis via `hint_first_font_r/g/b/a` config.
- Overlap detection: pre-computes bounding boxes, calculates overlap fraction, greedy filtering with configurable `hint_overlap_threshold` (0–100, default 60).
- Per-character text rendering: first letter red+larger, already-typed chars green, rest normal.

### 4. `d90d6b5` feat: overflow redistribution to minimize 3-char hints
**Files:** `hints/hints.py`

- After bucketing children into 3×3 zones, overflow redistribution spills excess children to the nearest neighboring zone with spare capacity.
- Children closest to the neighbor's center are moved first to preserve spatial coherence.
- Iterates up to 9 passes until balanced.
- Result: 3-char hints only appear when total children exceed the global 2-char capacity (676). A skewed test case went from 238 → 0 three-char hints.

### 5. `6b2230e` perf: lazy backend imports + /proc-based WM detection (~44% faster startup)
**Files:** `hints/hints.py`

- **Lazy backend imports:** `AtspiBackend` and `OpenCV` are imported only when their backend is used in the loop. Since atspi usually succeeds, the ~130ms `cv2` import is skipped.
- **Removed unused `subprocess.run` import.**
- **/proc-based WM detection:** On Wayland, replaced `ps -e | grep` shell pipeline with direct `/proc/*/comm` scan, avoiding two subprocess spawns.

### 6. `38060ee` perf: eliminate GI imports from startup critical path (~62% faster)
**Files:** `hints/constants.py`, `hints/utils.py`, `hints/hints.py`, `hints/window_systems/x11.py`

- **Lazy `get_default_config()`:** Converted `DEFAULT_CONFIG` from a module-level dict to a cached function. Uses raw integer values for all Atspi enum constants (StateType, CollectionMatchType, Role) and Gdk key/modifier constants instead of importing GI typelibs. GI enums are int subclasses so comparisons work identically. Saves ~31ms (gi+Atspi) + ~14ms (Gdk) from config load.
- **Ctypes-based X11 window system:** Rewrote `x11.py` to use ctypes Xlib calls directly (`XGetWindowProperty`, `XGetGeometry`, `XTranslateCoordinates`) instead of gi+Wnck. Gets active window, geometry, PID, and WM_CLASS in ~3ms vs ~59ms with Wnck. No new dependencies — ctypes and libX11 are always available.
- **Deferred imports in `hints.py`:** Removed all module-level gi/GTK/overlay/mouse imports. `OverlayWindow` imported after `get_children()`. `InterceptorWindow`/`click`/`MouseButton`/`MouseButtonState` imported only when a mouse action is needed. Scroll mode imports `InterceptorWindow` lazily.
- **Threaded GTK preload:** `_preload_gtk_modules()` runs in a daemon thread started before `get_children()`, pre-importing GTK+Gdk+overlay so the ~30ms GTK bootstrap overlaps with the ~31ms atspi tree walk.

### 7. `5123d07` perf: eliminate ctypes.util + defer logging/argparse (~10ms faster)
**Files:** `hints/hints.py`, `hints/window_systems/x11.py`

- **Direct libX11 loading:** Removed `import ctypes.util` (~6ms) and `find_library()` subprocess call (~4ms). Now tries `LoadLibrary('libX11.so.6')` directly, with lazy `find_library` fallback only on unusual systems. X11 module import: ~5ms → ~0.7ms.
- **Lazy logger proxy:** Replaced module-level `import logging` (~5ms) with `_LazyLogger` class that defers the import until first actual log call. The proxy replaces itself with the real logger on first access.
- **Deferred stdlib imports:** `ArgumentParser` moved into `main()`, `import logging` for `basicConfig` moved into `main()`, `get_args` moved to error-only path, `Any`/`Iterable`/`Type` moved behind `TYPE_CHECKING` guard.
- **Benchmarking insight:** Tested early GTK preload (in `main()`) vs late (in `hint_mode()` after atspi import). Early adds GIL contention during the serial atspi import; late is ~4ms faster. GTK preload now starts in `hint_mode()` only.

### 8. `7c474ec` fix: remove white border around focused window on hints trigger
**Files:** `hints/huds/overlay.py`

- Removed `Gtk.Frame` (with `ShadowType.IN`) and `Gtk.VPaned` that were wrapping the `DrawingArea` in `OverlayWindow.__init__`. These GTK container widgets were rendering a visible white border/shadow around the focused window every time hints were activated.
- `DrawingArea` is now added directly to the window with `self.add(self.drawing_area)`.

### 9. `54ccb7d` perf: stub asyncio before gi import to skip 23ms bootstrap cost
**Files:** `hints/hints.py`

- `gi._gi` (C extension) unconditionally imports `asyncio` for GLib event-loop integration that hints never uses. This costs ~23ms of the ~32ms `import gi` total.
- At the very start of `main()`, before any gi import can happen, `sys.modules['asyncio']` is pre-populated with a minimal `_AsyncioStub(ModuleType)` that exposes exactly the two symbols `gi._gi` accesses: `InvalidStateError`, `_get_running_loop()`, `get_event_loop()`.
- The guard `if "asyncio" not in sys.modules` ensures normal asyncio is untouched in contexts where it was already imported (e.g. tests).
- Atspi remains fully functional: desktop tree walk, `get_child_at_index`, `get_role`, state sets all verified working.
- Fixed overhead: **~38ms → ~23ms** (-15ms, -39%)

### 10. `8fe3733` perf: stub socket/selectors/ipaddress/gi._option to save ~3ms
**Files:** `hints/hints.py`

- `socket` (~2ms): `gi/overrides/GLib.py` imports it for a Win32 `isinstance(channel, socket.socket)` check — dead code on Linux. Stub provides a dummy `socket` class so `isinstance` returns `False` without triggering `selectors`/`ipaddress`.
- `selectors`, `ipaddress`: pulled transitively by `socket`; stubbed as empty modules.
- `gi._option` / `optparse` (~3ms): `GLib.py` imports `gi._option` to expose GLib option parsing. Hints never uses it. Stubbing `gi._option` directly avoids loading `optparse`. All public names (`OptParseError`, `OptionGroup`, etc.) provided as dummy classes.
- Fixed overhead: **~23ms → ~20ms**

### 11. `85503d1` perf: stub pkgutil + lazy logger in atspi.py (~5ms more)
**Files:** `hints/hints.py`, `hints/backends/atspi.py`

- `pkgutil` stub (~3ms): `gi/__init__.py` calls `pkgutil.extend_path()` to find alternate gi installations. With a single install this is a no-op that costs ~3ms. Stub returns `__path__` unchanged.
- Lazy logger in `atspi.py` (~3ms): `atspi.py` had `import logging` at module level (called during the fixed-overhead import of `AtspiBackend`). Replaced with `_LazyLogger` proxy identical to `hints.py`. `import logging` now deferred until first `logger.*` call inside `get_children()` (the variable phase).
- Fixed overhead: **~20ms → ~16ms**

### 12. `92dabf1` fix: remove socket/selectors/ipaddress stubs that broke Gtk.main() + subprocess
**Files:** `hints/hints.py`

- The socket stub from commit 10 had a fatal runtime flaw: `gi/_ossighelper.py` calls `socket.socketpair()` at runtime *inside* `Gtk.main()` (not at import time), so the empty stub caused `AttributeError` when the overlay tried to display. Overlay showed nothing.
- `selectors` stub broke `subprocess.py` which does `selectors.SelectSelector` at module import time — `AttributeError` on any code path that used subprocess (including the opencv backend).
- `ipaddress` was an unnecessary dependent stub, also removed.
- **All three stubs removed.** Socket's ~1.6ms import cost is accepted.
- Hints overlay functional again. Fixed overhead: **~16ms → ~18ms** (net regression of ~2ms for correctness).

## Current Timing Breakdown (~18ms fixed overhead + variable tree walk)

| Phase | Time | Notes |
|---|---|---|
| gi stubs install | ~0 ms | ModuleType subclasses/lambdas in-process |
| config + utils import | ~3.5 ms | No GI at all |
| hints.py / get_ws import | ~0.7 ms | Lazy logger, deferred stdlib |
| X11 init | ~2.2 ms | Direct `LoadLibrary('libX11.so.6')`, no `ctypes.util` |
| Atspi backend import | ~10.5 ms | gi._gi C-ext (~3ms) + Atspi typelib (~6ms) + socket (~1.6ms); asyncio/pkgutil/optparse all stubbed |
| Atspi backend init | ~0 ms | Fast |
| `get_children()` | variable | atspi tree walk (GTK preloading in parallel) |
| GTK thread join | ~0 ms | Already finished during tree walk |
| overlay import | ~0 ms | Cached from preload thread |
| mouse + interceptor | ~1 ms | Only imported when needed |

## Remaining Optimization Opportunities

1. **gi._gi C extension (~3ms)**: Core GObject type system init inside the compiled `.so`. Hard to reduce without patching the binary or pre-loading the shared library via `LD_PRELOAD`.
2. **Atspi typelib loading (~6ms)**: Loading the Atspi introspection typelib + GLib typelib. Possibly reducible by pre-generating a cached Python binding or using ctypes for just the handful of Atspi functions needed.
3. **socket (~1.6ms)**: `gi/overrides/GLib.py` imports socket at module level for a Win32-only `isinstance` check. Cannot stub it — `gi/_ossighelper.py` calls `socket.socketpair()` at runtime inside `Gtk.main()`. One option: monkey-patch `GLib.py` to not import socket, then provide only the `socketpair` symbol via a custom stub that delegates to the real `socket` loaded lazily.
4. **config + utils (~3.5ms)**: JSON parse + deep-merge with default config. Could cache a compiled config object in `/tmp` (pickle or msgpack) across invocations.
5. **X11 init (~2.2ms)**: `XOpenDisplay` + window property lookups. Minimal further savings without changing the approach.
6. **Pre-warm daemon**: A persistent background process keeping GTK/Atspi loaded would eliminate all import costs — optimal but adds architectural complexity.
7. **get_children() tree walk**: The variable phase. Could potentially cache the tree across invocations using a UNIX socket to a long-lived Atspi listener process.

## Config
User config at `~/.config/hints/config.json`, deep-merged with `DEFAULT_CONFIG` in `hints/constants.py`.

## Dev Setup
- Editable install in venv: `/home/yogi/hints/venv`
- i3 keybinding: `Ctrl+Mod1+m` → `/home/yogi/hints/venv/bin/hints`
- Base (upstream) install: `/home/yogi/.local/share/uv/tools/hints/` (v0.0.7)
- **Important:** When benchmarking base vs dev, run base from `/tmp` to avoid CWD shadowing the dev source.
