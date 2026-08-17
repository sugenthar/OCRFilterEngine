"""Targeted Multi-Pass Re-OCR and Candidate Consensus Engine."""

from collections import Counter
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image
import pytesseract
from pytesseract import Output

from ocr.preprocessing import (
    preprocess_crop_adaptive_threshold,
    preprocess_crop_otsu_binarize,
    preprocess_crop_upscale_contrast,
    preprocess_target_crop,
)
from ocr.tokens import BoundingBox, OCRToken
from extraction.postcode import is_valid_postcode, repair_postcode_characters

logger = logging.getLogger(__name__)

DEFAULT_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Field-specific Tesseract whitelist configurations (no unquoted spaces)
FIELD_WHITELISTS: Dict[str, str] = {
    "IMEI 1": "0123456789-",
    "Contact": "0123456789",
    "DOB": "0123456789/",
    "Issue Date": "0123456789/",
    "Renewal Date": "0123456789/",
    "First Name": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-'",
    "Last Name": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-'",
    "Father Name": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-.'",
    "City": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ,-",
    "Mailing Street": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789,-./",
}


@dataclass
class TargetedCandidate:
    raw_text: str
    cleaned_value: str
    confidence: float
    variant: str
    psm: int
    is_whitelist: bool
    is_valid_structure: bool
    tokens: List[OCRToken] = field(default_factory=list)


def _ensure_tesseract_configured(tesseract_cmd: Optional[str] = None) -> None:
    if tesseract_cmd and os.path.exists(tesseract_cmd):
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    elif not pytesseract.pytesseract.tesseract_cmd or pytesseract.pytesseract.tesseract_cmd == "tesseract":
        if os.path.exists(DEFAULT_TESSERACT_PATH):
            pytesseract.pytesseract.tesseract_cmd = DEFAULT_TESSERACT_PATH


def re_ocr_region(
    image_input: Union[Path, str, Image.Image],
    bbox: BoundingBox,
    padding: int = 6,
    psm: int = 7,
    upscale_factor: float = 3.0,
    tesseract_cmd: Optional[str] = None,
) -> List[OCRToken]:
    """Crop a bounding box region with padding, preprocess, and run single-pass OCR."""
    _ensure_tesseract_configured(tesseract_cmd)

    if isinstance(image_input, (str, Path)):
        with Image.open(image_input) as img:
            full_img = img.copy()
    elif isinstance(image_input, Image.Image):
        full_img = image_input.copy()
    else:
        return []

    img_w, img_h = full_img.size
    crop_x1 = max(0, bbox.x - padding)
    crop_y1 = max(0, bbox.y - padding)
    crop_x2 = min(img_w, bbox.x + bbox.width + padding)
    crop_y2 = min(img_h, bbox.y + bbox.height + padding)

    if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
        return []

    cropped = full_img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
    proc_crop = preprocess_target_crop(cropped, scale=upscale_factor)

    config = f"--psm {psm} --oem 3"
    data = pytesseract.image_to_data(proc_crop, output_type=Output.DICT, config=config)

    tokens: List[OCRToken] = []
    n_boxes = len(data["text"])
    for i in range(n_boxes):
        text = str(data["text"][i]).strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        if conf < 0:
            continue

        token_rel_x = int(round(data["left"][i] / upscale_factor))
        token_rel_y = int(round(data["top"][i] / upscale_factor))
        token_w = int(round(data["width"][i] / upscale_factor))
        token_h = int(round(data["height"][i] / upscale_factor))

        orig_x = crop_x1 + token_rel_x
        orig_y = crop_y1 + token_rel_y

        tok_bbox = BoundingBox(x=orig_x, y=orig_y, width=token_w, height=token_h)
        tokens.append(
            OCRToken(
                text=text,
                bbox=tok_bbox,
                confidence=round(conf, 2),
                needs_review=conf < 60.0,
                variant="targeted_crop",
            )
        )

    return tokens


