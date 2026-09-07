"""IEP Trapeza API Client."""

import os
import json
import random
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
        # Sort items by question number (2, 4) and then ID
        items.sort(key=lambda x: (x.question or 99, x.id))
        return items

    def download_file(self, url: str, destination_path: str, force: bool = False, max_retries: int = 3) -> str:
        """Download a file (PDF/DOCX) to a destination path with retry backoff and locked file fallback."""
        if os.path.exists(destination_path) and os.path.getsize(destination_path) > 0 and not force:
            # Validate existing PDF if path ends with .pdf
            if destination_path.lower().endswith(".pdf"):
                try:
                    with open(destination_path, "rb") as f:
                        header = f.read(5)
                        if header.startswith(b"%PDF"):
                            logger.debug(f"File already cached and valid: {destination_path}")
                            return destination_path
                except Exception:
                    pass
            else:
                logger.debug(f"File already cached: {destination_path}")
                return destination_path

        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

        last_error = None
        for attempt in range(max_retries):
            temp_path = destination_path + f".tmp_{random.randint(100, 999)}"
            try:
                logger.info(f"Downloading (attempt {attempt + 1}/{max_retries}) {url} -> {destination_path}")
                resp = self.session.get(url, stream=True, timeout=30)
                resp.raise_for_status()

                with open(temp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            f.write(chunk)

                # Validate downloaded content
                file_sz = os.path.getsize(temp_path)
                if file_sz < 50:
                    raise ValueError(f"Downloaded file too small ({file_sz} bytes)")

                if destination_path.lower().endswith(".pdf"):
                    with open(temp_path, "rb") as f:
                        header = f.read(5)
                        if not header.startswith(b"%PDF"):
                            raise ValueError(f"Downloaded file is not a valid PDF (header: {header[:10]!r})")

                try:
                    if os.path.exists(destination_path):
                        os.remove(destination_path)
                    os.rename(temp_path, destination_path)
                    return destination_path
                except PermissionError:
                    base, ext = os.path.splitext(destination_path)
                    rand_suffix = random.randint(100, 999)
                    new_path = f"{base}_{rand_suffix}{ext}"
                    logger.warning(f"Destination locked ({destination_path}), saved with random suffix to {new_path}")
                    if os.path.exists(new_path):
                        try:
                            os.remove(new_path)
                        except Exception:
                            pass
                    os.rename(temp_path, new_path)
                    return new_path
            except Exception as e:
                last_error = e
                logger.warning(f"Download attempt {attempt + 1} failed for {url}: {e}")
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1.0 * (attempt + 1) + random.uniform(0.1, 0.5))

        raise last_error or RuntimeError(f"Failed to download {url} after {max_retries} attempts")
