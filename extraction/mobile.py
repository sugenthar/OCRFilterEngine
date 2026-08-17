"""Mobile, SIM, Network, Service Provider, and Reference number extraction."""

import re
from typing import List, Optional, Tuple

from ocr.tokens import OCRToken
from extraction.dictionaries import MODEL_BRANDS, NETWORKS, PLAN_STARTS, PROVIDERS_MAP


def clean_mobile_token(text: str) -> str:
    return text.strip(".,;:_—- •*~#=+!?/\\()[]{}<>\"'|")


def extract_service_provider(tokens: List[OCRToken], start_idx: int) -> Tuple[str, List[OCRToken], str, int]:
    """Extract Service Provider and any attached File Ref prefix, returning (prov_name, prov_toks, file_ref_prefix, prov_idx)."""
    for i in range(start_idx, len(tokens)):
        norm = tokens[i].normalized_text
        for key, name in PROVIDERS_MAP:
            if norm.startswith(key):
                if key in ('o2', '02') and len(norm) > 4:
                    continue
                rem = tokens[i].text[len(key):].strip(" =-_~:;,.|")
                file_ref_prefix = rem if rem and any(c.isalpha() for c in rem) else ""
                return name, [tokens[i]], file_ref_prefix, i
    return "", [], "", len(tokens)


def extract_network_type(tokens: List[OCRToken], start_idx: int) -> Tuple[str, List[OCRToken], int]:
    """Extract Network Type (GSM, CDMA, CDMA+GSM, CDMA+CDMA)."""
    for i in range(start_idx, len(tokens)):
        norm = tokens[i].normalized_text
        if norm in NETWORKS:
            val = "CDMA+GSM" if ("cdma" in norm and "gsm" in norm) else ("CDMA+CDMA" if "cdmacdma" in norm else norm.upper())
            return val, [tokens[i]], i
    return "", [], start_idx


def extract_mobile_model(tokens: List[OCRToken], start_idx: int) -> Tuple[str, List[OCRToken], int]:
    """Extract Mobile Model Brand + Model Name (e.g. Siemens MC60, Nokia 7210, Samsung S40, T722).
    
    Guarantees complete consumption of model designation so model digits/letters never leak into IMEI 1.
    """
    for i in range(start_idx, len(tokens)):
        norm = tokens[i].normalized_text
        clean_text = clean_mobile_token(tokens[i].text)
        if not clean_text or clean_text in {"=", "-", "~=", "•"}:
            continue

        # Stop if token belongs to plan type or network
        if any(norm.startswith(p) for p in PLAN_STARTS) or norm in NETWORKS:
            continue

        # Case 1: Token matches a known mobile brand (e.g. Nokia, Siemens, Samsung, Apple, Motorola)
        if any(norm.startswith(b) for b in MODEL_BRANDS):
            model_toks = [tokens[i]]
            m_parts = [clean_text]
            next_idx = i + 1

            while next_idx < len(tokens):
                nxt_tok = tokens[next_idx]
                nxt_norm = nxt_tok.normalized_text
                nxt_clean = clean_mobile_token(nxt_tok.text)

                if not nxt_clean or nxt_clean in {"=", "-", "~=", "•"}:
                    next_idx += 1
                    continue

                # Stop if next token is a plan start, network type, or looks like the start of the 15-digit IMEI
                if any(nxt_norm.startswith(p) for p in PLAN_STARTS) or nxt_norm in NETWORKS:
                    break
                if re.match(r"^\d{5,}$", nxt_norm):
                    break

                # Accept model suffix tokens (e.g. MC60, 6800, 7210, S40, AP75, Note, Pro, Plus, Ultra, Mini)
                if (
                    any(c.isdigit() for c in nxt_norm)
                    or len(nxt_norm) <= 6
                    or nxt_norm in {"galaxy", "iphone", "lumia", "experia", "xperia", "plus", "pro", "max"}
                ):
                    model_toks.append(nxt_tok)
                    m_parts.append(nxt_clean)
                    next_idx += 1
                    if len(m_parts) >= 3:
                        break
                else:
                    break

            model_val = " ".join(m_parts)
            return model_val, model_toks, next_idx

        # Case 2: Model identifier without explicit brand prefix (e.g. T722, MC60, S40, AP75, V60)
        # An alphanumeric model identifier starts with letter(s) and contains digits, or is a short model token
        # followed by numeric IMEI sequence
        is_alphanumeric_model = bool(
            re.match(r"^[A-Za-z]+[0-9]+[A-Za-z0-9]*$", clean_text)
            or (clean_text.isalnum() and any(c.isalpha() for c in clean_text) and any(c.isdigit() for c in clean_text))
            or (clean_text.isdigit() and len(clean_text) in (3, 4) and i + 1 < len(tokens) and re.match(r"^\d{5,}$", tokens[i + 1].normalized_text))
        )

        if is_alphanumeric_model:
            # Verify that following tokens represent the IMEI sequence
            remaining_tokens = [t for t in tokens[i + 1:] if clean_mobile_token(t.text) not in {"", "=", "-", "~="}]
            if remaining_tokens:
                model_toks = [tokens[i]]
                model_val = clean_text
                return model_val, model_toks, i + 1

    return "", [], start_idx


