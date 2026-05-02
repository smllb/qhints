from typing import Any

from hints.constants import CONFIG_PATH, get_default_config

HintsConfig = dict[str, Any]

# Marshal cache path keyed by config.json mtime to auto-invalidate.
_CACHE_DIR = "/tmp"


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
    """Load config with marshal-based caching.

    On first run (or when config.json changes), parse JSON + deep-merge
    and write a marshal cache to /tmp.  Subsequent runs load the pre-built
    dict from cache (~0.3 ms vs ~3.5 ms).

    :return: config object.
    """
    from os.path import exists, getmtime, join

    config_mtime = 0.0
    try:
        config_mtime = getmtime(CONFIG_PATH)
    except OSError:
        pass  # no user config file

    cache_path = join(_CACHE_DIR, f"qhints_config_{int(config_mtime * 1000)}.dat")

    # Try loading from cache first.
    if exists(cache_path):
        try:
            import marshal
            with open(cache_path, "rb") as f:
                return marshal.load(f)
        except Exception:
            pass  # corrupt cache, rebuild

    # Cache miss — build from scratch.
    from json import load

    config = {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as _f:
            config = load(_f)
    except FileNotFoundError:
        pass

    merged = merge_configs(config, get_default_config())

    # Write cache (best-effort, non-fatal).
    try:
        import marshal
        with open(cache_path, "wb") as f:
            marshal.dump(merged, f)
    except Exception:
        pass

    return merged
