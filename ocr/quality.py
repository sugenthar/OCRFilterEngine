"""Image Quality Analysis module."""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageStat


@dataclass
class ImageQualityReport:
    width: int
    height: int
    is_valid: bool
    brightness: float
    contrast: float
    estimated_dpi: int
    is_blank: bool
    aspect_ratio: float
    error: str = ""

    def summary(self) -> str:
        if not self.is_valid:
            return f"INVALID: {self.error}"
        return (
            f"Dimensions: {self.width}x{self.height} | Brightness: {self.brightness:.1f} | "
            f"Contrast: {self.contrast:.1f} | Blank: {self.is_blank}"
        )


def analyze_image_quality(image_input: Path | Image.Image) -> ImageQualityReport:
    """Analyze image quality parameters to guide preprocessing strategies."""
    try:
        if isinstance(image_input, (str, Path)):
            with Image.open(image_input) as img:
                return _compute_metrics(img)
        elif isinstance(image_input, Image.Image):
            return _compute_metrics(image_input)
        else:
            return ImageQualityReport(0, 0, False, 0.0, 0.0, 72, True, 1.0, "Unsupported input type")
    except Exception as exc:
        return ImageQualityReport(0, 0, False, 0.0, 0.0, 72, True, 1.0, str(exc))


def _compute_metrics(img: Image.Image) -> ImageQualityReport:
    width, height = img.size
    if width <= 0 or height <= 0:
        return ImageQualityReport(width, height, False, 0.0, 0.0, 72, True, 1.0, "Zero dimension image")

    aspect_ratio = width / height if height > 0 else 1.0

    # Convert to grayscale for statistical metrics
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)

    mean_brightness = stat.mean[0]
    std_dev_contrast = stat.stddev[0]

    # Extreme low contrast or near single-color image indicates blank
    is_blank = std_dev_contrast < 2.0 or (mean_brightness > 252 and std_dev_contrast < 5.0)

    # Estimate DPI
    dpi_info = img.info.get("dpi")
    if dpi_info and isinstance(dpi_info, tuple) and len(dpi_info) >= 1:
        estimated_dpi = int(dpi_info[0])
    else:
        estimated_dpi = 300 if width >= 2000 else (150 if width >= 1000 else 96)

    return ImageQualityReport(
        width=width,
        height=height,
        is_valid=not is_blank and width >= 50 and height >= 50,
        brightness=mean_brightness,
        contrast=std_dev_contrast,
        estimated_dpi=estimated_dpi,
        is_blank=is_blank,
        aspect_ratio=aspect_ratio,
        error="Image appears blank or has near-zero contrast" if is_blank else "",
    )
