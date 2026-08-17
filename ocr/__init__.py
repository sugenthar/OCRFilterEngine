"""OCR Subsystem Package."""

from ocr.consensus import merge_ocr_pass_tokens
from ocr.field_localization import FieldRegion, attach_token_span_regions, locate_field_regions
from ocr.preprocessing import (
    preprocess_crop_adaptive_threshold,
    preprocess_crop_otsu_binarize,
    preprocess_crop_upscale_contrast,
    preprocess_target_crop,
    preprocess_variant_a,
    preprocess_variant_b,
    preprocess_variant_c,
    preprocess_variant_d_binarized,
)
from ocr.quality import ImageQualityReport, analyze_image_quality
from ocr.record_segmentation import is_record_start_row, segment_rows_into_records
from ocr.row_clustering import cluster_tokens_into_rows, compute_dynamic_row_tolerance
from ocr.targeted_ocr import re_ocr_region, run_multi_pass_targeted_ocr
from ocr.tesseract_engine import DEFAULT_TESSERACT_PATH, TesseractEngine
from ocr.tokens import BoundingBox, OCRRow, OCRToken, RawRecord

__all__ = [
    "BoundingBox",
    "FieldRegion",
    "ImageQualityReport",
    "OCRRow",
    "OCRToken",
    "RawRecord",
    "TesseractEngine",
    "analyze_image_quality",
    "attach_token_span_regions",
    "cluster_tokens_into_rows",
    "compute_dynamic_row_tolerance",
    "is_record_start_row",
    "locate_field_regions",
    "merge_ocr_pass_tokens",
    "preprocess_crop_adaptive_threshold",
    "preprocess_crop_otsu_binarize",
    "preprocess_crop_upscale_contrast",
    "preprocess_target_crop",
    "preprocess_variant_a",
    "preprocess_variant_b",
    "preprocess_variant_c",
    "preprocess_variant_d_binarized",
    "re_ocr_region",
    "run_multi_pass_targeted_ocr",
    "segment_rows_into_records",
    "DEFAULT_TESSERACT_PATH",
]
