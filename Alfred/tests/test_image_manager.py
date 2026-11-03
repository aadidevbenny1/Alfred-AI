"""Tests for character images, ImageManager loading, caching, and fallback."""

from pathlib import Path
from src.ui.image_manager import ImageManager, REQUIRED_IMAGES, DEFAULT_IMAGE_NAME


def test_required_images_list():
    """Ensures exact 7 character PNG names are present in specification."""
    expected = {
        "v smoking.png",
        "v cat.png",
        "v thinking.png",
        "v happy.png",
        "v sad.png",
        "v cheers.png",
        "v stop.png",
    }
    assert set(REQUIRED_IMAGES) == expected
    assert DEFAULT_IMAGE_NAME == "v smoking.png"


def test_load_all_seven_images_from_assets():
    """Verifies that all 7 actual PNG images exist in assets/ and are discovered."""
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    mgr = ImageManager(assets_dir=assets_dir)

    validation = mgr.validate_all_images()
    for img_name, exists in validation.items():
        assert exists, f"Required image missing: {img_name}"

    assert len(mgr.get_available_images()) == 7


def test_image_fallback_behavior(tmp_path):
    """When a non-existent image is requested, falls back gracefully to default image."""
    # Create temp dir with only smoking image
    (tmp_path / "v smoking.png").write_bytes(b"dummy")
    mgr = ImageManager(assets_dir=tmp_path)

    fallback_path = mgr.get_image_path("v non_existent.png")
    assert fallback_path.name == "v smoking.png"


def test_aspect_ratio_and_pixmap_caching():
    """Verifies pixmap loading and caching with Qt."""
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    mgr = ImageManager(assets_dir=assets_dir, target_size=150)

    pixmap1 = mgr.get_pixmap("v smoking.png", target_size=140)
    assert not pixmap1.isNull()
    assert pixmap1.width() <= 140
    assert pixmap1.height() <= 140

    # Ensure caching works
    pixmap2 = mgr.get_pixmap("v smoking.png", target_size=140)
    assert pixmap1 == pixmap2

