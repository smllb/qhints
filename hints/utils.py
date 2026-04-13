from json import load
from typing import Any

from hints.constants import CONFIG_PATH, get_default_config

HintsConfig = dict[str, Any]


def merge_configs(source: HintsConfig, destination: HintsConfig) -> HintsConfig:
    """Deepmerge configs recursively.

    :param source: Source config.
    :param destination: Destination config.
    :return: Destination config.
    """
    for key, value in source.items():
        if isinstance(value, dict):
            node = destination.setdefault(key, {})
            merge_configs(value, node)
        else:
            destination[key] = value

    return destination


def load_config() -> HintsConfig:
    """Load Json config file.

    :return: config object.
    """
    config = {}

    try:
        with open(CONFIG_PATH, encoding="utf-8") as _f:
            config = load(_f)
    except FileNotFoundError:
        pass

    return merge_configs(config, get_default_config())
