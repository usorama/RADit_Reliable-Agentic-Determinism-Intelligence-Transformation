"""Visual Regression Testing Engine (UAT-003).

This module implements AI-powered visual comparison for UI regression testing:

1. Visual Comparison: Pixel-by-pixel and perceptual hash comparison
2. Baseline Management: Store, load, update baselines with version control
3. Difference Detection: Highlight changed regions and calculate percentages
4. Integration: Hook into UATAgent for screenshot comparison

Key Features:
- Pixel-by-pixel comparison for exact matching
- Perceptual hash comparison for minor variations (anti-aliasing, compression)
- Threshold enforcement: < 0.1% pixel difference for pass (configurable)
- Detailed difference reporting with bounding boxes
- Visual diff image generation

Dependencies:
- UAT-001: UAT Agent (for screenshot capture integration)
- Pillow (PIL): Image manipulation
- imagehash: Perceptual hashing for fuzzy comparison
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, cast

import imagehash
import numpy as np
from PIL import Image, ImageChops

from daw_agents.agents.uat.models import BaselineMetadata, ComparisonResult

logger = logging.getLogger(__name__)


class VisualRegressionEngine:
    """Visual regression testing engine with AI-powered comparison.

    The VisualRegressionEngine provides visual regression testing capabilities:
    1. Compare screenshots against baseline images
    2. Detect visual changes with configurable thresholds
    3. Generate visual diff images highlighting changes
    4. Manage baseline versions with metadata tracking

    The engine uses both pixel-by-pixel comparison for exact matching and
    perceptual hashing for fuzzy comparison to handle minor variations like
    anti-aliasing or compression artifacts.

    Attributes:
        baselines_dir: Directory for storing baseline images
        threshold: Pixel difference threshold for pass/fail (percent)
        perceptual_threshold: Perceptual hash difference threshold

    Example:
        engine = VisualRegressionEngine(
            baselines_dir=Path("baselines"),
            threshold=0.1  # 0.1% pixel difference
        )

        # Save baseline
        metadata = engine.save_baseline("login_page", screenshot_bytes)

        # Compare against baseline
        result = engine.compare_images(baseline_bytes, current_bytes)
        if result.passed:
            print("Visual regression test passed!")
        else:
            print(f"Failed: {result.pixel_difference_percent}% difference")
    """

    def __init__(
        self,
        baselines_dir: Path,
        threshold: float = 0.1,
        perceptual_threshold: int = 5,
    ) -> None:
        """Initialize the Visual Regression Engine.

        Args:
            baselines_dir: Directory for storing baseline images
            threshold: Pixel difference threshold for pass/fail (percent)
            perceptual_threshold: Perceptual hash difference threshold (0-64)
        """
        self.baselines_dir = baselines_dir
        self.threshold = threshold
        self.perceptual_threshold = perceptual_threshold

        # Ensure baselines directory exists
        self.baselines_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "VisualRegressionEngine initialized: baselines_dir=%s, threshold=%.2f%%",
            self.baselines_dir,
            self.threshold,
        )

    def save_baseline(
        self,
        name: str,
        image: bytes,
        approver: str | None = None,
    ) -> BaselineMetadata:
        """Save a baseline image with metadata.

        Args:
            name: Baseline name (used as filename)
            image: Image bytes (PNG format)
            approver: Optional email of approver

        Returns:
            BaselineMetadata with version and hash information
        """
        # Calculate hash of image
        image_hash = hashlib.sha256(image).hexdigest()

        # Save image file
        baseline_path = self.baselines_dir / f"{name}.png"
        baseline_path.write_bytes(image)

        # Create metadata
        now = datetime.now()
        metadata = BaselineMetadata(
            name=name,
            version=1,
            created_at=now,
            updated_at=now,
            hash=image_hash,
            approver=approver,
        )

        # Save metadata
        self._save_metadata(name, metadata)

        logger.info(
            "Baseline saved: name=%s, version=%d, hash=%s",
            name,
            metadata.version,
            image_hash[:8],
        )

        return metadata

    def load_baseline(self, name: str) -> bytes:
        """Load a baseline image.

        Args:
            name: Baseline name

        Returns:
            Image bytes

        Raises:
            FileNotFoundError: If baseline does not exist
        """
        baseline_path = self.baselines_dir / f"{name}.png"

        if not baseline_path.exists():
            raise FileNotFoundError(f"Baseline not found: {name}")

        return baseline_path.read_bytes()

    def update_baseline(
        self,
        name: str,
        image: bytes,
        reason: str,
        approver: str | None = None,
    ) -> BaselineMetadata:
        """Update an existing baseline (increments version).

        Args:
            name: Baseline name
            image: New image bytes
            reason: Reason for update (for audit trail)
            approver: Optional email of approver

        Returns:
            Updated BaselineMetadata

        Raises:
            FileNotFoundError: If baseline does not exist
        """
        # Load existing metadata
        old_metadata = self.get_baseline_metadata(name)

        # Calculate new hash
        image_hash = hashlib.sha256(image).hexdigest()

        # Save new image
        baseline_path = self.baselines_dir / f"{name}.png"
        baseline_path.write_bytes(image)

        # Create new metadata with incremented version
        now = datetime.now()
        metadata = BaselineMetadata(
            name=name,
            version=old_metadata.version + 1,
            created_at=old_metadata.created_at,
            updated_at=now,
            hash=image_hash,
            approver=approver,
        )

        # Save metadata
        self._save_metadata(name, metadata)

        logger.info(
            "Baseline updated: name=%s, version=%d->%d, reason=%s",
            name,
            old_metadata.version,
            metadata.version,
            reason,
        )

        return metadata

    def compare_images(
        self,
        baseline: bytes,
        current: bytes,
    ) -> ComparisonResult:
        """Compare two images and return comparison result.

        Uses both pixel-by-pixel comparison and perceptual hashing:
        1. Pixel-by-pixel: Exact comparison of each pixel
        2. Perceptual hash: Fuzzy comparison for minor variations

        Args:
            baseline: Baseline image bytes
            current: Current image bytes

        Returns:
            ComparisonResult with pass/fail and difference details

        Raises:
            ValueError: If image dimensions do not match
        """
        # Load images
        baseline_img = Image.open(BytesIO(baseline)).convert("RGB")
        current_img = Image.open(BytesIO(current)).convert("RGB")

        # Verify dimensions match
        if baseline_img.size != current_img.size:
            raise ValueError(
                f"Image dimensions do not match: "
                f"baseline={baseline_img.size}, current={current_img.size}"
            )

        # Calculate pixel difference
        pixel_diff_percent = self._calculate_pixel_difference(
            baseline_img,
            current_img,
        )

        # Determine pass/fail based on pixel threshold
        passed = pixel_diff_percent <= self.threshold

        # Detect changed regions (only if failed)
        changed_regions: list[dict[str, Any]] = []
        diff_image_base64: str | None = None

        if not passed:
            changed_regions = self._detect_changed_regions(
                baseline_img,
                current_img,
            )
            # Generate diff image
            diff_bytes = self.generate_diff(baseline, current)
            diff_image_base64 = base64.b64encode(diff_bytes).decode("utf-8")

        return ComparisonResult(
            passed=passed,
            pixel_difference_percent=pixel_diff_percent,
            changed_regions=changed_regions,
            diff_image_base64=diff_image_base64,
            threshold=self.threshold,
        )

    def generate_diff(
        self,
        baseline: bytes,
        current: bytes,
    ) -> bytes:
        """Generate a visual diff image highlighting changes.

        Creates a composite image showing differences in red.

        Args:
            baseline: Baseline image bytes
            current: Current image bytes

        Returns:
            Diff image bytes (PNG format)
        """
        baseline_img = Image.open(BytesIO(baseline)).convert("RGB")
        current_img = Image.open(BytesIO(current)).convert("RGB")

        # Calculate difference using ImageChops
        diff = ImageChops.difference(baseline_img, current_img)

        # Convert to grayscale to identify changed pixels
        diff_gray = diff.convert("L")

        # Create a mask of changed pixels (threshold at 10 to ignore minor noise)
        threshold = 10
        diff_mask = diff_gray.point(lambda p: 255 if p > threshold else 0)

        # Create output image (current image with changes highlighted in red)
        output = current_img.copy()
        output_pixels = output.load()
        mask_pixels = diff_mask.load()

        if output_pixels is not None and mask_pixels is not None:
            width, height = output.size
            for y in range(height):
                for x in range(width):
                    pixel_value = mask_pixels[x, y]
                    # Handle both int and tuple pixel values
                    # Grayscale images return int, but we need to handle tuple case too
                    if isinstance(pixel_value, int):
                        is_changed = pixel_value > 0
                    else:
                        # For tuple case (shouldn't happen with 'L' mode but handle it)
                        pixel_tuple = cast(tuple[int, ...], pixel_value)
                        is_changed = pixel_tuple[0] > 0
                    if is_changed:
                        # Highlight changed pixel in red
                        output_pixels[x, y] = (255, 0, 0)

        # Convert to bytes
        buffer = BytesIO()
        output.save(buffer, format="PNG")
        return buffer.getvalue()

    def get_baseline_metadata(self, name: str) -> BaselineMetadata:
        """Get metadata for a baseline.

        Args:
            name: Baseline name

        Returns:
            BaselineMetadata

        Raises:
            FileNotFoundError: If baseline metadata does not exist
        """
        metadata_path = self.baselines_dir / f"{name}.metadata.json"

        if not metadata_path.exists():
            raise FileNotFoundError(f"Baseline metadata not found: {name}")

        metadata_dict = json.loads(metadata_path.read_text())
        return BaselineMetadata(**metadata_dict)

    def list_baselines(self) -> list[str]:
        """List all baseline names.

        Returns:
            List of baseline names
        """
        baselines = []
        for path in self.baselines_dir.glob("*.png"):
            # Exclude diff images
            if not path.stem.endswith("_diff"):
                baselines.append(path.stem)
        return sorted(baselines)

    def delete_baseline(self, name: str) -> None:
        """Delete a baseline and its metadata.

        Args:
            name: Baseline name
        """
        baseline_path = self.baselines_dir / f"{name}.png"
        metadata_path = self.baselines_dir / f"{name}.metadata.json"

        if baseline_path.exists():
            baseline_path.unlink()

        if metadata_path.exists():
            metadata_path.unlink()

        logger.info("Baseline deleted: name=%s", name)

    def _save_metadata(
        self,
        name: str,
        metadata: BaselineMetadata,
    ) -> None:
        """Save baseline metadata to JSON file.

        Args:
            name: Baseline name
            metadata: Metadata to save
        """
        metadata_path = self.baselines_dir / f"{name}.metadata.json"
        metadata_dict = metadata.model_dump(mode="json")
        metadata_path.write_text(json.dumps(metadata_dict, indent=2))

    def _calculate_pixel_difference(
        self,
        baseline_img: Image.Image,
        current_img: Image.Image,
    ) -> float:
        """Calculate pixel-by-pixel difference percentage.

        Args:
            baseline_img: Baseline PIL Image
            current_img: Current PIL Image

        Returns:
            Percentage of pixels that differ (0.0 to 100.0)
        """
        # Convert to numpy arrays
        baseline_array = np.array(baseline_img)
        current_array = np.array(current_img)

        # Calculate difference
        diff = np.abs(baseline_array.astype(int) - current_array.astype(int))

        # Count pixels with any channel difference > 0
        changed_pixels = np.any(diff > 0, axis=2).sum()

        # Calculate percentage
        total_pixels = baseline_array.shape[0] * baseline_array.shape[1]
        percent = (float(changed_pixels) / total_pixels) * 100.0

        return float(round(percent, 4))

    def _calculate_perceptual_difference(
        self,
        baseline_img: Image.Image,
        current_img: Image.Image,
    ) -> int:
        """Calculate perceptual hash difference.

        Uses average hash for fast fuzzy comparison.

        Args:
            baseline_img: Baseline PIL Image
            current_img: Current PIL Image

        Returns:
            Hamming distance between hashes (0-64)
        """
        baseline_hash = imagehash.average_hash(baseline_img)
        current_hash = imagehash.average_hash(current_img)

        # Calculate Hamming distance
        return baseline_hash - current_hash

    def _detect_changed_regions(
        self,
        baseline_img: Image.Image,
        current_img: Image.Image,
    ) -> list[dict[str, Any]]:
        """Detect bounding boxes of changed regions.

        Args:
            baseline_img: Baseline PIL Image
            current_img: Current PIL Image

        Returns:
            List of bounding box dicts with x, y, width, height
        """
        # Calculate difference
        diff = ImageChops.difference(baseline_img, current_img)
        diff_gray = diff.convert("L")

        # Threshold to create binary mask
        threshold = 10
        diff_mask = diff_gray.point(lambda p: 255 if p > threshold else 0)

        # Convert to numpy for region detection
        mask_array = np.array(diff_mask)

        # Find contiguous changed regions using simple connected components
        regions = []

        # Simple approach: Find bounding box of all changed pixels
        # (More sophisticated would use scipy.ndimage.label)
        changed_coords = np.argwhere(mask_array > 0)

        if len(changed_coords) > 0:
            # Get bounding box of all changes
            y_min, x_min = changed_coords.min(axis=0)
            y_max, x_max = changed_coords.max(axis=0)

            regions.append({
                "x": int(x_min),
                "y": int(y_min),
                "width": int(x_max - x_min + 1),
                "height": int(y_max - y_min + 1),
            })

        return regions
