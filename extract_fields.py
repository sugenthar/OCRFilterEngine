"""High-Accuracy 31-Field Record Extractor with backward-compatible API."""

from collections import OrderedDict
import re
from typing import Any, Dict, List, Optional, Tuple

from extraction.dictionaries import (
    CARD_STARTS,
    COUNTRIES,
    MODEL_BRANDS,
    NETWORKS,
    PLAN_STARTS,
    PROFESSIONS_MAP,
    PROVIDERS_MAP,
)
from extraction.extractor import FIELD_ORDER, build_field, extract_31_fields
from ocr.tokens import OCRToken, RawRecord

PROFESSIONS = list(PROFESSIONS_MAP.keys())
DATE_PATTERN = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")
POSTCODE_PATTERN = re.compile(
    r"^([A-Z0-9]{2,4}\s*[A-Z0-9]{2,4}\.?|[A-Z]{1,3}\d[A-Z0-9]*|\d[A-Z0-9]{4,7}\.?|E[0-9]{4})$",
    re.I,
)


def normalized(token: dict) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9+*@-]", "", token.get("text", "")).lower()
    return cleaned


def clean_val(text: str) -> str:
    return text.strip(".,;:_—- •*~#=+!?/\\()[]{}<>'\"|")


def joined(tokens: list[dict]) -> str:
    return " ".join(token.get("text", "") for token in tokens).strip()


def field(tokens: list[dict] | None = None, value: str | None = None, review: bool = False) -> dict:
    tokens = tokens or []
    raw = joined(tokens)
    val = raw if value is None else str(value)
    
    valid_confs = [float(token.get("confidence", 0.0)) for token in tokens if float(token.get("confidence", 0.0)) > 0]
    if valid_confs:
        conf = round(sum(valid_confs) / len(valid_confs), 2)
    elif tokens:
        conf = round(sum(float(t.get("confidence", 0.0)) for t in tokens) / len(tokens), 2)
    else:
        conf = 100.0 if val else 0.0

    needs_review = review or (not tokens and not val) or any(token.get("needs_review", False) for token in tokens)
    return {
        "value": val,
        "raw_text": raw,
        "confidence": conf,
        "needs_review": needs_review,
        "coordinates": [{k: token[k] for k in ("x", "y", "width", "height")} for token in tokens if "x" in token],
        "source_tokens": tokens,
    }


def clean_ocr_date(raw_str: str) -> str | None:
    from extraction.dates import clean_ocr_date as _clean_date
    return _clean_date(raw_str)


def locate_date_tokens(tokens: list[dict]) -> list[tuple[int, str]]:
    from extraction.dates import clean_ocr_date as _clean_date, DATE_REGEX
    found = []
    for index, token in enumerate(tokens):
        match = DATE_REGEX.search(token.get("text", ""))
        if match:
            cleaned = _clean_date(match.group(0))
            if cleaned:
                found.append((index, cleaned))
    return found


def extract_record(ocr_record: dict, file_no: str, form_no: int) -> dict:
    """Extract all 31 fields from OCR record dictionary, preserving full schema compatibility."""
    raw_record = RawRecord.from_dict(ocr_record)
    result = extract_31_fields(raw_record, str(file_no), form_no)
    return result
