"""Dynamic Row Clustering based on word geometry and median token height."""

import statistics
from typing import List
from ocr.tokens import OCRRow, OCRToken

DEFAULT_ROW_MULTIPLIER = 0.6
MIN_ROW_TOLERANCE = 8
MAX_ROW_TOLERANCE = 35


def compute_dynamic_row_tolerance(tokens: List[OCRToken], multiplier: float = DEFAULT_ROW_MULTIPLIER) -> int:
    """Calculate row clustering tolerance dynamically from median token heights."""
    if not tokens:
        return 15
    heights = [t.height for t in tokens if t.height > 4]
    if not heights:
        return 15
    median_h = statistics.median(heights)
    tolerance = int(round(median_h * multiplier))
    return max(MIN_ROW_TOLERANCE, min(tolerance, MAX_ROW_TOLERANCE))


def cluster_tokens_into_rows(
    tokens: List[OCRToken],
    tolerance: int | None = None,
    filter_artifact_rows: bool = True,
) -> List[OCRRow]:
    """Group tokens into horizontal visual rows using vertical center alignment and dynamic tolerance."""
    if not tokens:
        return []

    if tolerance is None:
        tolerance = compute_dynamic_row_tolerance(tokens)

    # Sort tokens primarily by Y coordinate then X
    sorted_tokens = sorted(tokens, key=lambda t: (t.y, t.x))

    row_buckets: List[OCRRow] = []
    for token in sorted_tokens:
        token_center_y = token.y + token.height / 2.0
        placed = False
        for row in row_buckets:
            # Check vertical distance against row center
            if row.words:
                row_center_y = sum(w.y + w.height / 2.0 for w in row.words) / len(row.words)
            else:
                row_center_y = row.y
            if abs(token_center_y - row_center_y) <= tolerance:
                row.words.append(token)
                placed = True
                break
        if not placed:
            row_buckets.append(OCRRow(y=token.y, words=[token]))

    # Finalize row text, sort rows by Y and words inside row by X
    clean_rows: List[OCRRow] = []
    for row in sorted(row_buckets, key=lambda r: r.y):
        row.recompute_text()
        if filter_artifact_rows and row.text.strip() in {"—", "©", "-", "- - - -", "--", "•", "~"}:
            continue
        if row.words:
            clean_rows.append(row)

    return clean_rows
