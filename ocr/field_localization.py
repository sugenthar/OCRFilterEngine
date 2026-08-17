"""Label-first field-region localization for safe targeted OCR and spatial extraction."""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ocr.tokens import BoundingBox, OCRRow, OCRToken, RawRecord


# Controlled label aliases mapped by canonical field name
LABEL_ALIASES: Dict[str, Tuple[str, ...]] = {
    "IMEI 1": (
        "imei 1", "imei1", "imei no 1", "imei no. 1", "imei no.", "imei no",
        "imei-1", "imei #1", "imei number 1", "imei", "1mei 1", "1mei",
    ),
    "IMEI 2": (
        "imei 2", "imei2", "imei no 2", "imei no. 2", "imei-2", "imei #2",
        "imei number 2", "2nd imei", "imei(2)", "imei 2:",
    ),
    "Postal Code": (
        "postal code", "post code", "postcode", "postalcode", "pincode",
        "zip code", "zip", "post code.", "postal code.", "postcode:",
    ),
    "Reference No": (
        "reference no", "reference no.", "reference number", "ref no",
        "ref no.", "ref #", "reference", "ref. no.", "ref number",
    ),
    "SIM No": (
        "sim no", "sim no.", "sim number", "sim #", "sim", "iccid", "sim no:",
    ),
    "Contact": (
        "contact", "contact no", "contact #", "telephone", "tel", "phone", "contract",
    ),
    "Email": (
        "email", "e-mail", "email id", "email address", "email:", "e-mail:",
    ),
    "DOB": (
        "dob", "d.o.b", "d.o.b.", "date of birth", "birth date", "dob:",
    ),
    "Issue Date": (
        "issue date", "issuedate", "date of issue", "start date", "issue dt", "issue date:",
    ),
    "Renewal Date": (
        "renewal date", "renewaldate", "expiry date", "exp date", "renewal dt", "renewal date:",
    ),
    "Mobile Model": (
        "mobile model", "phone model", "model", "handset", "mobile model:", "handset model",
    ),
    "Network Type": (
        "network type", "network", "net type", "network type:",
    ),
    "Service Provider": (
        "service provider", "provider", "operator", "network provider", "service provider:",
    ),
    "Title": (
        "title", "salutation", "title:",
    ),
    "First Name": (
        "first name", "firstname", "forename", "given name", "first name:",
    ),
    "Last Name": (
        "last name", "lastname", "surname", "family name", "last name:",
    ),
    "Father Name": (
        "father name", "father's name", "father", "guardian", "father name:",
    ),
    "Gender": (
        "gender", "sex", "gender:",
    ),
    "Profession": (
        "profession", "occupation", "profession:",
    ),
    "Mailing Street": (
        "mailing street", "street", "street address", "address line 1", "address:", "street:",
    ),
    "City": (
        "city", "town", "city:",
    ),
    "Country": (
        "country", "nation", "country:",
    ),
    "Plan Type": (
        "plan type", "plan", "tariff plan", "plan type:",
    ),
    "Card Type": (
        "card type", "card", "payment card", "card type:",
    ),
    "File Ref": (
        "file ref", "file reference", "file ref:",
    ),
}


@dataclass(frozen=True)
class FieldRegion:
    field_name: str
    value_bbox: BoundingBox
    label_bbox: BoundingBox
    anchor_label: str
    confidence: float
    source: str = "label_right"  # "label_right", "label_below", "token_span", "grid_box"

    @property
    def region(self) -> List[int]:
        return [self.value_bbox.x, self.value_bbox.y, self.value_bbox.width, self.value_bbox.height]

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "region": {
                "x": self.value_bbox.x,
                "y": self.value_bbox.y,
                "width": self.value_bbox.width,
                "height": self.value_bbox.height,
            },
            "bbox": self.value_bbox.to_dict(),
            "anchor_label": self.anchor_label,
            "anchor_coordinates": self.label_bbox.to_dict(),
            "anchor_bbox": self.label_bbox.to_dict(),
            "confidence": self.confidence,
            "source": self.source,
        }


