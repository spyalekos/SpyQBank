"""IEP Trapeza API Client."""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
import requests

from src.models import SchoolType, QuestionItem

logger = logging.getLogger("SpyQBank.API")

BASE_API_URL = "https://api.trapeza.registry.digitalschool.gov.gr/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


class IepApiClient:
    """Client for IEP Question Bank REST API."""

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def get_school_tree(self) -> List[SchoolType]:
        """Fetch the full hierarchy of school types, classes, and subjects."""
        url = f"{BASE_API_URL}/public/school/type/tree"
        logger.info(f"Fetching tree from {url}")
        resp = self.session.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        school_types = [
            SchoolType.from_dict(st)
            for st in data.get("school_types", [])
        ]
        return school_types

    def get_subject_items(
        self,
        school_type_id: int,
        class_id: int,
        subject_id: int,
        up_to_last_chapter: bool = False
    ) -> List[QuestionItem]:
        """Fetch all question items for a given subject."""
        up_param = "true" if up_to_last_chapter else "false"
        url = (
            f"{BASE_API_URL}/public/school/type/{school_type_id}"
            f"/class/{class_id}/subject/{subject_id}/items?up_to_last_chapter={up_param}"
        )
        logger.info(f"Fetching subject items from {url}")
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        raw_items = data.get("items", [])
        items = [
            QuestionItem.from_dict(it, subject_id=subject_id)
            for it in raw_items
        ]
        # Sort items by question number (1, 2, 3, 4) and then ID
        items.sort(key=lambda x: (x.question or 99, x.id))
        return items

    def download_file(self, url: str, destination_path: str, force: bool = False) -> str:
        """Download a file (PDF/DOCX) to a destination path if not already cached."""
        if os.path.exists(destination_path) and os.path.getsize(destination_path) > 0 and not force:
            logger.debug(f"File already cached: {destination_path}")
            return destination_path

        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        temp_path = destination_path + ".tmp"

        logger.info(f"Downloading {url} -> {destination_path}")
        resp = self.session.get(url, stream=True, timeout=40)
        resp.raise_for_status()

        with open(temp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)

        if os.path.exists(destination_path):
            os.remove(destination_path)
        os.rename(temp_path, destination_path)
        return destination_path
