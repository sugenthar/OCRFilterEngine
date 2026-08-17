"""Multi-Stage Image Preprocessing Pipelines for Full Document and Targeted Crop OCR."""

from typing import Optional, Tuple
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def get_adaptive_scale(width: int, height: int, target_min_dim: int = 2400) -> float:
    """Calculate an optimal scaling factor without blowing up memory."""
    if width >= target_min_dim or height >= target_min_dim:
        return 1.0
    scale = max(1.0, target_min_dim / max(width, 1))
    return min(scale, 3.0)


def preprocess_variant_a(image: Image.Image, scale: Optional[float] = None) -> Tuple[Image.Image, float]:
    """Variant A: Grayscale -> Contrast Enhancement -> Upscale -> Unsharp Mask."""
    width, height = image.size
    if scale is None:
        scale = get_adaptive_scale(width, height, target_min_dim=2800)

    gray = image.convert("L")
    if scale != 1.0:
        new_w = int(round(width * scale))
        new_h = int(round(height * scale))
        gray = gray.resize((new_w, new_h), Image.Resampling.BICUBIC)

    enhanced = ImageEnhance.Contrast(gray).enhance(1.6)
    sharpened = enhanced.filter(ImageFilter.UnsharpMask(radius=2, percent=140, threshold=3))
    return sharpened, scale


def preprocess_variant_b(image: Image.Image, scale: Optional[float] = None) -> Tuple[Image.Image, float]:
    """Variant B: Grayscale -> Median Denoise -> Auto Contrast -> Adaptive Binarization -> Upscale."""
    width, height = image.size
    if scale is None:
        scale = get_adaptive_scale(width, height, target_min_dim=2800)

    gray = image.convert("L")
    autocontrast = ImageOps.autocontrast(gray, cutoff=2)
    denoised = autocontrast.filter(ImageFilter.MedianFilter(size=3))

    if scale != 1.0:
        new_w = int(round(width * scale))
        new_h = int(round(height * scale))
        denoised = denoised.resize((new_w, new_h), Image.Resampling.BICUBIC)

    mean_val = ImageEnhance.Contrast(denoised).enhance(1.8)
    return mean_val, scale


def preprocess_variant_c(image: Image.Image, scale: Optional[float] = None) -> Tuple[Image.Image, float]:
    """Variant C: Grayscale -> Deskew Check -> Contrast boost -> Lanczos Upscale."""
    width, height = image.size
    if scale is None:
        scale = get_adaptive_scale(width, height, target_min_dim=3200)

    gray = image.convert("L")
    if scale != 1.0:
        new_w = int(round(width * scale))
        new_h = int(round(height * scale))
        gray = gray.resize((new_w, new_h), Image.Resampling.LANCZOS)

    unsharp = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    enhanced = ImageEnhance.Contrast(unsharp).enhance(1.5)
    return enhanced, scale


def preprocess_variant_d_binarized(image: Image.Image, scale: float = 2.0) -> Tuple[Image.Image, float]:
    """Variant D: Grayscale -> Stronger Denoise -> Otsu-like Binary Threshold -> Sharpen."""
    width, height = image.size
    gray = image.convert("L")
    if scale != 1.0:
        new_w = int(round(width * scale))
        new_h = int(round(height * scale))
        gray = gray.resize((new_w, new_h), Image.Resampling.BICUBIC)

    denoised = gray.filter(ImageFilter.MedianFilter(size=3))
    lut = [255 if i > 140 else 0 for i in range(256)]
    binary = denoised.point(lut, mode="L")
    sharpened = binary.filter(ImageFilter.SHARPEN)
    return sharpened, scale


# Targeted Crop Preprocessors

def preprocess_crop_upscale_contrast(crop_img: Image.Image, scale: float = 3.0) -> Image.Image:
    """Grayscale + Bicubic Upscale (3x/4x) + Contrast + Sharpen."""
    w, h = crop_img.size
    gray = crop_img.convert("L")
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = gray.resize((new_w, new_h), Image.Resampling.BICUBIC)
    enhanced = ImageEnhance.Contrast(resized).enhance(2.0)
    return enhanced.filter(ImageFilter.SHARPEN)


def preprocess_crop_otsu_binarize(crop_img: Image.Image, scale: float = 4.0) -> Image.Image:
    """Grayscale + Lanczos 4x + Otsu-like Global Threshold."""
    w, h = crop_img.size
    gray = crop_img.convert("L")
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = gray.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Calculate simple Otsu-like threshold from histogram
    hist = resized.histogram()
    total = sum(hist)
    sum_all = sum(i * count for i, count in enumerate(hist))
    sum_b, weight_b, max_var, threshold = 0.0, 0, 0.0, 128
    for i in range(256):
        weight_b += hist[i]
        if weight_b == 0:
            continue
        weight_f = total - weight_b
        if weight_f == 0:
            break
        sum_b += i * hist[i]
        mean_b = sum_b / weight_b
        mean_f = (sum_all - sum_b) / weight_f
        var_between = float(weight_b) * float(weight_f) * (mean_b - mean_f) ** 2
        if var_between > max_var:
            max_var = var_between
            threshold = i

    lut = [255 if i > threshold else 0 for i in range(256)]
    return resized.point(lut, mode="L")


def preprocess_crop_adaptive_threshold(crop_img: Image.Image, scale: float = 3.0) -> Image.Image:
    """Grayscale + Upscale + Unsharp Mask + High Contrast."""
    w, h = crop_img.size
    gray = crop_img.convert("L")
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = gray.resize((new_w, new_h), Image.Resampling.LANCZOS)
    unsharp = resized.filter(ImageFilter.UnsharpMask(radius=3, percent=180, threshold=2))
    return ImageOps.autocontrast(unsharp, cutoff=3)


def preprocess_target_crop(crop_img: Image.Image, scale: float = 3.0) -> Image.Image:
    """Standard targeted crop preprocessing."""
    return preprocess_crop_upscale_contrast(crop_img, scale=scale)
