"""Configuration and user directory manager for SpyQBank (Documents\\SpyQBank)."""

import os
import sys
import json
import shutil
import logging
from typing import Dict, Any

logger = logging.getLogger("SpyQBank.Config")


def get_documents_dir() -> str:
    """Resolve the user's real Documents directory (handles Windows locale & OneDrive redirection)."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            folder_id = GUID(
                0xFDD39AD0,
                0x238F,
                0x46AF,
                (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7),
            )
            shell32 = ctypes.windll.shell32
            ole32 = ctypes.windll.ole32
            shell32.SHGetKnownFolderPath.argtypes = [
                ctypes.POINTER(GUID),
                wintypes.DWORD,
                wintypes.HANDLE,
                ctypes.POINTER(ctypes.c_wchar_p),
            ]
            shell32.SHGetKnownFolderPath.restype = ctypes.c_long
            ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
            ole32.CoTaskMemFree.restype = None

            path_ptr = ctypes.c_wchar_p()
            hr = shell32.SHGetKnownFolderPath(
                ctypes.byref(folder_id), 0, None, ctypes.byref(path_ptr)
            )
            if hr == 0 and path_ptr.value:
                result = path_ptr.value
                ole32.CoTaskMemFree(path_ptr)
                return result
        except Exception as e:
            logger.warning(f"SHGetKnownFolderPath failed, falling back to ~/Documents: {e}")

    return os.path.join(os.path.expanduser("~"), "Documents")


def get_app_user_dir() -> str:
    """Return the writable user application directory: Documents\\SpyQBank."""
    app_dir = os.path.join(get_documents_dir(), "SpyQBank")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def get_downloads_dir() -> str:
    """Return the writable downloads directory: Documents\\SpyQBank\\downloads."""
    dl_dir = os.path.join(get_app_user_dir(), "downloads")
    os.makedirs(dl_dir, exist_ok=True)
    return dl_dir


def get_config_path() -> str:
    """Get the path to spyqbank.json inside Documents\\SpyQBank (with one-time legacy migration)."""
    config_path = os.path.join(get_app_user_dir(), "spyqbank.json")
    if not os.path.exists(config_path):
        # One-time migration from legacy directory next to executable / cwd if present
        legacy_base = (
            os.path.dirname(sys.executable)
            if getattr(sys, "frozen", False)
            else os.path.abspath(".")
        )
        legacy_path = os.path.join(legacy_base, "spyqbank.json")
        if os.path.exists(legacy_path) and os.path.abspath(legacy_path) != os.path.abspath(config_path):
            try:
                shutil.copy2(legacy_path, config_path)
                logger.info(f"Migrated legacy config from {legacy_path} to {config_path}")
            except Exception as e:
                logger.warning(f"Could not migrate legacy config: {e}")
    return config_path


DEFAULT_CONFIG: Dict[str, Any] = {
    "custom_header_title": "",
    "custom_footer_text": "",
    "trim_whitespace": True,
    "include_chapter_covers": True,
    "group_by_main_chapter": True,
    "include_table_of_contents": True,
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
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved config to {path}")
        return path
    except Exception as e:
        logger.error(f"Error saving config to {path}: {e}")
        raise e
