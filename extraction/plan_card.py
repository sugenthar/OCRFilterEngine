"""Plan Type, Card Type, and Contact currency extraction."""

import re
from typing import List, Optional, Tuple

from ocr.tokens import OCRToken
from extraction.dictionaries import CARD_STARTS, PLAN_STARTS


def clean_val(text: str) -> str:
    return text.strip(".,;:_—- •*~#=+!?/\\()[]{}<>\"'|")


def extract_plan_and_card(
    tokens: List[OCRToken],
    start_idx: int,
    contact_idx: Optional[int],
    first_end_date_idx: int,
) -> Tuple[str, List[OCRToken], Optional[int], str, List[OCRToken], Optional[int]]:
    """Extract Plan Type and Card Type with visual artifact filtering."""
    plan_index = next(
        (i for i in range(start_idx, len(tokens)) if any(tokens[i].normalized_text.startswith(p) for p in PLAN_STARTS)),
        None,
    )

    card_search_start = (plan_index + 1) if plan_index is not None else start_idx
    card_index = next(
        (i for i in range(card_search_start, len(tokens)) if any(tokens[i].normalized_text.startswith(c) for c in CARD_STARTS)),
        None,
    )
    if card_index is None and plan_index is not None:
        card_index = next(
            (i for i in range(start_idx, plan_index) if any(tokens[i].normalized_text.startswith(c) for c in CARD_STARTS)),
            None,
        )

    plan_val, plan_toks = "", []
    if plan_index is not None:
        plan_end = card_index if (card_index is not None and card_index > plan_index) else (contact_idx if (contact_idx is not None and contact_idx > plan_index) else plan_index + 1)
        raw_plan_toks = [t for t in tokens[plan_index:plan_end] if t.text.strip() not in {"—", "---", "--", "•", "=", "-"}]
        plan_val = clean_val(" ".join(t.text for t in raw_plan_toks))
        plan_toks = raw_plan_toks

    card_val, card_toks = "", []
    if card_index is not None:
        card_end = contact_idx if (contact_idx is not None and contact_idx > card_index) else first_end_date_idx
        raw_card_toks = [t for t in tokens[card_index:card_end] if t.text.strip() not in {"—", "---", "--", "•", "=", "-"}]
        card_val = clean_val(" ".join(t.text for t in raw_card_toks))
        card_toks = raw_card_toks

    return plan_val, plan_toks, plan_index, card_val, card_toks, card_index


def extract_contact(
    tokens: List[OCRToken],
    start_idx: int,
    end_idx: int,
) -> Tuple[str, List[OCRToken], Optional[int]]:
    """Locate Contact amount token (e.g. £507, €580, £336) and extract purely numeric value.
    
    Searches backwards from date tokens to ensure earlier IMEI numbers are never confused with contact.
    """
    # Priority 1: Explicit currency symbol [£€$] preceding digits
    for i in range(end_idx - 1, start_idx - 1, -1):
        if re.search(r"[£€\$]\s*\d{2,5}", tokens[i].text):
            numeric = re.sub(r"[^0-9]", "", tokens[i].text)
            return numeric, [tokens[i]], i

    # Priority 2: Pure digits immediately preceding the date tokens
    for i in range(end_idx - 1, max(start_idx - 1, end_idx - 4), -1):
        clean_num = tokens[i].text.strip(".,;:_— •*~#=+!?/\\()[]{}<>\"'|")
        if clean_num.isdigit() and 2 <= len(clean_num) <= 5:
            return clean_num, [tokens[i]], i

    return "", [], None
