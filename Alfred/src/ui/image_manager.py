"""Image manager for Alfred.

Loads, caches, and scales the seven character PNG images with transparency preservation,
aspect ratio maintenance, and fallback handling.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("alfred.image_manager")

REQUIRED_IMAGES = [
    "v smoking.png",
    "v cat.png",
    "v thinking.png",
    "v happy.png",
    "v sad.png",
    "v cheers.png",
    "v stop.png",
]

DEFAULT_IMAGE_NAME = "v smoking.png"


class ImageManager:
    """Manages character images, ensuring clean scaling, aspect ratio preservation, and caching."""

    def __init__(self, assets_dir: Path | str, target_size: int = 150):
        self.assets_dir = Path(assets_dir)
        self.target_size = target_size
        self._pixmap_cache: Dict[str, Any] = {}
        self._available_images: Dict[str, Path] = {}
        self._scan_and_cache()

    def _scan_and_cache(self) -> None:
        """Discovers all images in the assets directory."""
        if not self.assets_dir.exists():
            logger.error("Assets directory does not exist: %s", self.assets_dir)
            return

        for img_name in REQUIRED_IMAGES:
            img_path = self.assets_dir / img_name
            if img_path.exists():
                self._available_images[img_name] = img_path
            else:
                logger.warning("Required image not found: %s", img_path)

        logger.info(
            "ImageManager initialized. Loaded %d/%d images from %s",
            len(self._available_images),
            len(REQUIRED_IMAGES),
            self.assets_dir,
        )

    def is_image_available(self, image_name: str) -> bool:
        """Checks if a specific image file exists."""
        return image_name in self._available_images

    def get_available_images(self) -> list[str]:
        """Returns list of currently available image filenames."""
        return list(self._available_images.keys())

    def get_image_path(self, image_name: str) -> Path:
        """Returns the file path for an image, or default/fallback if missing."""
        if image_name in self._available_images:
            return self._available_images[image_name]

        if DEFAULT_IMAGE_NAME in self._available_images:
            logger.warning("Image '%s' not found. Falling back to default: %s", image_name, DEFAULT_IMAGE_NAME)
            return self._available_images[DEFAULT_IMAGE_NAME]

        # If even default is missing, try any available
        if self._available_images:
            first_key = next(iter(self._available_images.keys()))
            logger.warning("Default image missing! Falling back to %s", first_key)
            return self._available_images[first_key]

        raise FileNotFoundError(f"No valid character images available in {self.assets_dir}")

    def get_pixmap(self, image_name: str, target_size: Optional[int] = None):
        """Loads and scales a QPixmap preserving aspect ratio and transparency.
        
        Uses in-memory caching to prevent disk re-reads.
        """
        size = target_size or self.target_size
        cache_key = f"{image_name}_{size}"

        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPixmap

        image_path = self.get_image_path(image_name)

        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            logger.error("Failed to load QPixmap from %s", image_path)
            # Try default image
            if image_name != DEFAULT_IMAGE_NAME and DEFAULT_IMAGE_NAME in self._available_images:
                return self.get_pixmap(DEFAULT_IMAGE_NAME, size)
            return QPixmap()

        # Proportional scaling without distortion
        scaled_pixmap = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self._pixmap_cache[cache_key] = scaled_pixmap
        return scaled_pixmap

    def validate_all_images(self) -> dict[str, bool]:
        """Returns validation report for all 7 required images."""
        return {name: (self.assets_dir / name).exists() for name in REQUIRED_IMAGES}

