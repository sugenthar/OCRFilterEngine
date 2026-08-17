"""IMEI 1 (strict/digit candidate) and IMEI 2 (masked/symbol-preserved candidate) extraction."""

import re
from typing import List, Tuple

from ocr.tokens import OCRToken


def clean_imei_token(text: str) -> str:
    return text.strip(".,;:_— •*~#=+!?/\\()[]{}<>\"'|")


def extract_imei_pair(
    tokens: List[OCRToken],
    start_idx: int,
    end_idx: int,
) -> Tuple[str, List[OCRToken], str, List[OCRToken]]:
    """Extract and cleanly separate IMEI 1 and IMEI 2 from the candidate token span.
    
    IMEI 1 is strictly the clean number / digit structure (must form 15 digits).
    IMEI 2 contains symbol-masked characters (%, $, *, ?, @, !, &, #, |, +).
    """
    raw_span = [t for t in tokens[start_idx:end_idx] if t.text.strip() not in {"—", "•", "=", "~="}]
    if not raw_span:
        return "", [], "", []

    # Exclude any leading alphanumeric model identifier that may have leaked into span
    span_tokens: List[OCRToken] = []
    for idx, t in enumerate(raw_span):
        c_text = clean_imei_token(t.text)
        # If token has letters and digits (e.g. T722, MC60) and is at the start of span, exclude from IMEI
        if not span_tokens and any(c.isalpha() for c in c_text) and not re.search(r"[%$*?@!&#|]", c_text):
            continue
        span_tokens.append(t)

    imei_1_toks: List[OCRToken] = []
    imei_2_toks: List[OCRToken] = []
    in_imei_2 = False

    for t in span_tokens:
        txt = t.text
        # Detect transition to masked IMEI 2 if token contains masking symbols
        if re.search(r"[%$*?@!&#|]", txt) and not in_imei_2 and imei_1_toks:
            in_imei_2 = True

        if not in_imei_2:
            imei_1_toks.append(t)
        else:
            imei_2_toks.append(t)

    # If all tokens ended up in IMEI 1 without symbols, check if there's a two-block split
    if not imei_2_toks and len(imei_1_toks) >= 4:
        digits_all = "".join(c for t in imei_1_toks for c in t.text if c.isdigit())
        if len(digits_all) > 15:
            mid = len(imei_1_toks) // 2
            imei_2_toks = imei_1_toks[mid:]
            imei_1_toks = imei_1_toks[:mid]

    imei1_val = " ".join(t.text for t in imei_1_toks).strip(" .,;:_~")
    imei2_val = " ".join(t.text for t in imei_2_toks).strip(" .,;:_~")

    return imei1_val, imei_1_toks, imei2_val, imei_2_toks