def _normal(text: str) -> str:
    """Normalize text for exact alias matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein distance between two short strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if not s2:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _matches_label(text: str, field_name: str, aliases: Tuple[str, ...]) -> bool:
    """Controlled field-specific matching: exact or tightly bounded edit distance."""
    norm_candidate = _normal(text)
    if not norm_candidate:
        return False

    # Disallow cross-matching between numbered fields (e.g. IMEI 1 vs IMEI 2)
    candidate_digits = re.findall(r"\d", norm_candidate)
    if field_name == "IMEI 1" and "2" in candidate_digits:
        return False
    if field_name == "IMEI 2" and "1" in candidate_digits:
        return False

    for alias in aliases:
        norm_alias = _normal(alias)
        if norm_candidate == norm_alias:
            return True

        alias_digits = re.findall(r"\d", norm_alias)
        # If either has digits, they must match exactly
        if candidate_digits != alias_digits:
            continue

        # Allow edit distance 1 for aliases with length >= 4
        if len(norm_alias) >= 4 and abs(len(norm_candidate) - len(norm_alias)) <= 1:
            if _levenshtein_distance(norm_candidate, norm_alias) <= 1:
                return True
        # Allow edit distance 2 for long aliases (>= 9 chars)
        elif len(norm_alias) >= 9 and abs(len(norm_candidate) - len(norm_alias)) <= 2:
            if _levenshtein_distance(norm_candidate, norm_alias) <= 2:
                return True

    return False


def _union(tokens: Iterable[OCRToken]) -> BoundingBox:
    items = list(tokens)
    if not items:
        return BoundingBox(0, 0, 0, 0)
    left = min(token.x for token in items)
    top = min(token.y for token in items)
    right = max(token.x + token.width for token in items)
    bottom = max(token.y + token.height for token in items)
    return BoundingBox(left, top, right - left, bottom - top)


def locate_field_regions(record: RawRecord) -> Dict[str, FieldRegion]:
    """Find known labels and bound value regions to adjacent tokens or layout bounds."""
    regions: Dict[str, FieldRegion] = {}
    if not record.rows:
        return regions

    # Pass 1: Identify all labels and their locations
    label_hits: List[Tuple[str, List[OCRToken], BoundingBox, int, int]] = []
    # (field_name, matched_tokens, label_box, row_index, token_start_index)

    for row_index, row in enumerate(record.rows):
        words = row.words
        n_words = len(words)
        for field_name, aliases in LABEL_ALIASES.items():
            if field_name in regions:
                continue
            for index in range(n_words):
                matched_tokens: List[OCRToken] = []
                for width in (4, 3, 2, 1):
                    if index + width > n_words:
                        continue
                    chunk = words[index:index + width]
                    chunk_text = " ".join(token.text for token in chunk)
                    if _matches_label(chunk_text, field_name, aliases):
                        matched_tokens = chunk
                        break
                if matched_tokens:
                    label_box = _union(matched_tokens)
                    label_hits.append((field_name, matched_tokens, label_box, row_index, index))
                    break

    # Sort label hits by spatial reading order (row_index, x)
    label_hits.sort(key=lambda item: (item[3], item[2].x))

    # Pass 2: Derive value bounding box for each label based on neighboring labels and layout
    for hit_idx, (field_name, matched_tokens, label_box, row_index, token_start_index) in enumerate(label_hits):
        if field_name in regions:
            continue

        row = record.rows[row_index]
        words = row.words
        after_label_idx = token_start_index + len(matched_tokens)

        # Determine right boundary from the next label on the same row, if any
        next_label_token_idx = len(words)
        next_label_x = None
        for other_field, _, other_box, other_row_idx, other_token_idx in label_hits:
            if other_row_idx == row_index and other_token_idx > token_start_index:
                if other_token_idx < next_label_token_idx:
                    next_label_token_idx = other_token_idx
                    next_label_x = other_box.x

        # Layout option 1: Same row to the right (LABEL: VALUE)
        same_row_tokens = words[after_label_idx:next_label_token_idx]

        if same_row_tokens:
            val_box = _union(same_row_tokens)
            regions[field_name] = FieldRegion(
                field_name=field_name,
                value_bbox=val_box,
                label_bbox=label_box,
                anchor_label=" ".join(t.text for t in matched_tokens),
                confidence=0.95,
                source="label_right",
            )
            continue

        # Layout option 2: Directly below label (LABEL \n VALUE)
        if row_index + 1 < len(record.rows):
            next_row = record.rows[row_index + 1]
            # Column boundary: align with label x, extending to next label or reasonable column width
            col_min_x = max(0, label_box.x - 25)
            col_max_x = next_label_x if next_label_x is not None else (label_box.right + 250)

            below_tokens = [
                token for token in next_row.words
                if col_min_x <= token.x <= col_max_x
            ]

            if below_tokens:
                val_box = _union(below_tokens)
                regions[field_name] = FieldRegion(
                    field_name=field_name,
                    value_bbox=val_box,
                    label_bbox=label_box,
                    anchor_label=" ".join(t.text for t in matched_tokens),
                    confidence=0.85,
                    source="label_below",
                )
                continue

        # Layout option 3: Label exists but value tokens faint or not initially segmented
        # Estimate expected geometric region to the right of label
        est_width = 180 if "imei" in field_name.lower() or "reference" in field_name.lower() else 120
        est_right = min(next_label_x or (label_box.right + est_width), label_box.right + est_width)
        est_box = BoundingBox(
            x=label_box.right + 4,
            y=label_box.y,
            width=max(40, est_right - label_box.right - 4),
            height=label_box.height,
        )
        regions[field_name] = FieldRegion(
            field_name=field_name,
            value_bbox=est_box,
            label_bbox=label_box,
            anchor_label=" ".join(t.text for t in matched_tokens),
            confidence=0.60,
            source="label_estimated_right",
        )

    return regions


def attach_token_span_regions(record_fields: Dict[str, Any]) -> None:
    """Attach bounding regions from extracted field tokens when no explicit label was detected."""
    for field_name, field_data in record_fields.items():
        if "field_region" in field_data and field_data["field_region"]:
            continue
        coords = field_data.get("coordinates", [])
        if coords:
            left = min(c["x"] for c in coords)
            top = min(c["y"] for c in coords)
            right = max(c["x"] + c["width"] for c in coords)
            bottom = max(c["y"] + c["height"] for c in coords)
            val_box = BoundingBox(left, top, right - left, bottom - top)
            field_data["field_region"] = {
                "field_name": field_name,
                "region": {"x": left, "y": top, "width": right - left, "height": bottom - top},
                "bbox": val_box.to_dict(),
                "anchor_label": "",
                "anchor_coordinates": val_box.to_dict(),
                "anchor_bbox": val_box.to_dict(),
                "confidence": 0.70,
                "source": "token_span",
            }
