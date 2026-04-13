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

## Current Timing Breakdown (~38ms fixed overhead + variable tree walk)

| Phase | Time | Notes |
|---|---|---|
| config + utils import | ~3.5 ms | No GI at all |
| hints.py / get_ws import | ~0.7 ms | Lazy logger, deferred stdlib |
| X11 init | ~2.2 ms | Direct `LoadLibrary('libX11.so.6')`, no `ctypes.util` |
| Atspi backend import | ~32 ms | gi bootstrap + Atspi typelib (dominates) |
| Atspi backend init | ~0 ms | Fast |
| `get_children()` | variable | atspi tree walk (GTK preloading in parallel) |
| GTK thread join | ~0 ms | Already finished during tree walk |
| overlay import | ~0 ms | Cached from preload thread |
| mouse + interceptor | ~1 ms | Only imported when needed |

## Remaining Optimization Opportunities

1. **Atspi gi bootstrap (~32ms)**: This is now the single largest serial cost. Could potentially use ctypes for Atspi too, but the API surface is much larger than X11.
2. **Cache window system class**: The WM doesn't change between invocations. A one-line file in `/tmp/hints_wm` could skip detection entirely on subsequent runs.
3. **Pre-warm with a daemon**: A persistent background process that keeps GTK/Atspi loaded and listens for activation signals would eliminate all import costs.
4. **get_children()**: The atspi tree walk itself. Time varies with window complexity. Hard to optimize without changing the traversal algorithm or caching the tree.

## Config
User config at `~/.config/hints/config.json`, deep-merged with `DEFAULT_CONFIG` in `hints/constants.py`.

## Dev Setup
- Editable install in venv: `/home/yogi/hints/venv`
- i3 keybinding: `Ctrl+Mod1+m` → `/home/yogi/hints/venv/bin/hints`
- Base (upstream) install: `/home/yogi/.local/share/uv/tools/hints/` (v0.0.7)
- **Important:** When benchmarking base vs dev, run base from `/tmp` to avoid CWD shadowing the dev source.
