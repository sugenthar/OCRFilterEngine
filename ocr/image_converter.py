"""High-resolution, OCR-safe image conversion for incoming form scans.

The converter improves image readability without inventing missing characters.
Validation remains available as a diagnostic after OCR.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


TARGET_LONG_EDGE = 3600
MAX_UPSCALE = 4.0


@dataclass(frozen=True)
class ImageConversionReport:
    """Traceable metadata for one OCR-ready converted image."""

    source_path: str
    output_path: str
    original_size: Tuple[int, int]
    converted_size: Tuple[int, int]
    scale: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "source_path": self.source_path,
            "output_path": self.output_path,
            "original_size": {"width": self.original_size[0], "height": self.original_size[1]},
            "converted_size": {"width": self.converted_size[0], "height": self.converted_size[1]},
            "scale": self.scale,
            "operations": [
                "EXIF orientation correction",
                "Lanczos HD upscale",
                "median noise reduction",
                "auto contrast normalization",
                "contrast boost",
                "unsharp text enhancement",
            ],
        }


def _scale_for_hd(width: int, height: int) -> float:
    """Return an upscale factor that improves OCR without excessive memory use."""
    long_edge = max(width, height, 1)
    return round(min(MAX_UPSCALE, max(1.0, TARGET_LONG_EDGE / long_edge)), 4)


def _flatten_to_white(image: Image.Image) -> Image.Image:
    """Flatten transparency before grayscale conversion so text remains readable."""
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        return Image.alpha_composite(background, rgba).convert("RGB")
    return image.convert("RGB")


def convert_image_for_ocr(source_path: Path, output_path: Path) -> ImageConversionReport:
    """Create a high-resolution enhanced PNG and return its audit metadata."""
    source_path = Path(source_path)
    output_path = Path(output_path)
    with Image.open(source_path) as opened:
        oriented = ImageOps.exif_transpose(opened)
        source = _flatten_to_white(oriented)

    original_size = source.size
    scale = _scale_for_hd(*original_size)
    converted_size = (
        max(1, int(round(original_size[0] * scale))),
        max(1, int(round(original_size[1] * scale))),
    )

    grayscale = ImageOps.grayscale(source)
    if converted_size != original_size:
        grayscale = grayscale.resize(converted_size, Image.Resampling.LANCZOS)

    denoised = grayscale.filter(ImageFilter.MedianFilter(size=3))
    normalized = ImageOps.autocontrast(denoised, cutoff=1)
    contrast = ImageEnhance.Contrast(normalized).enhance(1.35)
    enhanced = contrast.filter(ImageFilter.UnsharpMask(radius=1.5, percent=160, threshold=2))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")
    enhanced.save(temporary_path, format="PNG", optimize=True)
    temporary_path.replace(output_path)

    return ImageConversionReport(
        source_path=str(source_path),
        output_path=str(output_path),
        original_size=original_size,
        converted_size=converted_size,
        scale=scale,
    )
