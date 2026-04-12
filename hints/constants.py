"""Global constant values."""

from os import path

from gi import require_version

require_version("Gdk", "3.0")
require_version("Atspi", "2.0")
from gi.repository import Atspi, Gdk

# QWERTY keyboard key positions normalized to [0, 1] x [0, 1].
# Used for spatial hint assignment: keyboard topology maps to screen position.
# Accounts for standard row stagger (home row offset +0.25, bottom row +0.75).
KEYBOARD_POSITIONS: dict[str, tuple[float, float]] = {
    # Top row (y=0.0)
    "q": (0.000, 0.0), "w": (0.111, 0.0), "e": (0.222, 0.0),
    "r": (0.333, 0.0), "t": (0.444, 0.0), "y": (0.556, 0.0),
    "u": (0.667, 0.0), "i": (0.778, 0.0), "o": (0.889, 0.0),
    "p": (1.000, 0.0),
    # Home row (y=0.5)
    "a": (0.028, 0.5), "s": (0.139, 0.5), "d": (0.250, 0.5),
    "f": (0.361, 0.5), "g": (0.472, 0.5), "h": (0.583, 0.5),
    "j": (0.694, 0.5), "k": (0.806, 0.5), "l": (0.917, 0.5),
    # Bottom row (y=1.0)
    "z": (0.083, 1.0), "x": (0.194, 1.0), "c": (0.306, 1.0),
    "v": (0.417, 1.0), "b": (0.528, 1.0), "n": (0.639, 1.0),
    "m": (0.750, 1.0),
}

CONFIG_PATH = path.join(path.expanduser("~"), ".config/hints/config.json")
MOUSE_GRAB_PAUSE = 0.2
UNIX_DOMAIN_SOCKET_FILE = "/tmp/hints.socket"
SOCKET_MESSAGE_SIZE = 1024
DEFAULT_CONFIG = {
    "hints": {
        "hint_height": 30,
        "hint_width_padding": 10,
        "hint_font_size": 15,
        "hint_font_face": "Sans",
        "hint_font_r": 0,
        "hint_font_g": 0,
        "hint_font_b": 0,
        "hint_font_a": 1,
        "hint_pressed_font_r": 0.7,
        "hint_pressed_font_g": 0.7,
        "hint_pressed_font_b": 0.4,
        "hint_pressed_font_a": 1,
        "hint_upercase": True,
        "hint_background_r": 1,
        "hint_background_g": 1,
        "hint_background_b": 0.5,
        "hint_background_a": 0.8,
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
