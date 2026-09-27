"""
Image Search Module — Pexels API

Searches and downloads stock photos from Pexels for use in
presentations and documents. Gracefully degrades if API key
is missing or requests fail.
"""

import os
import tempfile
import requests
from pathlib import Path
from typing import Optional

from core.logger import get_logger


class ImageSearch:
    """Search and download images from Pexels API."""

    PEXELS_BASE = "https://api.pexels.com/v1/search"

    def __init__(self, api_key: str = None, config=None):
        self.logger = get_logger(__name__, config)
        self.api_key = api_key or os.getenv("PEXELS_API_KEY", "")
        self._session = requests.Session()
        if self.api_key:
            self._session.headers["Authorization"] = self.api_key
        self._available = bool(self.api_key)
        if not self._available:
            self.logger.warning("[image_search] No PEXELS_API_KEY — image search disabled")

    @property
    def available(self) -> bool:
        """Whether image search is available (API key configured)."""
        return self._available

    def search(self, query: str, orientation: str = "landscape",
               per_page: int = 1) -> Optional[dict]:
        """Search Pexels for an image.

        Args:
            query: Search query (2-4 words ideal)
            orientation: landscape|portrait|square
            per_page: Number of results to return

        Returns:
            Photo metadata dict or None on failure
        """
        if not self._available:
            return None

        try:
            resp = self._session.get(
                self.PEXELS_BASE,
                params={
                    "query": query,
                    "orientation": orientation,
                    "per_page": per_page,
                    "size": "medium",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            photos = data.get("photos", [])
            if photos:
                return photos[0]

            self.logger.debug(f"[image_search] No results for: {query!r}")
            return None

        except Exception as e:
            self.logger.warning(f"[image_search] Search failed for {query!r}: {e}")
            return None

    def download(self, photo: dict, dest_dir: Path,
                 size: str = "medium") -> Optional[Path]:
        """Download a photo to the destination directory.

        Args:
            photo: Pexels photo metadata dict
            dest_dir: Directory to save the image
            size: original|large2x|large|medium|small|portrait|landscape|tiny

        Returns:
            Path to downloaded image, or None on failure
        """
        try:
            src_map = photo.get("src", {})
            url = src_map.get(size) or src_map.get("medium") or src_map.get("original")
            if not url:
                return None

            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()

            # Determine extension from content type
            content_type = resp.headers.get("content-type", "image/jpeg")
            ext = ".jpg"
            if "png" in content_type:
                ext = ".png"
            elif "webp" in content_type:
                ext = ".webp"

            photo_id = photo.get("id", "img")
            filename = f"pexels_{photo_id}{ext}"
            dest_path = Path(dest_dir) / filename
            dest_path.write_bytes(resp.content)

            self.logger.debug(f"[image_search] Downloaded: {dest_path.name} ({len(resp.content)} bytes)")
            return dest_path

        except Exception as e:
            self.logger.warning(f"[image_search] Download failed: {e}")
            return None

    def search_and_download(self, query: str, dest_dir: Path) -> Optional[Path]:
        """Search for an image and download it in one step.

        Args:
            query: Search query
            dest_dir: Directory to save the image

        Returns:
            Path to downloaded image, or None on failure
        """
        photo = self.search(query)
        if not photo:
            return None
        return self.download(photo, dest_dir)
