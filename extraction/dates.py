"""Date cleaning, extraction, and validation components."""

from datetime import datetime
import re
from typing import List, Optional, Tuple

from ocr.tokens import OCRToken

DATE_REGEX = re.compile(
    r"\b[0-9oOlISBZbZgq]{1,2}[/.\-][0-9oOlISBZbZgq]{1,2}[/.\-][0-9oOlISBZbZgq]{4}\b",
    re.IGNORECASE,
)

SUBSTITUTIONS = {
    'o': '0', 'O': '0',
    'l': '1', 'I': '1', '|': '1',
    'S': '5', 's': '5',
    'B': '8', 'b': '6',
    'Z': '2', 'z': '2',
    'g': '9', 'q': '9',
}


def clean_ocr_date(raw_str: str) -> Optional[str]:
    """Clean OCR character noise from date string and validate DD/MM/YYYY."""
    cleaned = "".join(SUBSTITUTIONS.get(c, c) for c in raw_str.replace(" ", ""))
    parts = re.split(r"[/.\-]", cleaned)
    if len(parts) != 3:
        return None
    try:
        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
        if 1 <= d <= 31 and 1 <= m <= 12 and 1900 <= y <= 2100:
            # Validate calendar validity
            datetime(year=y, month=m, day=d)
            return f"{d:02d}/{m:02d}/{y:04d}"
    except (ValueError, TypeError):
        pass
    return None


def locate_date_tokens(tokens: List[OCRToken]) -> List[Tuple[int, str, OCRToken]]:
    """Scan tokens and extract all valid date matches along with their token indices."""
    found: List[Tuple[int, str, OCRToken]] = []
    for index, token in enumerate(tokens):
        match = DATE_REGEX.search(token.text)
        if match:
            cleaned = clean_ocr_date(match.group(0))
            if cleaned:
                found.append((index, cleaned, token))
    return found
