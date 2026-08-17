"""Email extraction and contextual domain correction."""

import re
from typing import Optional, Tuple

EMAIL_FULL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def clean_email_token(raw_str: str) -> Tuple[str, str]:
    """Clean OCR email token, fix missing TLD dots, and extract any prefixed last name."""
    cleaned = raw_str.strip(".,;:_—- •*~#=+!?/\\()[]{}<>\"'|")
    pre_last_name = ""

    # Case 1: Underscore separator before email (e.g., Smith_smith@domain.com)
    prefix_match = re.match(r"^([A-Za-z]{2,})_([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)$", cleaned)
    if prefix_match:
        pre_last_name = prefix_match.group(1)
        email_part = prefix_match.group(2)
    else:
        # Case 2: Merged repetition (e.g., Sawreyssawrey@hilton.com)
        email_at = cleaned.find("@")
        found_merged = False
        if email_at > 0:
            local_part = cleaned[:email_at]
            local_lower = local_part.lower()
            for s_len in range(len(local_lower) // 2 + 1, 2, -1):
                suffix = local_lower[-s_len:]
                if local_lower.startswith(suffix) and len(local_part) > s_len:
                    pre_last_name = local_part[:-s_len]
                    email_part = local_part[-s_len:] + cleaned[email_at:]
                    found_merged = True
                    break
        if not found_merged:
            email_part = cleaned

    # Contextual domain corrections (only applied within email string)
    email_part = re.sub(r"@([a-zA-Z0-9-]+)(com|org|net|edu|gov)$", r"@\1.\2", email_part, flags=re.I)
    email_part = re.sub(r"@([a-zA-Z0-9-]+)couk$", r"@\1.co.uk", email_part, flags=re.I)
    email_part = re.sub(r"@([a-zA-Z0-9-]+)acuk$", r"@\1.ac.uk", email_part, flags=re.I)
    email_part = re.sub(r"@([a-zA-Z0-9-]+)ch$", r"@\1.ch", email_part, flags=re.I)
    email_part = re.sub(r"@([a-zA-Z0-9-]+)de$", r"@\1.de", email_part, flags=re.I)
    email_part = re.sub(r"@([a-zA-Z0-9-]+)fr$", r"@\1.fr", email_part, flags=re.I)
    email_part = email_part.strip(".,;:_—- •*~#=+!?/\\()[]{}<>\"'|")

    # If email contains extra leading noise before local part
    at_pos = email_part.find("@")
    if at_pos > 0:
        match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", email_part)
        if match:
            email_part = match.group(0)

    return email_part, pre_last_name
