"""Configuration management for zlib-cli."""

import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "zlib-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_FILE = CONFIG_DIR / "last_search.json"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "zlib"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    os.chmod(CONFIG_FILE, 0o600)


def get_download_dir() -> Path:
    config = load_config()
    d = Path(config.get("download_dir", str(DEFAULT_DOWNLOAD_DIR)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_last_search(results: list[dict]):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(results, f, ensure_ascii=False)


def load_last_search() -> list[dict]:
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return []