def extract_file_ref(
    tokens: List[OCRToken],
    start_idx: int,
    file_ref_prefix: str,
) -> Tuple[str, List[OCRToken], int]:
    """Extract File Ref (e.g. Tango - 4616541, Foxtrot - 288262831)."""
    fref_tokens = []
    fref_parts = [file_ref_prefix] if file_ref_prefix else []
    curr_i = start_idx

    while curr_i < len(tokens):
        t_norm = tokens[curr_i].normalized_text
        t_text = clean_mobile_token(tokens[curr_i].text)
        if not t_text or t_text in {"=", "-", "~=", "•"}:
            curr_i += 1
            continue
        # Stop at Reference No / SIM / Network / Model tokens
        if re.search(r"ORN|VFONE|VIR|HUWH|T-M|VW|GSM|CDMA|NOKIA|SIEMENS|SAMSUNG|APPLE|MOTOROLA", t_norm, re.I):
            break
        fref_tokens.append(tokens[curr_i])
        fref_parts.append(t_text)
        curr_i += 1
        if re.match(r"^\d{5,10}$", t_norm):
            break

    fref_val = ""
    if fref_parts:
        if len(fref_parts) > 1 and not any("-" in p for p in fref_parts):
            fref_val = " - ".join(fref_parts)
        else:
            fref_val = " ".join(fref_parts)

    return fref_val, fref_tokens, curr_i


def extract_reference_no(tokens: List[OCRToken], start_idx: int) -> Tuple[str, List[OCRToken], int]:
    """Extract Reference No starting with provider code (ORN, Vfone, VIR, HuWh, T-M, O2, TM)."""
    curr_i = start_idx
    while curr_i < len(tokens):
        t_norm = tokens[curr_i].normalized_text
        t_text = tokens[curr_i].text.strip("= ")
        if re.match(r"^(ORN|VFONE|VIR|HUWH|T-M|O2|TM)", t_norm, re.I):
            return t_text, [tokens[curr_i]], curr_i + 1
        curr_i += 1
    return "", [], start_idx


def extract_sim_no(tokens: List[OCRToken], start_idx: int) -> Tuple[str, List[OCRToken], int]:
    """Extract SIM No (10-22 character alphanumeric token)."""
    curr_i = start_idx
    while curr_i < len(tokens):
        t_norm = tokens[curr_i].normalized_text
        t_text = clean_mobile_token(tokens[curr_i].text)
        if t_norm in NETWORKS or any(t_norm.startswith(b) for b in MODEL_BRANDS):
            break
        if len(t_norm) >= 10 and any(c.isdigit() for c in t_norm) and any(c.isalpha() for c in t_norm):
            return t_text, [tokens[curr_i]], curr_i + 1
        curr_i += 1
    return "", [], start_idx
