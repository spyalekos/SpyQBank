"""Configuration manager for SpyQBank (spyqbank.json)."""

import os
import sys
import json
import logging
from typing import Dict, Any

logger = logging.getLogger("SpyQBank.Config")

def get_config_path() -> str:
    """Get the path to spyqbank.json in the current working directory or executable directory."""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.abspath(".")
    return os.path.join(base_dir, "spyqbank.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "custom_header_title": "",
    "custom_footer_text": "",
}

def load_config() -> Dict[str, Any]:
    """Load settings from spyqbank.json."""
    path = get_config_path()
    if not os.path.exists(path):
        return dict(DEFAULT_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = dict(DEFAULT_CONFIG)
            merged.update(data)
            return merged
    except Exception as e:
        logger.error(f"Error loading config from {path}: {e}")
        return dict(DEFAULT_CONFIG)

def save_config(config_data: Dict[str, Any]) -> str:
    """Save settings to spyqbank.json."""
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved config to {path}")
        return path
    except Exception as e:
        logger.error(f"Error saving config to {path}: {e}")
        raise e
