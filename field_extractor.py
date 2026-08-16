"""Build a coordinate-preserving OCR source for later 31-field extraction.

Preserves bounding boxes, confidence, and tokens, grouped into records
using dynamic row clustering and multi-factor title/name segmentation.
"""

import json
from pathlib import Path
from typing import List, Tuple

from ocr import (
    DEFAULT_TESSERACT_PATH,
    OCRRow,
    OCRToken,
    RawRecord,
    TesseractEngine,
    cluster_tokens_into_rows,
    is_record_start_row,
    segment_rows_into_records,
)

TESSERACT_PATH = DEFAULT_TESSERACT_PATH
IMAGE_PATH = Path("images/sample.png")
OUTPUT_PATH = Path("output/coordinate_records.json")

ROW_Y_TOLERANCE = 15
LOW_CONFIDENCE = 50.0
RECORD_START_TITLES = {
    # Personal and professional titles
    "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "miss", "dr", "dr.", "prof", "prof.", "professor",
    # Military and official ranks
    "major", "major general", "general", "colonel", "col", "col.", "captain", "capt", "capt.",
    "lieutenant", "lt", "lt.", "commander", "cmdr", "admiral", "brigadier", "field marshal",
    # Religious, academic, nobility, and civic titles
    "rev", "rev.", "reverend", "pastor", "father", "fr", "fr.", "rabbi", "imam", "sheikh", "sheik",
    "sir", "lady", "lord", "dame", "baron", "baroness",
    "judge", "justice", "hon", "hon.", "honorable", "honourable",
}


def read_ocr_words(image_path: Path, variant: str = "A") -> list[dict]:
    """Return all non-empty OCR words with their geometry and confidence."""
    engine = TesseractEngine(tesseract_cmd=TESSERACT_PATH)
    tokens, _ = engine.run_ocr(image_path, variant=variant, psm=6)
    return [t.to_dict() for t in tokens]


def group_words_into_rows(words: list[dict], tolerance: int | None = None) -> list[dict]:
    """Group words into horizontal visual rows using dynamic clustering."""
    tokens = [OCRToken.from_dict(w) for w in words]
    rows = cluster_tokens_into_rows(tokens, tolerance=tolerance)
    return [r.to_dict() for r in rows]


def clean_title_token(text: str) -> str:
    from ocr.record_segmentation import clean_title_word
    return clean_title_word(text)


def is_record_start(row: dict) -> bool:
    """Return True for a row that begins a person's record."""
    ocr_row = OCRRow.from_dict(row)
    return is_record_start_row(ocr_row)


def group_rows_into_records(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Segment visual rows into discrete records."""
    ocr_rows = [OCRRow.from_dict(r) for r in rows]
    records, unassigned = segment_rows_into_records(ocr_rows)
    return [rec.to_dict() for rec in records], [un.to_dict() for un in unassigned]


def main() -> None:
    if not IMAGE_PATH.exists():
        raise FileNotFoundError(f"Source image not found: {IMAGE_PATH}")

    words = read_ocr_words(IMAGE_PATH)
    rows = group_words_into_rows(words)
    records, unassigned_rows = group_rows_into_records(rows)

    result = {
        "source_image": str(IMAGE_PATH),
        "row_y_tolerance": ROW_Y_TOLERANCE,
        "low_confidence_threshold": LOW_CONFIDENCE,
        "useful_row_count": len(rows),
        "record_count": len(records),
        "unassigned_rows": unassigned_rows,
        "records": records,
    }

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"Useful rows found: {len(rows)}")
    print(f"Records found: {len(records)}")
    print(f"Saved coordinate OCR data: {OUTPUT_PATH}")

    if unassigned_rows:
        print(f"WARNING: {len(unassigned_rows)} row(s) were not assigned to a record.")

    for record in records:
        review_words = sum(
            word["needs_review"]
            for row in record["rows"]
            for word in row["words"]
        )
        print(
            f"Record {record['record_number']}: "
            f"{review_words} low-confidence word(s) retained for review"
        )


if __name__ == "__main__":
    main()
