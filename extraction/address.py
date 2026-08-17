"""Address extraction: Mailing Street, City, Postal Code, and Country."""

import re
from typing import List, Optional, Tuple

from ocr.tokens import OCRToken
from extraction.dictionaries import COUNTRIES, STREET_SUFFIX_PATTERN
from extraction.postcode import is_valid_postcode, repair_postcode_characters


def clean_address_token(text: str) -> str:
    return text.strip(".,;:_—- •*~#=+!?/\\()[]{}<>\"'|")


def extract_address_block(
    tokens: List[OCRToken],
    start_idx: int,
    end_idx: int,
) -> Tuple[str, List[OCRToken], str, List[OCRToken], str, List[OCRToken], str, List[OCRToken]]:
    """Extract Mailing Street, City, Postal Code, and Country from the address token span."""
    addr_tokens = [t for t in tokens[start_idx:end_idx] if t.normalized_text not in {"|", "•", "—", "=", "-"}]

    # 1. Extract Country (from the end of address block)
    country_val, country_toks = "", []
    country_idx = None
    for idx in range(len(addr_tokens) - 1, -1, -1):
        alpha = re.sub(r"[^a-zA-Z]", "", addr_tokens[idx].text).lower()
        if alpha in COUNTRIES:
            country_idx = idx
            country_val = COUNTRIES[alpha]
            country_toks = [addr_tokens[idx]]
            break

    if country_idx is not None:
        addr_tokens = addr_tokens[:country_idx] + addr_tokens[country_idx + 1:]

    # 2. Extract Postal Code
    postcode_val, postcode_toks = "", []
    postcode_idx = None
    for idx in range(len(addr_tokens) - 1, -1, -1):
        txt = clean_address_token(addr_tokens[idx].text)
        if is_valid_postcode(txt):
            postcode_idx = idx
            postcode_toks = [addr_tokens[idx]]
            postcode_val = repair_postcode_characters(txt)
            break
        elif idx > 0:
            pair = f"{clean_address_token(addr_tokens[idx - 1].text)} {clean_address_token(addr_tokens[idx].text)}"
            if is_valid_postcode(pair):
                postcode_idx = idx - 1
                postcode_toks = [addr_tokens[idx - 1], addr_tokens[idx]]
                postcode_val = repair_postcode_characters(pair)
                break

    if postcode_idx is not None:
        addr_tokens = addr_tokens[:postcode_idx]

    # 3. Separate Remaining tokens into Mailing Street and City
    street_val, street_toks = "", []
    city_val, city_toks = "", []

    if addr_tokens:
        split_done = False

        # Check for street suffix ending position in addr_tokens
        # Look for the last token that ends with or contains a street suffix (Road, Street, Lane, Avenue, Drive, Way, Square, Building, House, Park)
        suffix_idx = None
        for i in range(len(addr_tokens) - 1, -1, -1):
            t_txt = addr_tokens[i].text.rstrip(",;")
            if STREET_SUFFIX_PATTERN.search(t_txt):
                suffix_idx = i
                break

        if suffix_idx is not None and suffix_idx < len(addr_tokens) - 1:
            street_toks = addr_tokens[:suffix_idx + 1]
            city_toks = addr_tokens[suffix_idx + 1:]
            street_val = " ".join(t.text for t in street_toks).strip(" ,;")
            city_val = " ".join(t.text for t in city_toks).strip(" ,;")
            split_done = True

        if not split_done:
            # Check for comma separator (e.g. Coxwold York,North Yorkshire or Building 500, Abbey Park, Coventry, WMD)
            comma_idx = next((i for i, token in enumerate(addr_tokens) if "," in token.text), None)
            if comma_idx is not None:
                c_tok = addr_tokens[comma_idx]
                if "," in c_tok.text and not c_tok.text.endswith(",") and not c_tok.text.startswith(","):
                    parts = c_tok.text.split(",", 1)
                    s_toks = addr_tokens[:comma_idx] + [c_tok]
                    s_val = " ".join(clean_address_token(x.text) for x in addr_tokens[:comma_idx]) + " " + clean_address_token(parts[0])
                    c_toks = [c_tok] + addr_tokens[comma_idx + 1:]
                    c_val = clean_address_token(parts[1]) + " " + " ".join(clean_address_token(x.text) for x in addr_tokens[comma_idx + 1:])
                    street_val = s_val.strip()
                    city_val = c_val.strip()
                    street_toks = s_toks
                    city_toks = c_toks
                elif comma_idx > 0:
                    street_toks = addr_tokens[:comma_idx]
                    city_toks = addr_tokens[comma_idx:]
                    street_val = " ".join(t.text for t in street_toks).strip(" ,;")
                    city_val = " ".join(t.text for t in city_toks).strip(" ,;")
                else:
                    street_toks = [addr_tokens[0]]
                    city_toks = addr_tokens[1:]
                    street_val = clean_address_token(addr_tokens[0].text)
                    city_val = " ".join(t.text for t in city_toks).strip(" ,;")
                split_done = True

        if not split_done:
            if len(addr_tokens) >= 3:
                street_toks = addr_tokens[:-1]
                city_toks = [addr_tokens[-1]]
                street_val = " ".join(t.text for t in addr_tokens[:-1]).strip(" ,;")
                city_val = clean_address_token(addr_tokens[-1].text)
            else:
                street_toks = addr_tokens
                street_val = " ".join(t.text for t in addr_tokens).strip(" ,;")

    return street_val, street_toks, city_val, city_toks, postcode_val, postcode_toks, country_val, country_toks
