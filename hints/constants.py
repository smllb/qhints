"""Global constant values."""

from os import path

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
_DEFAULT_CONFIG = None


def get_default_config() -> dict:
    """Lazily build and cache the default config.

    Defers importing Atspi and Gdk (~30 ms) until the config is actually
    needed, which allows the startup path to reach the atspi tree walk
    before paying this cost.
    """
    global _DEFAULT_CONFIG
    if _DEFAULT_CONFIG is not None:
        return _DEFAULT_CONFIG

    # Use raw integer values for GI enum constants so we don't need to
    # import the heavy gi + Atspi typelibs (~31 ms) at config-load time.
    # GI enums are int subclasses and compare as plain ints. Values are
    # stable protocol/AT-SPI constants.

    # Atspi.StateType
    _ATSPI_STATE_SENSITIVE = 24
    _ATSPI_STATE_SHOWING = 25
    _ATSPI_STATE_VISIBLE = 30

    # Atspi.CollectionMatchType
    _ATSPI_MATCH_ALL = 1
    _ATSPI_MATCH_NONE = 3

    # Atspi.Role
    _ATSPI_ROLE_PANEL = 39
    _ATSPI_ROLE_SECTION = 85
    _ATSPI_ROLE_HTML_CONTAINER = 25
    _ATSPI_ROLE_FRAME = 23
    _ATSPI_ROLE_MENU_BAR = 34
    _ATSPI_ROLE_TOOL_BAR = 63
    _ATSPI_ROLE_LIST = 31
    _ATSPI_ROLE_PAGE_TAB_LIST = 38
    _ATSPI_ROLE_DESCRIPTION_LIST = 121
    _ATSPI_ROLE_SCROLL_PANE = 49
    _ATSPI_ROLE_TABLE = 55
    _ATSPI_ROLE_GROUPING = 99
    _ATSPI_ROLE_STATIC = 116
    _ATSPI_ROLE_HEADING = 83
    _ATSPI_ROLE_PARAGRAPH = 73
    _ATSPI_ROLE_DESCRIPTION_VALUE = 123
    _ATSPI_ROLE_LANDMARK = 110
    _ATSPI_ROLE_FILLER = 20
    _ATSPI_ROLE_DESCRIPTION_TERM = 122

    # Gdk key/modifier constants — stable X11 protocol values.
    _GDK_KEY_ESCAPE = 65307            # Gdk.KEY_Escape
    _GDK_CONTROL_MASK = 4              # Gdk.ModifierType.CONTROL_MASK
    _GDK_MOD1_MASK = 8                 # Gdk.ModifierType.MOD1_MASK (Alt)

    _DEFAULT_CONFIG = {
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
                            _ATSPI_STATE_SENSITIVE,
                            _ATSPI_STATE_SHOWING,
                            _ATSPI_STATE_VISIBLE,
                        ],
                        "states_match_type": _ATSPI_MATCH_ALL,
                        "attributes": {},
                        "attributes_match_type": _ATSPI_MATCH_ALL,
                        "roles": [
                            # containers
                            _ATSPI_ROLE_PANEL,
                            _ATSPI_ROLE_SECTION,
                            _ATSPI_ROLE_HTML_CONTAINER,
                            _ATSPI_ROLE_FRAME,
                            _ATSPI_ROLE_MENU_BAR,
                            _ATSPI_ROLE_TOOL_BAR,
                            _ATSPI_ROLE_LIST,
                            _ATSPI_ROLE_PAGE_TAB_LIST,
                            _ATSPI_ROLE_DESCRIPTION_LIST,
                            _ATSPI_ROLE_SCROLL_PANE,
                            _ATSPI_ROLE_TABLE,
                            _ATSPI_ROLE_GROUPING,
                            # text
                            _ATSPI_ROLE_STATIC,
                            _ATSPI_ROLE_HEADING,
                            _ATSPI_ROLE_PARAGRAPH,
                            _ATSPI_ROLE_DESCRIPTION_VALUE,
                            # other
                            _ATSPI_ROLE_LANDMARK,
                            _ATSPI_ROLE_FILLER,
                            _ATSPI_ROLE_DESCRIPTION_TERM,
                        ],
                        "roles_match_type": _ATSPI_MATCH_NONE,
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
        "exit_key": _GDK_KEY_ESCAPE,
        "hover_modifier": _GDK_CONTROL_MASK,
        "grab_modifier": _GDK_MOD1_MASK,  # Alt
        "overlay_x_offset": 0,
        "overlay_y_offset": 0,
        "window_system": "",
    }
    return _DEFAULT_CONFIG
