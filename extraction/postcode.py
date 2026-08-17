"""UK Postal Code extraction, normalization, and validation."""

import re
from typing import Optional

# UK Postcode pattern: 1-2 letters + 1-2 digits/alphanumeric + optional space + 1 digit + 2 letters
# Outward code MUST have at least 1 digit (e.g. BN1, LS16, SW1A, M1, EC1A). BNI is invalid.
# Inward code MUST be 1 digit + 2 letters (e.g. 2FN, 8AG, 1AA).
POSTCODE_STRICT_REGEX = re.compile(
    r"^([A-Z]{1,2}\d[A-Z0-9]?)\s*(\d[A-Z]{2})$",
    re.IGNORECASE,
)

POSTCODE_SPECIAL_REGEX = re.compile(
    r"^(GIR\s*0AA|SAN\s*TA1|[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})$",
    re.IGNORECASE,
)


def repair_postcode_characters(raw_text: str) -> str:
    """Contextually fix common OCR character confusions inside a postal code candidate."""
    cleaned = raw_text.strip(".,;:_—- •*~#=+!?/\\()[]{}<>\"'|`").upper()
    cleaned = cleaned.replace("]", "1").replace("[", "1").replace("|", "1").replace("!", "1")
    cleaned = re.sub(r"\s+", " ", cleaned)
    no_spaces = cleaned.replace(" ", "")
    
    if len(no_spaces) < 5 or len(no_spaces) > 8:
        return raw_text.strip()

    # Outward code (first 2-4 chars) + Inward code (last 3 chars: 1 digit + 2 letters)
    outward = no_spaces[:-3]
    inward = no_spaces[-3:]

    # Inward code must be: 1 Digit + 2 Letters
    inward_d = inward[0]
    if inward_d in {'O', 'D', 'Q'}:
        inward_d = '0'
    elif inward_d in {'I', 'L', '|', ']', '!'}:
        inward_d = '1'
    elif inward_d in {'Z'}:
        inward_d = '2'
    elif inward_d in {'S'}:
        inward_d = '5'
    elif inward_d in {'B'}:
        inward_d = '8'

    # Last two chars of inward must be letters
    inward_l1 = inward[1]
    if inward_l1 in {'0', 'Q'}:
        inward_l1 = 'O'
    elif inward_l1 in {'1', '|', ']'}:
        inward_l1 = 'I'
    elif inward_l1 == '8':
        inward_l1 = 'B'
    elif inward_l1 == '2':
        inward_l1 = 'Z'
    elif inward_l1 == '5':
        inward_l1 = 'S'

    inward_l2 = inward[2]
    if inward_l2 in {'0', 'Q'}:
        inward_l2 = 'O'
    elif inward_l2 in {'1', '|', ']'}:
        inward_l2 = 'I'
    elif inward_l2 == '8':
        inward_l2 = 'B'
    elif inward_l2 == '2':
        inward_l2 = 'Z'
    elif inward_l2 == '5':
        inward_l2 = 'S'

    # Outward code fixes:
    # First 1-2 chars must be letters
    out_chars = list(outward)
    if out_chars and out_chars[0] in {'0', 'Q'}:
        out_chars[0] = 'O'
    elif out_chars and out_chars[0] in {'1', '|', ']'}:
        out_chars[0] = 'I'

    # Characters in outward positions 2/3 (if digits)
    for idx in range(1, len(out_chars)):
        if out_chars[idx] in {'I', 'L', '|', ']'}:
            out_chars[idx] = '1'
        elif out_chars[idx] == 'O' and idx > 1:
            out_chars[idx] = '0'

    repaired_outward = "".join(out_chars)
    repaired_inward = f"{inward_d}{inward_l1}{inward_l2}"
    candidate = f"{repaired_outward} {repaired_inward}"

    if is_valid_postcode(candidate):
        return candidate
    return raw_text.strip()


def is_valid_postcode(text: str) -> bool:
    """Validate if the string matches a recognized UK postcode format."""
    cleaned = text.strip().upper()
    return bool(POSTCODE_STRICT_REGEX.match(cleaned) or POSTCODE_SPECIAL_REGEX.match(cleaned))
