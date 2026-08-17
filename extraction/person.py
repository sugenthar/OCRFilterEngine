"""Person identity fields extraction: Title, First Name, Last Name, Father Name, Gender, Profession."""

import re
from typing import List, Optional, Tuple
from ocr.tokens import OCRToken
from extraction.dictionaries import PROFESSIONS_MAP

EXACT_TITLES = {
    "mr", "mrs", "ms", "miss", "dr", "prof", "major general",
    "rev", "sir", "lady", "capt", "col", "hon",
}


def clean_person_token(text: str) -> str:
    return text.strip(".,;:_—- •*~#=+!?/\\()[]{}<>\"'|")


def extract_title(tokens: List[OCRToken], start_idx: int = 0) -> Tuple[str, List[OCRToken], int]:
    """Extract and normalize title, returning (title_val, title_tokens, next_token_index)."""
    title_idx = start_idx
    while title_idx < len(tokens):
        t_norm = tokens[title_idx].normalized_text
        if t_norm and any(c.isalpha() for c in t_norm) and t_norm not in {"—", "©", "•", "_", "=", "-"}:
            break
        title_idx += 1

    if title_idx >= len(tokens):
        return "Mr", [], start_idx

    w0_norm = tokens[title_idx].normalized_text
    w1_norm = tokens[title_idx + 1].normalized_text if title_idx + 1 < len(tokens) else ""

    if w0_norm == "major" and w1_norm.startswith("general"):
        title_val = "Major General"
        title_tokens = tokens[title_idx:title_idx + 2]
        next_idx = title_idx + 2
    else:
        title_tokens = [tokens[title_idx]]
        next_idx = title_idx + 1
        if w0_norm in {"mr", "mr."}:
            title_val = "Mr"
        elif w0_norm in {"mrs", "mrs."}:
            title_val = "Mrs"
        elif w0_norm in {"ms", "ms."}:
            title_val = "Ms"
        elif w0_norm in {"miss", "mlss"}:
            title_val = "Miss"
        elif w0_norm in {"dr", "dr."}:
            title_val = "Dr"
        elif w0_norm in {"prof", "prof."}:
            title_val = "Prof"
        elif w0_norm in {"rev", "rev."}:
            title_val = "Rev"
        elif w0_norm in {"capt", "capt."}:
            title_val = "Capt"
        elif w0_norm in {"col", "col."}:
            title_val = "Col"
        elif w0_norm in {"sir"}:
            title_val = "Sir"
        elif w0_norm in {"lady"}:
            title_val = "Lady"
        elif w0_norm in {"hon", "hon."}:
            title_val = "Hon"
        else:
            title_val = clean_person_token(tokens[title_idx].text).capitalize()

    return title_val, title_tokens, next_idx


def extract_names(
    tokens: List[OCRToken],
    start_idx: int,
    end_idx: int,
    pre_last_name: str = "",
) -> Tuple[str, List[OCRToken], str, List[OCRToken]]:
    """Extract First Name and Last Name cleanly from the name span."""
    name_tokens = [t for t in tokens[start_idx:end_idx] if t.normalized_text not in {"—", "©", "•", "_", "=", "-"}]
    
    expanded: List[Tuple[OCRToken, str]] = []
    for t in name_tokens:
        for part in t.text.strip().split():
            c_part = clean_person_token(part)
            if c_part:
                expanded.append((t, c_part))

    first_val, first_toks = "", []
    last_val, last_toks = "", []

    if len(expanded) >= 2:
        first_toks = [expanded[0][0]]
        first_val = expanded[0][1]
        last_toks = [item[0] for item in expanded[1:]]
        last_val = " ".join(item[1] for item in expanded[1:])
    elif len(expanded) == 1:
        t_obj, t_text = expanded[0]
        # Check CamelCase split (e.g. HillaryBenton -> Hillary, Benton)
        cmatch = re.fullmatch(r"([A-Z][a-z]+)([A-Z][a-z]+)", t_text)
        if cmatch:
            first_val = cmatch.group(1)
            first_toks = [t_obj]
            last_val = cmatch.group(2)
            last_toks = [t_obj]
        elif pre_last_name:
            first_val = t_text
            first_toks = [t_obj]
            last_val = pre_last_name
            last_toks = []
        else:
            first_val = t_text
            first_toks = [t_obj]

    return first_val, first_toks, last_val, last_toks


def extract_father_name(tokens: List[OCRToken], email_idx: Optional[int], dob_idx: Optional[int]) -> Tuple[str, List[OCRToken]]:
    """Extract Father Name between Email and DOB, removing academic/honorary titles."""
    if email_idx is None or dob_idx is None or dob_idx <= email_idx:
        return "", []

    father_toks = [
        t for t in tokens[email_idx + 1:dob_idx]
        if t.normalized_text not in {"©", "—", "+", "=", "_", "•", "-", ""}
    ]
    if not father_toks:
        return "", []

    f_raw = " ".join(t.text for t in father_toks).strip()
    f_val = clean_person_token(f_raw)
    
    # Strip prefix titles like Phy.D, Ph.D, Dr, Mr, Mrs, Ms, Prof
    f_val = re.sub(r"^(phy\.?d|ph\.?d|dr|mr|mrs|ms|prof)\.?\s*", "", f_val, flags=re.I).strip()
    
    # Split joined tokens like BrettM.Joseph -> Brett M. Joseph or JuanCoyle -> Juan Coyle
    f_val = re.sub(r"([a-z])([A-Z])", r"\1 \2", f_val)
    f_val = re.sub(r"([A-Z]\.)([A-Z])", r"\1 \2", f_val)

    return f_val, father_toks


def extract_gender(tokens: List[OCRToken]) -> Tuple[str, List[OCRToken], Optional[int]]:
    """Locate and normalize Gender (Male / Female)."""
    for idx, t in enumerate(tokens):
        norm = t.normalized_text
        if norm in {"male", "ma1e", "maie"}:
            return "Male", [t], idx
        elif norm in {"female", "fe-male", "femate", "fema1e"}:
            return "Female", [t], idx
    return "", [], None


def extract_profession(tokens: List[OCRToken], start_idx: int) -> Tuple[str, List[OCRToken], int]:
    """Extract and normalize profession using controlled profession dictionary."""
    for i in range(start_idx, min(start_idx + 6, len(tokens))):
        t_norm = tokens[i].normalized_text
        t_next = tokens[i + 1].normalized_text if i + 1 < len(tokens) else ""
        pair = f"{t_norm} {t_next}".strip()

        if pair in PROFESSIONS_MAP:
            return PROFESSIONS_MAP[pair], tokens[i:i + 2], i + 2
        if t_norm in PROFESSIONS_MAP:
            return PROFESSIONS_MAP[t_norm], [tokens[i]], i + 1

    return "", [], start_idx
