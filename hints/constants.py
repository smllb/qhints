"""Global constant values."""

from os import path

from gi import require_version

require_version("Gdk", "3.0")
require_version("Atspi", "2.0")
from gi.repository import Atspi, Gdk

# 3x3 screen zone to keyboard key mapping.
# The screen is divided into a 3x3 grid. Each zone maps to keys that sit in
# the same region on a QWERTY keyboard, so the spatial relationship is
# immediately obvious:
#   Screen Left   → keyboard left   (q/w/e, a/s/d, z/x/c)
#   Screen Center → keyboard center (r/t/y, f/g/h, v/b)
#   Screen Right  → keyboard right  (u/i/o/p, n/m/l, j/k)
# Row on keyboard (top/home/bottom) maps to row on screen (top/mid/bottom).
KEYBOARD_ZONES: list[list[str]] = [
    # (row, col)  →  keys assigned to that zone
    # Row 0 – top third of screen
    ["qwe", "rty", "uiop"],
    # Row 1 – middle third of screen
    ["asd", "fgh", "nml"],
    # Row 2 – bottom third of screen
    ["zxc", "vb", "jk"],
]

CONFIG_PATH = path.join(path.expanduser("~"), ".config/hints/config.json")
MOUSE_GRAB_PAUSE = 0.2
UNIX_DOMAIN_SOCKET_FILE = "/tmp/hints.socket"
SOCKET_MESSAGE_SIZE = 1024
DEFAULT_CONFIG = {
    "hints": {
        "hint_height": 20,
        "hint_width_padding": 10,
        "hint_font_size": 14,
        "hint_font_face": "monospace",
        "hint_font_r": 0.16,
        "hint_font_g": 0.16,
        "hint_font_b": 0.16,
        "hint_font_a": 1,
        "hint_first_font_r": 0.85,
        "hint_first_font_g": 0.1,
        "hint_first_font_b": 0.1,
        "hint_first_font_a": 1,
        "hint_first_font_size_boost": 0,
        "hint_overlap_threshold": 60,
        "hint_pressed_font_r": 0.45,
        "hint_pressed_font_g": 0.75,
        "hint_pressed_font_b": 0.25,
        "hint_pressed_font_a": 1,
        "hint_upercase": True,
        "hint_background_r": 1.0,
        "hint_background_g": 0.95,
        "hint_background_b": 0.55,
        "hint_background_a": 0.95,
        "hint_border_r": 0.78,
        "hint_border_g": 0.72,
        "hint_border_b": 0.36,
        "hint_border_a": 1.0,
        "hint_border_width": 1.0,
        "hint_corner_radius": 6.0,
        "hint_shadow": True,
        "hint_shadow_r": 0.0,
        "hint_shadow_g": 0.0,
        "hint_shadow_b": 0.0,
        "hint_shadow_a": 0.3,
        "hint_shadow_offset_x": 1,
        "hint_shadow_offset_y": 1,
    },
    "backends": {
        "enable": ["atspi", "opencv"],
        "atspi": {
            "application_rules": {
                "default": {
                    "scale_factor": 1,
                    "states": [
                        Atspi.StateType.SENSITIVE,
                        Atspi.StateType.SHOWING,
                        Atspi.StateType.VISIBLE,
                    ],
                    "states_match_type": Atspi.CollectionMatchType.ALL,
                    "attributes": {},
                    "attributes_match_type": Atspi.CollectionMatchType.ALL,
                    "roles": [
                        # containers
                        Atspi.Role.PANEL,
                        Atspi.Role.SECTION,
                        Atspi.Role.HTML_CONTAINER,
                        Atspi.Role.FRAME,
                        Atspi.Role.MENU_BAR,
                        Atspi.Role.TOOL_BAR,
                        Atspi.Role.LIST,
                        Atspi.Role.PAGE_TAB_LIST,
                        Atspi.Role.DESCRIPTION_LIST,
                        Atspi.Role.SCROLL_PANE,
                        Atspi.Role.TABLE,
                        Atspi.Role.GROUPING,
                        # text
                        Atspi.Role.STATIC,
                        Atspi.Role.HEADING,
                        Atspi.Role.PARAGRAPH,
                        Atspi.Role.DESCRIPTION_VALUE,
                        # other
                        Atspi.Role.LANDMARK,
                        Atspi.Role.FILLER,
                        Atspi.Role.DESCRIPTION_TERM,
                    ],
                    "roles_match_type": Atspi.CollectionMatchType.NONE,
                },
            },
        },
        "opencv": {
            "application_rules": {
                "default": {
                    "kernel_size": 6,
                    "canny_min_val": 100,
                    "canny_max_val": 200,
                }
            },
        },
    },
    "alphabet": "asdfgqwertzxcvbhjklyuiopnm",
    "mouse_move_left": "h",
    "mouse_move_right": "l",
    "mouse_move_up": "k",
    "mouse_move_down": "j",
    "mouse_scroll_left": "h",
    "mouse_scroll_right": "l",
    "mouse_scroll_up": "k",
    "mouse_scroll_down": "j",
    "mouse_move_pixel": 10,
    "mouse_move_pixel_sensitivity": 10,
    "mouse_move_rampup_time": 0.5,
    "mouse_scroll_pixel": 5,
    "mouse_scroll_pixel_sensitivity": 5,
    "mouse_scroll_rampup_time": 0.5,
    "exit_key": Gdk.KEY_Escape,
    "hover_modifier": Gdk.ModifierType.CONTROL_MASK,
    "grab_modifier": Gdk.ModifierType.MOD1_MASK,  # Alt
    "overlay_x_offset": 0,
    "overlay_y_offset": 0,
    "window_system": "",
}
