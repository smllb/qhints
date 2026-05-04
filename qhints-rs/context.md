# qhints-rs — Development Context

Rust rewrite of [hints](https://github.com/AlfredoSequeida/hints) — keyboard-driven UI navigation for Linux.

## Architecture

```
src/
├── main.rs              # Entry: CLI, lock file, orchestrates backends → hints → overlay
├── config.rs            # Config loading from ~/.config/hints/config.json, HintStyle, KEYBOARD_ZONES
├── hints.rs             # Spatial zone-based hint label generation with overflow redistribution
├── child.rs             # Child struct (relative/absolute position, width, height)
├── backend/
│   ├── mod.rs
│   ├── atspi.rs         # AT-SPI async tree walk via D-Bus (primary backend)
│   └── imageproc.rs     # CV fallback: screenshot → Canny → BFS connected components
├── overlay/
│   ├── mod.rs           # GTK3 overlay window, keyboard grab, key event handling
│   └── drawing.rs       # Cairo rendering: rounded rects, per-character text, overlap culling
└── window_system/
    ├── mod.rs           # WindowInfo struct + WindowSystem trait
    └── x11.rs           # X11 backend via x11rb
```

## Flow

1. Acquire lock (`/tmp/qhints.lock` via flock) — prevents re-entry
2. Init X11 → get focused window info (extents, PID, WM_CLASS)
3. Try AT-SPI backend (async, 150ms timeout) — walks a11y tree with state/role filtering
4. If AT-SPI returns empty → imageproc fallback (screenshot → edge detection → BFS)
5. Compute hints — bucket children into 3×3 screen zones, map to keyboard zones, redistribute overflow
6. Show GTK overlay — draw hint labels centered on elements, handle keypresses, cull overlaps
7. On match → spawn `xdotool mousemove/click`

## Recent Fixes

### `fix/overlay-freeze-grab-race`
- Log keyboard grab result instead of silently discarding
- Mouse click dismissal as safety net when grab fails
- Release grab on Escape (was only in hint-match path)
- Handle missing GdkWindow gracefully (no more unwrap panic)
- Narrow grab to `KEYBOARD` only instead of `ALL`
- `connect_destroy` handler ensures main loop exits on external close

### `fix/hint-placement-culling`
- Removed `cull_and_relabel()` — was discarding `get_hints()` output and reassigning labels without overflow redistribution
- Hints centered on child elements (was using raw top-left corner)
- Overlap culling uses configurable `hint_overlap_threshold` (default 60 → 40% overlap allowed) instead of hardcoded 0.05
- Removed duplicate `get_zone()` from `main.rs`

### `fix/cleanup-warnings`
- Removed unused `total_start` param from `hint_mode`
- Removed unused `min_dim`/`max_w`/`max_h` in `imageproc.rs`
- Removed unused `cairo::Context` import in `overlay/mod.rs`
- Deleted dead `mouse.rs`

## Key Differences from Python Version

| Aspect | Python | Rust |
|--------|--------|------|
| Window systems | X11 + Wayland (sway, Hyprland, plasmashell, gnome-shell) | X11 only |
| Backends | AT-SPI + OpenCV | AT-SPI + imageproc |
| Mouse device | uinput via unix socket | xdotool subprocess |
| Overlap culling | In draw, configurable threshold | In draw, configurable threshold |
| Hint assignment | Single `get_hints()` pass | Single `get_hints()` pass (was two before fix) |

## Config

At `~/.config/hints/config.json` — same format as Python version. Merged over defaults in `config.rs`.
