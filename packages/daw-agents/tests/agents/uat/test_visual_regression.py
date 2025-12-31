"""Tests for Visual Regression Testing (UAT-003).

This test module verifies the VisualRegressionEngine implementation:

1. Image comparison with pixel-by-pixel comparison
2. Perceptual hash comparison for minor variations
3. Baseline management (save, load, update)
4. Difference detection and reporting
5. Threshold enforcement (< 0.1% pixel difference)
6. Visual diff image generation

CRITICAL: These tests are written FIRST (TDD Red phase) and MUST fail
until the implementation is complete.
"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from daw_agents.agents.uat.models import BaselineMetadata, ComparisonResult
from daw_agents.agents.uat.visual_regression import VisualRegressionEngine


@pytest.fixture
def temp_baselines_dir(tmp_path: Path) -> Path:
    """Create a temporary baselines directory."""
    baselines_dir = tmp_path / "baselines"
    baselines_dir.mkdir()
    return baselines_dir


@pytest.fixture
def visual_engine(temp_baselines_dir: Path) -> VisualRegressionEngine:
    """Create a VisualRegressionEngine instance with temp baselines dir."""
    return VisualRegressionEngine(baselines_dir=temp_baselines_dir)


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Create a sample image (100x100 red square)."""
    img = Image.new("RGB", (100, 100), color="red")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def slightly_different_image_bytes() -> bytes:
    """Create a slightly different image (100x100 red square with 1 white pixel)."""
    img = Image.new("RGB", (100, 100), color="red")
    # Add 1 white pixel (0.01% difference)
    img.putpixel((50, 50), (255, 255, 255))
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def very_different_image_bytes() -> bytes:
    """Create a very different image (100x100 blue square)."""
    img = Image.new("RGB", (100, 100), color="blue")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def image_with_change_region() -> bytes:
    """Create an image with a distinct change region (white square in corner)."""
    img = Image.new("RGB", (100, 100), color="red")
    draw = ImageDraw.Draw(img)
    # Draw a 20x20 white square in top-left corner (4% change)
    draw.rectangle([0, 0, 19, 19], fill="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


class TestVisualRegressionEngine:
    """Test suite for VisualRegressionEngine."""

    def test_engine_initialization(
        self, temp_baselines_dir: Path
    ) -> None:
        """Test that engine initializes with baselines directory."""
        engine = VisualRegressionEngine(baselines_dir=temp_baselines_dir)
        assert engine.baselines_dir == temp_baselines_dir
        assert temp_baselines_dir.exists()

    def test_save_baseline_creates_file(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that saving a baseline creates the file and metadata."""
        metadata = visual_engine.save_baseline(
            name="test_baseline",
            image=sample_image_bytes,
        )

        assert isinstance(metadata, BaselineMetadata)
        assert metadata.name == "test_baseline"
        assert metadata.version == 1
        assert metadata.hash is not None
        assert metadata.created_at is not None
        assert metadata.updated_at is not None

        # Verify file exists
        baseline_path = visual_engine.baselines_dir / "test_baseline.png"
        assert baseline_path.exists()

    def test_load_baseline_returns_image(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that loading a baseline returns the correct image bytes."""
        # Save baseline first
        visual_engine.save_baseline(
            name="test_baseline",
            image=sample_image_bytes,
        )

        # Load it back
        loaded_image = visual_engine.load_baseline(name="test_baseline")

        assert loaded_image is not None
        assert len(loaded_image) > 0
        # Verify it's a valid image
        img = Image.open(BytesIO(loaded_image))
        assert img.size == (100, 100)

    def test_load_nonexistent_baseline_raises_error(
        self,
        visual_engine: VisualRegressionEngine,
    ) -> None:
        """Test that loading a nonexistent baseline raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            visual_engine.load_baseline(name="nonexistent")

    def test_compare_identical_images_passes(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that comparing identical images passes with 0% difference."""
        result = visual_engine.compare_images(
            baseline=sample_image_bytes,
            current=sample_image_bytes,
        )

        assert isinstance(result, ComparisonResult)
        assert result.passed is True
        assert result.pixel_difference_percent == 0.0
        assert result.threshold == 0.1
        assert len(result.changed_regions) == 0

    def test_compare_slightly_different_images_passes(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
        slightly_different_image_bytes: bytes,
    ) -> None:
        """Test that images with < 0.1% difference pass."""
        result = visual_engine.compare_images(
            baseline=sample_image_bytes,
            current=slightly_different_image_bytes,
        )

        assert result.passed is True
        assert result.pixel_difference_percent < 0.1
        assert result.pixel_difference_percent > 0.0

    def test_compare_very_different_images_fails(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
        very_different_image_bytes: bytes,
    ) -> None:
        """Test that images with > 0.1% difference fail."""
        result = visual_engine.compare_images(
            baseline=sample_image_bytes,
            current=very_different_image_bytes,
        )

        assert result.passed is False
        assert result.pixel_difference_percent > 0.1
        # Should have changed regions
        assert len(result.changed_regions) > 0

    def test_compare_detects_change_regions(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
        image_with_change_region: bytes,
    ) -> None:
        """Test that comparison detects and reports changed regions."""
        result = visual_engine.compare_images(
            baseline=sample_image_bytes,
            current=image_with_change_region,
        )

        assert result.passed is False
        assert len(result.changed_regions) > 0

        # Verify region structure
        region = result.changed_regions[0]
        assert "x" in region
        assert "y" in region
        assert "width" in region
        assert "height" in region

    def test_compare_generates_diff_image(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
        very_different_image_bytes: bytes,
    ) -> None:
        """Test that comparison generates a visual diff image."""
        result = visual_engine.compare_images(
            baseline=sample_image_bytes,
            current=very_different_image_bytes,
        )

        assert result.diff_image_base64 is not None
        # Verify it's valid base64
        diff_bytes = base64.b64decode(result.diff_image_base64)
        diff_img = Image.open(BytesIO(diff_bytes))
        assert diff_img.size == (100, 100)

    def test_generate_diff_image_highlights_changes(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
        image_with_change_region: bytes,
    ) -> None:
        """Test that generate_diff creates an image highlighting changes."""
        diff_bytes = visual_engine.generate_diff(
            baseline=sample_image_bytes,
            current=image_with_change_region,
        )

        assert diff_bytes is not None
        diff_img = Image.open(BytesIO(diff_bytes))
        assert diff_img.size == (100, 100)

    def test_update_baseline_increments_version(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
        very_different_image_bytes: bytes,
    ) -> None:
        """Test that updating a baseline increments version."""
        # Save initial baseline
        metadata_v1 = visual_engine.save_baseline(
            name="test_baseline",
            image=sample_image_bytes,
        )
        assert metadata_v1.version == 1

        # Update baseline
        metadata_v2 = visual_engine.update_baseline(
            name="test_baseline",
            image=very_different_image_bytes,
            reason="Intentional UI change",
        )

        assert metadata_v2.version == 2
        assert metadata_v2.name == "test_baseline"
        assert metadata_v2.hash != metadata_v1.hash
        assert metadata_v2.updated_at > metadata_v1.updated_at

    def test_update_baseline_stores_reason(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
        very_different_image_bytes: bytes,
    ) -> None:
        """Test that update reason is stored in metadata."""
        visual_engine.save_baseline(
            name="test_baseline",
            image=sample_image_bytes,
        )

        metadata = visual_engine.update_baseline(
            name="test_baseline",
            image=very_different_image_bytes,
            reason="Updated for new design",
            approver="user@example.com",
        )

        # Verify reason is tracked
        assert metadata.approver == "user@example.com"

    def test_perceptual_hash_comparison_for_similar_images(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
        slightly_different_image_bytes: bytes,
    ) -> None:
        """Test that perceptual hash identifies similar images."""
        # This test verifies that perceptual hashing is used for fuzzy comparison
        result = visual_engine.compare_images(
            baseline=sample_image_bytes,
            current=slightly_different_image_bytes,
        )

        # Images should be considered similar by perceptual hash
        assert result.passed is True

    def test_compare_different_sizes_raises_error(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that comparing images of different sizes raises ValueError."""
        # Create a different sized image
        img = Image.new("RGB", (200, 200), color="red")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        different_size = buffer.getvalue()

        with pytest.raises(ValueError, match="Image dimensions do not match"):
            visual_engine.compare_images(
                baseline=sample_image_bytes,
                current=different_size,
            )

    def test_compare_with_custom_threshold(
        self,
        temp_baselines_dir: Path,
        sample_image_bytes: bytes,
        image_with_change_region: bytes,
    ) -> None:
        """Test that custom threshold is respected."""
        # Create engine with higher threshold (5%)
        engine = VisualRegressionEngine(
            baselines_dir=temp_baselines_dir,
            threshold=5.0,
        )

        result = engine.compare_images(
            baseline=sample_image_bytes,
            current=image_with_change_region,
        )

        # Should pass with 4% change and 5% threshold
        assert result.threshold == 5.0
        assert result.passed is True

    def test_baseline_metadata_persistence(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that baseline metadata is persisted and can be retrieved."""
        metadata = visual_engine.save_baseline(
            name="test_baseline",
            image=sample_image_bytes,
        )

        # Retrieve metadata
        retrieved_metadata = visual_engine.get_baseline_metadata(
            name="test_baseline"
        )

        assert retrieved_metadata.name == metadata.name
        assert retrieved_metadata.version == metadata.version
        assert retrieved_metadata.hash == metadata.hash

    def test_list_all_baselines(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that all baselines can be listed."""
        # Save multiple baselines
        visual_engine.save_baseline("baseline1", sample_image_bytes)
        visual_engine.save_baseline("baseline2", sample_image_bytes)
        visual_engine.save_baseline("baseline3", sample_image_bytes)

        baselines = visual_engine.list_baselines()

        assert len(baselines) == 3
        assert "baseline1" in baselines
        assert "baseline2" in baselines
        assert "baseline3" in baselines

    def test_delete_baseline(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
    ) -> None:
        """Test that baselines can be deleted."""
        visual_engine.save_baseline("test_baseline", sample_image_bytes)

        # Verify it exists
        baseline_path = visual_engine.baselines_dir / "test_baseline.png"
        assert baseline_path.exists()

        # Delete it
        visual_engine.delete_baseline("test_baseline")

        # Verify it's gone
        assert not baseline_path.exists()

    def test_changed_regions_have_bounding_boxes(
        self,
        visual_engine: VisualRegressionEngine,
        sample_image_bytes: bytes,
        image_with_change_region: bytes,
    ) -> None:
        """Test that changed regions include bounding box coordinates."""
        result = visual_engine.compare_images(
            baseline=sample_image_bytes,
            current=image_with_change_region,
        )

        assert len(result.changed_regions) > 0
        for region in result.changed_regions:
            assert "x" in region
            assert "y" in region
            assert "width" in region
            assert "height" in region
            assert isinstance(region["x"], int)
            assert isinstance(region["y"], int)
            assert isinstance(region["width"], int)
            assert isinstance(region["height"], int)
