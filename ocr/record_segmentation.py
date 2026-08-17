"""Advanced Record Segmentation module."""

import re
from typing import List, Tuple
from ocr.tokens import OCRRow, RawRecord

RECORD_START_TITLES = {
    # Personal & Professional Titles
    "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "miss", "dr", "dr.", "prof", "prof.", "professor",
    # Military & Official Ranks
    "major", "major general", "general", "colonel", "col", "col.", "captain", "capt", "capt.",
    "lieutenant", "lt", "lt.", "commander", "cmdr", "admiral", "brigadier", "field marshal",
    # Religious, Nobility, Academic & Civic
    "rev", "rev.", "reverend", "pastor", "father", "fr", "fr.", "rabbi", "imam", "sheikh", "sheik",
    "sir", "lady", "lord", "dame", "baron", "baroness",
    "judge", "justice", "hon", "hon.", "honorable", "honourable",
}


def clean_title_word(text: str) -> str:
    """Strip leading noise, numbers, bullets, em-dashes, and punctuation."""
    cleaned = text.lower().strip(".,;:_—- •*~#=+!?/\\()[]{}<>\"'`")
    # Remove leading numeric index if attached like 1.Mr or 2-Mrs
    cleaned = re.sub(r"^\d+[\.\-_\)]", "", cleaned)
    return cleaned


def is_record_start_row(row: OCRRow) -> bool:
    """Determine if a visual row marks the beginning of a person record."""
    if not row.words:
        return False

    valid_words = [clean_title_word(w.text) for w in row.words if clean_title_word(w.text)]
    if not valid_words:
        return False

    # Check first 3 tokens for title
    for idx in range(min(3, len(valid_words))):
        w = valid_words[idx]
        if w in RECORD_START_TITLES:
            return True
        if idx + 1 < len(valid_words):
            w2 = f"{w} {valid_words[idx + 1]}"
            if w2 in RECORD_START_TITLES:
                return True
        # Check prefix match for common titles (e.g. miss, prof, capt)
        for title in RECORD_START_TITLES:
            title_clean = title.replace(" ", "").replace(".", "")
            if len(title_clean) >= 3 and w.startswith(title_clean):
                return True

    return False


def segment_rows_into_records(rows: List[OCRRow]) -> Tuple[List[RawRecord], List[OCRRow]]:
    """Segment a list of visual rows into discrete records based on title starts and vertical flow."""
    records: List[RawRecord] = []
    current_rows: List[OCRRow] = []
    unassigned_rows: List[OCRRow] = []

    for row in rows:
        if is_record_start_row(row):
            if current_rows:
                records.append(
                    RawRecord(
                        record_number=len(records) + 1,
                        rows=current_rows,
                    )
                )
            current_rows = [row]
        elif current_rows:
            current_rows.append(row)
        else:
            unassigned_rows.append(row)

    if current_rows:
        records.append(
            RawRecord(
                record_number=len(records) + 1,
                rows=current_rows,
            )
        )

    # Recompute source text for all created records
    for rec in records:
        rec.recompute_source_text()

    # Fallback if no explicit title recognized but rows exist
    if not records and rows:
        fallback_rec = RawRecord(record_number=1, rows=rows)
        fallback_rec.recompute_source_text()
        records.append(fallback_rec)
        unassigned_rows = []

    return records, unassigned_rows