def run_multi_pass_targeted_ocr(
    image_input: Union[Path, str, Image.Image],
    field_name: str,
    bbox: BoundingBox,
    padding: int = 6,
    tesseract_cmd: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute multi-pass targeted OCR across multiple preprocessors and PSMs with candidate consensus."""
    _ensure_tesseract_configured(tesseract_cmd)

    if isinstance(image_input, (str, Path)):
        with Image.open(image_input) as img:
            full_img = img.copy()
    elif isinstance(image_input, Image.Image):
        full_img = image_input.copy()
    else:
        return {"attempted": False, "decision": "INVALID_IMAGE_INPUT"}

    img_w, img_h = full_img.size
    crop_x1 = max(0, bbox.x - padding)
    crop_y1 = max(0, bbox.y - padding)
    crop_x2 = min(img_w, bbox.x + bbox.width + padding)
    crop_y2 = min(img_h, bbox.y + bbox.height + padding)

    if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
        return {"attempted": False, "decision": "EMPTY_CROP_REGION"}

    cropped = full_img.crop((crop_x1, crop_y1, crop_x2, crop_y2))

    # Preprocessing variations
    preproc_variants = [
        ("3x_contrast", preprocess_crop_upscale_contrast(cropped, scale=3.0), 3.0),
        ("4x_contrast", preprocess_crop_upscale_contrast(cropped, scale=4.0), 4.0),
        ("4x_otsu", preprocess_crop_otsu_binarize(cropped, scale=4.0), 4.0),
        ("3x_adaptive", preprocess_crop_adaptive_threshold(cropped, scale=3.0), 3.0),
    ]

    psm_modes = [7, 8, 6, 13]
    whitelist = FIELD_WHITELISTS.get(field_name)

    candidates: List[TargetedCandidate] = []
    all_runs: List[Dict[str, Any]] = []

    for var_name, proc_img, scale in preproc_variants:
        for psm in psm_modes:
            configs_to_run = [(f"--psm {psm} --oem 3", False)]
            if whitelist:
                configs_to_run.append((f"--psm {psm} --oem 3 -c tessedit_char_whitelist={whitelist}", True))

            for cfg, is_wl in configs_to_run:
                try:
                    data = pytesseract.image_to_data(proc_img, output_type=Output.DICT, config=cfg)
                except Exception as exc:
                    logger.debug("Targeted OCR pass failed: cfg=%s error=%s", cfg, exc)
                    all_runs.append({
                        "variant": var_name,
                        "psm": psm,
                        "whitelist": is_wl,
                        "raw_text": "",
                        "cleaned": "",
                        "confidence": 0.0,
                        "is_valid": False,
                    })
                    continue

                tok_texts = []
                tok_confs = []
                tok_objects = []

                n_boxes = len(data.get("text", []))
                for i in range(n_boxes):
                    t = str(data["text"][i]).strip()
                    if not t:
                        continue
                    try:
                        c = float(data["conf"][i])
                    except (ValueError, TypeError):
                        c = -1.0
                    if c < 0:
                        continue
                    tok_texts.append(t)
                    tok_confs.append(c)

                    rel_x = int(round(data["left"][i] / scale))
                    rel_y = int(round(data["top"][i] / scale))
                    tw = int(round(data["width"][i] / scale))
                    th = int(round(data["height"][i] / scale))
                    tok_objects.append(
                        OCRToken(
                            text=t,
                            bbox=BoundingBox(crop_x1 + rel_x, crop_y1 + rel_y, tw, th),
                            confidence=round(c, 2),
                            variant=var_name,
                        )
                    )

                raw_line = " ".join(tok_texts).strip()
                valid_tok_confs = [c for c in tok_confs if c > 0]
                avg_conf = round(sum(valid_tok_confs) / len(valid_tok_confs), 2) if valid_tok_confs else (round(sum(tok_confs) / len(tok_confs), 2) if tok_confs else 0.0)

                # Structure validation and span isolation based on field type
                cleaned_val = raw_line
                is_valid = False
                field_owned_tokens = tok_objects
                excluded_tokens = []

                if field_name == "IMEI 1":
                    # Separate any leading model or network tokens outside the numeric IMEI span
                    numeric_toks = []
                    for t in tok_objects:
                        t_clean = t.text.strip(".,;:_—- •*~#=+!?/\\()[]{}<>\"'|")
                        if not numeric_toks and any(c.isalpha() for c in t_clean) and not re.search(r"[%$*?@!&#|]", t_clean):
                            excluded_tokens.append(t)
                            logger.info("IMEI1 TOKENS: excluded model token=%r bbox=%s", t.text, t.bbox.to_dict())
                        else:
                            numeric_toks.append(t)
                            logger.info("IMEI1 TOKENS: included token=%r bbox=%s", t.text, t.bbox.to_dict())

                    field_owned_tokens = numeric_toks if numeric_toks else tok_objects
                    digits = "".join(c for t in field_owned_tokens for c in t.text if c.isdigit())
                    cleaned_val = digits
                    is_valid = len(digits) == 15

                    logger.info(
                        "IMEI1 NUMERIC PASS: Variant=%s PSM=%d Whitelist=%s Raw=%r Candidate=%r Valid=%s Conf=%.1f",
                        var_name, psm, is_wl, raw_line, cleaned_val, is_valid, avg_conf,
                    )
                elif field_name == "Postal Code":
                    repaired = repair_postcode_characters(raw_line)
                    cleaned_val = repaired
                    is_valid = is_valid_postcode(repaired)
                elif field_name in ("Issue Date", "Renewal Date", "DOB"):
                    date_match = re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", raw_line)
                    if date_match:
                        cleaned_val = date_match.group(0)
                        is_valid = True
                elif field_name == "Contact":
                    digits = re.sub(r"\D", "", raw_line)
                    cleaned_val = digits
                    is_valid = bool(digits and digits.isdigit())
                elif field_name in ("First Name", "Last Name", "Father Name"):
                    cleaned_val = raw_line.strip(".,;:_—- •*~#=+!?/\\()[]{}<>\"'|")
                    is_valid = bool(cleaned_val and any(c.isalpha() for c in cleaned_val))
                elif field_name in ("Mailing Street", "City", "Country"):
                    cleaned_val = raw_line.strip(".,;:_—- •*~#=+!?/\\()[]{}<>\"'|")
                    is_valid = bool(len(cleaned_val) >= 2)
                else:
                    is_valid = len(raw_line) > 0

                all_runs.append({
                    "variant": var_name,
                    "psm": psm,
                    "whitelist": is_wl,
                    "raw_text": raw_line,
                    "cleaned": cleaned_val,
                    "confidence": avg_conf,
                    "is_valid": is_valid,
                })

                if tok_texts:
                    cand = TargetedCandidate(
                        raw_text=raw_line,
                        cleaned_value=cleaned_val,
                        confidence=avg_conf,
                        variant=var_name,
                        psm=psm,
                        is_whitelist=is_wl,
                        is_valid_structure=is_valid,
                        tokens=field_owned_tokens,
                    )
                    candidates.append(cand)

                if field_name != "IMEI 1":
                    logger.info(
                        "TARGETED OCR: Field=%s Region=%s Variant=%s PSM=%d Whitelist=%s Result=%r Candidate=%r Valid=%s Conf=%.1f",
                        field_name, bbox.to_dict(), var_name, psm, is_wl, raw_line, cleaned_val, is_valid, avg_conf,
                    )

    if not candidates:
        return {
            "attempted": True,
            "decision": "NO_OCR_OUTPUT",
            "candidates_evaluated": 0,
            "result": "",
            "confidence": 0.0,
            "runs": all_runs,
        }

    # Consensus and Validation Engine
    valid_candidates = [c for c in candidates if c.is_valid_structure]

    if field_name == "IMEI 1":
        # Must be strictly 15 digits
        fifteen_digit_candidates = [c for c in valid_candidates if len(c.cleaned_value) == 15 and c.cleaned_value.isdigit()]
        if fifteen_digit_candidates:
            counts = Counter(c.cleaned_value for c in fifteen_digit_candidates)
            best_val, vote_count = counts.most_common(1)[0]
            matching_cands = [c for c in fifteen_digit_candidates if c.cleaned_value == best_val]
            pos_confs = [c.confidence for c in matching_cands if c.confidence > 0]
            mean_conf = round(sum(pos_confs) / len(pos_confs), 2) if pos_confs else max(c.confidence for c in matching_cands)
            
            if mean_conf >= 55.0 or vote_count >= 2:
                best_cand = max(matching_cands, key=lambda c: c.confidence)
                decision = "ACCEPTED_STRICT_IMEI"
                logger.info(
                    "IMEI1 CONSENSUS: Candidate=%s Support=%d MeanConfidence=%.1f Decision=%s",
                    best_val, vote_count, mean_conf, decision,
                )
                return {
                    "attempted": True,
                    "decision": decision,
                    "value": best_val,
                    "raw_text": best_cand.raw_text,
                    "confidence": mean_conf,
                    "votes": vote_count,
                    "tokens": [t.to_dict() for t in best_cand.tokens],
                    "runs": all_runs,
                }

        logger.warning(
            "IMEI1 CONSENSUS: ValidCandidates=%d Decision=NO_SAFE_CORRECTION",
            len(fifteen_digit_candidates),
        )
        return {
            "attempted": True,
            "decision": "NO_SAFE_CORRECTION",
            "reason": "INVALID_IMEI1",
            "detail": "No confident 15-digit candidate produced from IMEI 1 region",
            "runs": all_runs,
        }

    elif field_name == "Postal Code":
        valid_postcodes = [c for c in valid_candidates if is_valid_postcode(c.cleaned_value)]
        if valid_postcodes:
            counts = Counter(c.cleaned_value for c in valid_postcodes)
            best_pc, vote_count = counts.most_common(1)[0]
            matching_cands = [c for c in valid_postcodes if c.cleaned_value == best_pc]
            pos_confs = [c.confidence for c in matching_cands if c.confidence > 0]
            mean_conf = round(sum(pos_confs) / len(pos_confs), 2) if pos_confs else max(c.confidence for c in matching_cands)

            logger.info("CONSENSUS: Field=Postal Code Candidate=%s Votes=%d Confidence=%.1f", best_pc, vote_count, mean_conf)

            if mean_conf >= 55.0 or vote_count >= 2:
                best_cand = max(matching_cands, key=lambda c: c.confidence)
                return {
                    "attempted": True,
                    "decision": "ACCEPTED_POSTCODE",
                    "value": best_pc,
                    "raw_text": best_cand.raw_text,
                    "confidence": mean_conf,
                    "votes": vote_count,
                    "tokens": [t.to_dict() for t in best_cand.tokens],
                    "runs": all_runs,
                }

        return {
            "attempted": True,
            "decision": "NO_SAFE_CORRECTION",
            "reason": "INVALID_POSTAL_CODE",
            "detail": "Postal code candidates remain ambiguous after multi-pass OCR",
            "runs": all_runs,
        }

    # General field consensus
    if valid_candidates:
        counts = Counter(c.cleaned_value for c in valid_candidates)
        best_val, vote_count = counts.most_common(1)[0]
        matching_cands = [c for c in valid_candidates if c.cleaned_value == best_val]
        pos_confs = [c.confidence for c in matching_cands if c.confidence > 0]
        mean_conf = round(sum(pos_confs) / len(pos_confs), 2) if pos_confs else max(c.confidence for c in matching_cands)
        best_cand = max(matching_cands, key=lambda c: c.confidence)

        if mean_conf >= 55.0 or vote_count >= 2:
            return {
                "attempted": True,
                "decision": "ACCEPTED_CONSENSUS",
                "value": best_val,
                "raw_text": best_cand.raw_text,
                "confidence": mean_conf,
                "votes": vote_count,
                "tokens": [t.to_dict() for t in best_cand.tokens],
                "runs": all_runs,
            }

    return {
        "attempted": True,
        "decision": "NO_SAFE_CORRECTION",
        "runs": all_runs,
    }
