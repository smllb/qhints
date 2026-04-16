# qhints (quantum hints)

![...](https://imgur.com/dP3T5pG.png)
Disclaimer:

All changes were done through Github Copilot (Claude Opus 4.6) and honestly i don't advocate for a merge with the source, but it might serve as a reference in future implementations. I had some ideas the other day and gave it a run to see what would happen. The current fork solves some issues i personally had with hints and they are listed below.

---


A performance-focused fork of [AlfredoSequeida/hints](https://github.com/AlfredoSequeida/hints) — keyboard-driven GUI navigation for Linux. Type hint labels to click, drag, scroll, or hover anywhere on screen without touching the mouse.

> **Upstream:** [AlfredoSequeida/hints](https://github.com/AlfredoSequeida/hints) — original concept, daemon architecture, backends, and wiki. Go there for the full backstory and video demos.

---

## What's different from upstream

### Spatial letter assignment
Hint labels are chosen so that the key you press is physically located on the same region of your keyboard as the target on screen. The screen is divided into a 3×3 grid that mirrors the keyboard layout:

```
Screen region  →  keyboard keys used
─────────────────────────────────────
top-left       →  q w e
top-center     →  r t y
top-right      →  u i o p
mid-left       →  a s d
mid-center     →  f g h
mid-right      →  n m l
bot-left       →  z x c
bot-center     →  v b
bot-right      →  j k
```

A button in the top-right corner of a window will always get a label from `uiop`, so your muscle memory builds spatially rather than arbitrarily.

### Overflow redistribution
When one screen region has more clickable targets than its key budget allows, excess targets are redistributed to the nearest neighbouring region that still has spare capacity. Targets closest to the neighbour's center move first to preserve spatial coherence. This minimises three-character hints — they only appear when the total number of targets exceeds the global two-character capacity (676).

### Vimium-style hint appearance
Hints look like Vimium browser hints: compact yellow badges with a monospace font, rounded corners, a thin border, and a subtle drop shadow. The first (untyped) character is highlighted in red; already-typed characters turn green.

### Overlap filtering
Hints that overlap significantly with another hint are dropped before display, keeping the overlay readable even on dense UIs. The threshold is configurable (`hint_overlap_threshold`, 0–100, default 60).

### No white border on activation
Upstream rendered a visible white border/shadow around the focused window every time hints appeared, caused by a `Gtk.Frame` + `Gtk.VPaned` wrapper around the drawing area. Removed — the overlay is now clean and borderless.

### Startup performance
The critical path from keybinding press to hints visible has been heavily optimised. The fixed import overhead (everything before the AT-SPI tree walk) is roughly **~18 ms** vs. the upstream baseline of several hundred milliseconds. Key techniques:

- **asyncio stub** — `gi._gi` unconditionally imports asyncio (~23 ms) for GLib event-loop integration hints never uses. A minimal three-symbol stub is installed in `sys.modules` before any gi import.
- **gi._option / optparse stub** — GLib option-parsing extension (~3 ms) stubbed out entirely; hints never uses it.
- **pkgutil stub** — `gi/__init__.py` calls `pkgutil.extend_path()` (~3 ms) to find alternate gi installs; stubbed to a no-op.
- **Lazy loggers** — `import logging` (~5 ms) deferred to first actual log call via a proxy class in both `hints.py` and `atspi.py`.
- **Ctypes X11** — `x11.py` rewritten to use ctypes directly instead of gi+Wnck (~59 ms → ~3 ms).
- **Deferred stdlib** — `argparse`, `logging.basicConfig`, and type-annotation imports moved out of the module-level critical path.
- **Threaded GTK preload** — GTK bootstrap (~30 ms) runs in a daemon thread that overlaps with the AT-SPI tree walk, hiding most of its cost.
- **/proc WM detection** — Wayland compositor detection reads `/proc/*/comm` directly instead of spawning `ps | grep`.

---

## Usage

```
hints
```

With hints visible, type the label characters shown on screen. Modifier keys change the action:

| Keys | Action |
|---|---|
| label | left click |
| number + label | click N times |
| <kbd>Shift</kbd> + label | right click |
| <kbd>Alt</kbd> + label | drag |
| <kbd>Ctrl</kbd> + label | hover |
| <kbd>h</kbd> <kbd>j</kbd> <kbd>k</kbd> <kbd>l</kbd> | scroll / move mouse (vim bindings) |
| <kbd>Esc</kbd> | dismiss |

> **Wayland note:** dragging may not work on all compositors due to how they handle overlay windows.

---

## Installing

### System requirements

1. **Compositor** — you need compositing enabled so the transparent overlay renders correctly. Without it the overlay covers the entire screen opaquely.

2. **Accessibility** — enable AT-SPI for your system. Many desktop environments do this automatically. If hints finds no targets, add to `/etc/environment`:

   ```
   ACCESSIBILITY_ENABLED=1
   GTK_MODULES=gail:atk-bridge
   OOO_FORCE_DESKTOP=gnome
   GNOME_ACCESSIBILITY=1
   QT_ACCESSIBILITY=1
   QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1
   ```

3. **uinput** — the hints daemon uses uinput for mouse actions:

   ```
   sudo modprobe uinput && echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf
   ```

4. **Daemon** — if you are not using the latest pipx, set `HINTS_EXPECTED_BIN_DIR` before installing so `setup.py` can write the correct service file path (e.g. `export HINTS_EXPECTED_BIN_DIR="$HOME/.local/bin"`).

### Install from this fork

```bash
pipx install git+https://github.com/smllb/qhints.git
```

Or clone and install in editable mode for development (see below).

### Distro dependencies

**Ubuntu**
```bash
sudo apt update && \
    sudo apt install git libgirepository1.0-dev gcc libcairo2-dev pkg-config python3-dev gir1.2-gtk-4.0 pipx cmake libdbus-1-dev && \
    [ "$XDG_SESSION_TYPE" = "wayland" ] && sudo apt install gtk-layer-shell grim
```

**Fedora**
```bash
sudo dnf install git gcc gobject-introspection-devel cairo-gobject-devel pkg-config python3-devel gtk4 pipx && \
    [ "$XDG_SESSION_TYPE" = "wayland" ] && sudo dnf install gtk-layer-shell grim
```

**Arch**
```bash
sudo pacman -Sy && \
    sudo pacman -S git python cairo pkgconf gobject-introspection gtk4 python-pipx && \
    { [ "$XDG_SESSION_TYPE" = "wayland" ] && sudo pacman -S gtk-layer-shell grim || sudo pacman -S libwnck3; }
```

After installing, source your shell config or open a new terminal.

### Window manager setup

Follow the upstream [Window Manager and Desktop Environment Setup Guide](https://github.com/AlfredoSequeida/hints/wiki/Window-Manager-and-Desktop-Environment-Setup-Guide) — the keybinding and compositor setup is the same.

---

## Configuration

User config lives at `~/.config/hints/config.json` and is deep-merged with the defaults. See the upstream [Wiki](https://github.com/AlfredoSequeida/hints/wiki) for the full option reference. Fork-specific defaults:

| Key | Default | Notes |
|---|---|---|
| `hint_height` | `20` | compact badge height (px) |
| `hint_font_size` | `14` | monospace font size |
| `hint_font_face` | `monospace` | |
| `hint_corner_radius` | `6.0` | rounded corners |
| `hint_shadow` | `true` | subtle drop shadow |
| `hint_first_font_r/g/b` | red | first character highlight colour |
| `hint_pressed_font_r/g/b` | green | already-typed character colour |
| `hint_overlap_threshold` | `60` | 0–100; hints overlapping more than this % are dropped |

---

## Development

```bash
git clone https://github.com/smllb/qhints.git
cd qhints
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

Run from `/tmp` when benchmarking to avoid the CWD shadowing the dev source:

```bash
cd /tmp && hints
```

**Trapped by a keyboard grab?** Switch to a virtual terminal with <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>F2</kbd>, log in, run `killall hints`, then return with <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>F1</kbd>.

---

## Credits

All original work by [Alfredo Sequeida](https://github.com/AlfredoSequeida). This fork adds spatial hint assignment, performance optimisations, overlap filtering, and UI polish.
