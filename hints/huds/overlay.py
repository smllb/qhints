"""Overlay to display hints over an application window."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gi import require_foreign, require_version

from hints.mouse_enums import MouseButton
from hints.utils import HintsConfig

require_version("Gdk", "3.0")
require_version("Gtk", "3.0")
require_foreign("cairo")
from cairo import FONT_SLANT_NORMAL, FONT_WEIGHT_BOLD
from gi.repository import Gdk, Gtk

if TYPE_CHECKING:
    from cairo import Context

    from hints.child import Child


class OverlayWindow(Gtk.Window):
    """Composite widget to overlay hints over a window."""

    def __init__(
        self,
        x_pos: float,
        y_pos: float,
        width: float,
        height: float,
        config: HintsConfig,
        hints: dict[str, Child],
        mouse_action: dict[str, Any],
        is_wayland: bool = False,
    ):
        """Hint overlay constructor.

        :param x_pos: X window position.
        :param y_pos: Y window position.
        :param width: Window width.
        :param height: Window height.
        :param config: Hints config.
        :param hints: Hints to draw.
        :param mouse_action: Mouse action information.
        """
        super().__init__(Gtk.WindowType.POPUP)

        self.width = width
        self.height = height
        self.hints = hints
        self.hint_selector_state = ""
        self.mouse_action = mouse_action
        self.is_wayland = is_wayland

        # hint settings
        hints_config = config["hints"]
        self.hint_height = hints_config["hint_height"]
        self.hint_width_padding = hints_config["hint_width_padding"]

        self.hint_font_size = hints_config["hint_font_size"]
        self.hint_font_face = hints_config["hint_font_face"]
        self.hint_font_r = hints_config["hint_font_r"]
        self.hint_font_g = hints_config["hint_font_g"]
        self.hint_font_b = hints_config["hint_font_b"]
        self.hint_font_a = hints_config["hint_font_a"]

        self.hint_first_font_r = hints_config.get("hint_first_font_r", 0.85)
        self.hint_first_font_g = hints_config.get("hint_first_font_g", 0.1)
        self.hint_first_font_b = hints_config.get("hint_first_font_b", 0.1)
        self.hint_first_font_a = hints_config.get("hint_first_font_a", 1)
        self.hint_first_font_size_boost = hints_config.get("hint_first_font_size_boost", 3)
        self.hint_overlap_threshold = hints_config.get("hint_overlap_threshold", 50)

        self.hint_pressed_font_r = hints_config["hint_pressed_font_r"]
        self.hint_pressed_font_g = hints_config["hint_pressed_font_g"]
        self.hint_pressed_font_b = hints_config["hint_pressed_font_b"]
        self.hint_pressed_font_a = hints_config["hint_pressed_font_a"]
        self.hint_upercase = hints_config["hint_upercase"]

        self.hint_background_r = hints_config["hint_background_r"]
        self.hint_background_g = hints_config["hint_background_g"]
        self.hint_background_b = hints_config["hint_background_b"]
        self.hint_background_a = hints_config["hint_background_a"]

        self.hint_border_r = hints_config.get("hint_border_r", 0.78)
        self.hint_border_g = hints_config.get("hint_border_g", 0.72)
        self.hint_border_b = hints_config.get("hint_border_b", 0.36)
        self.hint_border_a = hints_config.get("hint_border_a", 1.0)
        self.hint_border_width = hints_config.get("hint_border_width", 1.0)
        self.hint_corner_radius = hints_config.get("hint_corner_radius", 3.0)
        self.hint_shadow = hints_config.get("hint_shadow", True)
        self.hint_shadow_r = hints_config.get("hint_shadow_r", 0.0)
        self.hint_shadow_g = hints_config.get("hint_shadow_g", 0.0)
        self.hint_shadow_b = hints_config.get("hint_shadow_b", 0.0)
        self.hint_shadow_a = hints_config.get("hint_shadow_a", 0.3)
        self.hint_shadow_offset_x = hints_config.get("hint_shadow_offset_x", 1)
        self.hint_shadow_offset_y = hints_config.get("hint_shadow_offset_y", 1)

        # key settings
        self.exit_key = config["exit_key"]
        self.hover_modifier = config["hover_modifier"]
        self.grab_modifier = config["grab_modifier"]

        self.hints_drawn_offsets: dict[str, tuple[float, float]] = {}

        # composite setup
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        self.set_visual(visual)

        # window setup
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_accept_focus(True)
        self.set_sensitive(True)
        self.set_default_size(self.width, self.height)
        self.move(x_pos, y_pos)

        self.drawing_area = Gtk.DrawingArea()

        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self.on_key_press)
        self.connect("show", self.on_show)
        self.drawing_area.connect("draw", self.on_draw)

        self.current_snippet = None

        self.add(self.drawing_area)

    def on_draw(self, _, cr: Context):
        """Draw hints.

        :param cr: Cairo Context.
        """
        hint_height = self.hint_height

        cr.select_font_face(self.hint_font_face, FONT_SLANT_NORMAL, FONT_WEIGHT_BOLD)
        cr.set_font_size(self.hint_font_size)

        # Pre-compute hint bounding boxes for overlap detection.
        hint_rects: dict[str, tuple[float, float, float, float]] = {}
        for hint_value, child in self.hints.items():
            x_loc, y_loc = child.relative_position
            if x_loc >= 0 and y_loc >= 0:
                utf8 = hint_value.upper() if self.hint_upercase else hint_value
                x_bearing, _, width, _, _, _ = cr.text_extents(utf8)
                hint_width = width + self.hint_width_padding
                hx = x_loc + child.width / 2 - hint_width / 2
                hy = y_loc + child.height / 2 - hint_height / 2
                hint_rects[hint_value] = (hx, hy, hint_width, hint_height)

        def overlap_fraction(a: tuple[float, float, float, float],
                             b: tuple[float, float, float, float]) -> float:
            """Return overlap as a fraction of the smaller rect's area."""
            ax, ay, aw, ah = a
            bx, by, bw, bh = b
            ox = max(0, min(ax + aw, bx + bw) - max(ax, bx))
            oy = max(0, min(ay + ah, by + bh) - max(ay, by))
            overlap_area = ox * oy
            smaller_area = min(aw * ah, bw * bh)
            return overlap_area / smaller_area if smaller_area > 0 else 0

        # Keep only hints that don't heavily overlap with already-accepted ones.
        # hint_overlap_threshold: 0 = show all (no filtering), 100 = very aggressive.
        overlap_limit = (100 - self.hint_overlap_threshold) / 100.0
        accepted: list[str] = []
        for hv in hint_rects:
            if self.hint_overlap_threshold == 0:
                accepted.append(hv)
                continue
            dominated = False
            for av in accepted:
                if overlap_fraction(hint_rects[hv], hint_rects[av]) > overlap_limit:
                    dominated = True
                    break
            if not dominated:
                accepted.append(hv)

        visible_hints = {hv: self.hints[hv] for hv in accepted}

        for hint_value, child in visible_hints.items():
            x_loc, y_loc = child.relative_position
            if x_loc >= 0 and y_loc >= 0:
                cr.save()
                utf8 = hint_value.upper() if self.hint_upercase else hint_value
                hint_state = (
                    self.hint_selector_state.upper()
                    if self.hint_upercase
                    else self.hint_selector_state
                )

                x_bearing, y_bearing, width, height, _, _ = cr.text_extents(utf8)
                hint_width = width + self.hint_width_padding

                cr.new_path()
                # offset to bring top left corner of a hint to the correct possition
                # so that the hint is centered on the object
                hint_x_offset = child.width / 2 - hint_width / 2
                hint_y_offset = child.height / 2 - hint_height / 2

                hint_x = x_loc + hint_x_offset
                hint_y = y_loc + hint_y_offset

                cr.translate(hint_x, hint_y)
                # adding offsets so that clicks sent happen in center of hints
                # (matching the position of hints on elements)
                self.hints_drawn_offsets[hint_value] = (
                    hint_x_offset + hint_width / 2,
                    hint_y_offset + hint_height / 2,
                )

                r = self.hint_corner_radius

                # draw shadow
                if self.hint_shadow:
                    sx = self.hint_shadow_offset_x
                    sy = self.hint_shadow_offset_y
                    cr.new_path()
                    cr.arc(sx + r, sy + r, r, 3.14159, 3.14159 * 1.5)
                    cr.arc(sx + hint_width - r, sy + r, r, 3.14159 * 1.5, 0)
                    cr.arc(sx + hint_width - r, sy + hint_height - r, r, 0, 3.14159 * 0.5)
                    cr.arc(sx + r, sy + hint_height - r, r, 3.14159 * 0.5, 3.14159)
                    cr.close_path()
                    cr.set_source_rgba(
                        self.hint_shadow_r,
                        self.hint_shadow_g,
                        self.hint_shadow_b,
                        self.hint_shadow_a,
                    )
                    cr.fill()

                # draw rounded background
                cr.new_path()
                cr.arc(r, r, r, 3.14159, 3.14159 * 1.5)
                cr.arc(hint_width - r, r, r, 3.14159 * 1.5, 0)
                cr.arc(hint_width - r, hint_height - r, r, 0, 3.14159 * 0.5)
                cr.arc(r, hint_height - r, r, 3.14159 * 0.5, 3.14159)
                cr.close_path()
                cr.set_source_rgba(
                    self.hint_background_r,
                    self.hint_background_g,
                    self.hint_background_b,
                    self.hint_background_a,
                )
                cr.fill_preserve()

                # draw border
                cr.set_source_rgba(
                    self.hint_border_r,
                    self.hint_border_g,
                    self.hint_border_b,
                    self.hint_border_a,
                )
                cr.set_line_width(self.hint_border_width)
                cr.stroke()

                hint_text_position = (
                    (hint_width / 2) - (width / 2 + x_bearing),
                    (hint_height / 2) - (height / 2 + y_bearing),
                )

                # Draw hint text character by character.
                # First letter: red + slightly larger. Rest: normal color.
                text_x, text_y = hint_text_position
                pressed_len = len(hint_state)

                for ci, ch in enumerate(utf8):
                    if ci < pressed_len:
                        # Already-typed character — pressed color.
                        cr.set_font_size(self.hint_font_size)
                        cr.set_source_rgba(
                            self.hint_pressed_font_r,
                            self.hint_pressed_font_g,
                            self.hint_pressed_font_b,
                            self.hint_pressed_font_a,
                        )
                    elif ci == 0:
                        # First letter — red + larger.
                        cr.set_font_size(
                            self.hint_font_size + self.hint_first_font_size_boost
                        )
                        cr.set_source_rgba(
                            self.hint_first_font_r,
                            self.hint_first_font_g,
                            self.hint_first_font_b,
                            self.hint_first_font_a,
                        )
                    else:
                        # Remaining letters — normal color.
                        cr.set_font_size(self.hint_font_size)
                        cr.set_source_rgba(
                            self.hint_font_r,
                            self.hint_font_g,
                            self.hint_font_b,
                            self.hint_font_a,
                        )
                    cr.move_to(text_x, text_y)
                    cr.show_text(ch)
                    text_x += cr.text_extents(ch).x_advance

                # Reset font size for next hint.
                cr.set_font_size(self.hint_font_size)

                cr.close_path()
                cr.restore()

    def update_hints(self, next_char: str):
        """Update hints on screen to eliminate options.

        :param next_char: Next character for hint_selector_state.
        """

        updated_hints = {
            hint: child
            for hint, child in self.hints.items()
            if hint.startswith(self.hint_selector_state + next_char)
        }

        if updated_hints:
            self.hints = updated_hints
            self.hint_selector_state += next_char

        self.drawing_area.queue_draw()

    def on_key_press(self, _, event):
        """Handle key presses :param event: Event object."""
        keymap = Gdk.Keymap.get_for_display(Gdk.Display.get_default())

        # if keyval is bound, keyval, effective_group, level, consumed_modifiers
        *_, consumed_modifiers = keymap.translate_keyboard_state(
            event.hardware_keycode,
            Gdk.ModifierType(event.state & ~Gdk.ModifierType.LOCK_MASK),
            1,
        )

        modifiers = (
            # current state, default mod mask, consumed modifiers
            event.state
            & Gtk.accelerator_get_default_mod_mask()
            & ~consumed_modifiers
        )

        keyval_lower = Gdk.keyval_to_lower(event.keyval)

        if keyval_lower == self.exit_key:
            Gtk.main_quit()

        if modifiers == self.hover_modifier:
            self.mouse_action.update({"action": "hover"})

        if modifiers == self.grab_modifier:
            self.mouse_action.update({"action": "grab"})

        if keyval_lower != event.keyval:
            self.mouse_action.update({"action": "click", "button": MouseButton.RIGHT})

        hint_chr = chr(keyval_lower)

        if hint_chr.isdigit():
            self.mouse_action.update(
                {"repeat": int(f"{self.mouse_action.get('repeat', '')}{hint_chr}")}
            )

        self.update_hints(hint_chr)

        if len(self.hints) == 1:
            Gdk.keyboard_ungrab(event.time)
            self.destroy()
            x, y = self.hints[self.hint_selector_state].absolute_position
            x_offset, y_offset = self.hints_drawn_offsets[self.hint_selector_state]
            self.mouse_action.update(
                {
                    "action": self.mouse_action.get("action", "click"),
                    "x": x + x_offset,
                    "y": y + y_offset,
                    "repeat": self.mouse_action.get("repeat", 1),
                    "button": self.mouse_action.get("button", MouseButton.LEFT),
                }
            )

    def on_show(self, window):
        """Setup window on show.

        Force keyboard grab to listen for keybaord events. Hide mouse so
        it does not block hints.

        :param window: Gtk Window object.
        """

        while (
            not self.is_wayland
            and Gdk.keyboard_grab(window.get_window(), False, Gdk.CURRENT_TIME)
            != Gdk.GrabStatus.SUCCESS
        ):
            pass

        Gdk.Window.set_cursor(
            self.get_window(),  # Gdk Window object
            Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "none"),
        )
