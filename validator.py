"""Comprehensive Validation and Cross-Field Verification Engine."""

from datetime import datetime
import re
from typing import Any, Dict, List

from extraction.extractor import FIELD_ORDER
from extraction.person import EXACT_TITLES
from extraction.postcode import is_valid_postcode

REQUIRED_CORE_FIELDS = (
    "File No", "Form No", "Title", "First Name", "Last Name", "Initial", "Email",
    "DOB", "Gender", "Profession", "Mailing Street", "City", "Postal Code", "Country",
    "Contact", "Issue Date", "Renewal Date", "Installments", "Amount in Words",
)

DATE_FIELDS = ("DOB", "Issue Date", "Renewal Date")
MIN_ACCEPTED_OCR_CONFIDENCE = 60.0
EVIDENCE_REQUIRED_FIELDS = (
    "Title", "First Name", "Last Name", "Email", "DOB", "Gender", "Profession",
    "Mailing Street", "City", "Postal Code", "Country", "Mobile Model", "IMEI 1",
    "Contact", "Issue Date", "Renewal Date",
)

# Issue Severities
SEVERITY_MAP = {
    "MISSING_REQUIRED_FIELD": "FATAL",
    "INVALID_EMAIL": "FATAL",
    "INVALID_DOB": "FATAL",
    "INVALID_ISSUE_DATE": "FATAL",
    "INVALID_RENEWAL_DATE": "FATAL",
    "DOB_AFTER_ISSUE_DATE": "FATAL",
    "RENEWAL_BEFORE_ISSUE_DATE": "FATAL",
    "INVALID_GENDER": "FATAL",
    "INVALID_CONTACT": "FATAL",
    "INVALID_POSTAL_CODE": "FATAL",
    "INVALID_IMEI1": "FATAL",
    "CALCULATION_MISMATCH": "FATAL",
    "INVALID_INSTALLMENTS": "FATAL",
    "EMPTY_AMOUNT_WORDS": "FATAL",
    "MOBILE_MODEL_IMEI_CONFLICT": "FATAL",
    "FIELD_REGION_NOT_LOCATED": "FATAL",
    "LOW_OCR_CONFIDENCE": "REVIEW",
    "AMBIGUOUS_IMEI1": "REVIEW",
    "MULTIPLE_CANDIDATES": "REVIEW",
    "OCR_CONFLICT": "REVIEW",
    "INVALID_INITIAL": "WARNING",
}


def parse_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y")
    except (ValueError, TypeError):
        return None


def validate_record(record: Dict[str, Any]) -> List[Dict[str, str]]:
    """Validate 31-field record structure, data formats, and cross-field relationships."""
    fields = record["fields"]
    issues: List[Dict[str, str]] = []
    my_is_zero = record.get("MY") == 0

    # OCR evidence is a separate acceptance gate. A value that passed a
    # format check is still not safe to auto-enter when its source OCR was
    # explicitly flagged as uncertain.
    for name in EVIDENCE_REQUIRED_FIELDS:
        evidence = fields.get(name, {})
        val = evidence.get("value", "").strip()
        if not val:
            continue  # missing-field validation below provides the primary reason.

        # Special semantic verification exemption for exact dictionary titles
        if name == "Title" and val.lower() in EXACT_TITLES:
            continue

        confidence = evidence.get("confidence")
        if evidence.get("needs_review") or (
            confidence is not None and float(confidence) < MIN_ACCEPTED_OCR_CONFIDENCE
        ):
            issues.append({
                "field": name,
                "reason": "LOW_OCR_CONFIDENCE",
                "severity": SEVERITY_MAP.get("LOW_OCR_CONFIDENCE", "REVIEW"),
                "detail": f"OCR confidence {confidence!s} is below the automatic-acceptance threshold",
            })

    # 1. Required core fields presence
    for name in REQUIRED_CORE_FIELDS:
        if name == "Amount in Words" and my_is_zero:
            continue
        val = fields[name]["value"].strip()
        if not val:
            issues.append({
                "field": name,
                "reason": "MISSING_REQUIRED_FIELD",
                "severity": "FATAL",
                "detail": f"{name} is empty",
            })

    # 2. Email format validation
    email_val = fields["Email"]["value"].strip()
    if email_val and not re.fullmatch(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", email_val):
        issues.append({
            "field": "Email",
            "reason": "INVALID_EMAIL",
            "severity": "FATAL",
            "detail": "Email does not match valid pattern",
        })

    # 3. Date format and semantic validation
    parsed_dates: Dict[str, datetime] = {}
    for name in DATE_FIELDS:
        date_str = fields[name]["value"].strip()
        if date_str:
            dt = parse_date(date_str)
            if not dt:
                reason = f"INVALID_{name.upper().replace(' ', '_')}"
                issues.append({
                    "field": name,
                    "reason": reason,
                    "severity": "FATAL",
                    "detail": "Not a valid DD/MM/YYYY date",
                })
            else:
                parsed_dates[name] = dt

    # 4. Cross-Date Validation
    if "DOB" in parsed_dates and "Issue Date" in parsed_dates:
        if parsed_dates["DOB"] >= parsed_dates["Issue Date"]:
            issues.append({
                "field": "DOB",
                "reason": "DOB_AFTER_ISSUE_DATE",
                "severity": "FATAL",
                "detail": "DOB must be before Issue Date",
            })

    if "Issue Date" in parsed_dates and "Renewal Date" in parsed_dates:
        if parsed_dates["Issue Date"] > parsed_dates["Renewal Date"]:
            issues.append({
                "field": "Renewal Date",
                "reason": "RENEWAL_BEFORE_ISSUE_DATE",
                "severity": "FATAL",
                "detail": "Renewal Date cannot precede Issue Date",
            })

    # 5. Gender validation
    gender_val = fields["Gender"]["value"].strip()
    if gender_val and gender_val not in {"Male", "Female"}:
        issues.append({
            "field": "Gender",
            "reason": "INVALID_GENDER",
            "severity": "FATAL",
            "detail": f"Unrecognized gender '{gender_val}'",
        })

    # 6. Contact validation
    contact_val = fields["Contact"]["value"].strip()
    if contact_val and not contact_val.isdigit():
        issues.append({
            "field": "Contact",
            "reason": "INVALID_CONTACT",
            "severity": "FATAL",
            "detail": "Contact amount is not strictly numeric",
        })

    # 7. Postal Code validation
    postcode_val = fields["Postal Code"]["value"].strip()
    if postcode_val and not is_valid_postcode(postcode_val):
        issues.append({
            "field": "Postal Code",
            "reason": "INVALID_POSTAL_CODE",
            "severity": "FATAL",
            "detail": f"'{postcode_val}' is not a valid UK postcode",
        })

    # 8. Mobile Model vs IMEI Cross-Validation
    model_val = fields["Mobile Model"]["value"].strip()
    imei1_val = fields["IMEI 1"]["value"].strip()
    if model_val and imei1_val and (model_val == imei1_val or imei1_val in model_val):
        issues.append({
            "field": "IMEI 1",
            "reason": "MOBILE_MODEL_IMEI_CONFLICT",
            "severity": "FATAL",
            "detail": "Mobile Model and IMEI 1 must not be identical or overlapping",
        })
    imei_digits = re.sub(r"\D", "", imei1_val)
    if imei1_val and len(imei_digits) != 15:
        issues.append({
            "field": "IMEI 1",
            "reason": "INVALID_IMEI1",
            "severity": "FATAL",
            "detail": "IMEI 1 must contain exactly 15 digits",
        })
    if imei1_val and len(imei_digits) < 10:
        issues.append({
            "field": "IMEI 1",
            "reason": "AMBIGUOUS_IMEI1",
            "severity": "REVIEW",
            "detail": "Short numeric values may be mobile model numbers, not IMEI values",
        })

    # 9. Initials validation
    initial_val = fields["Initial"]["value"].strip()
    if initial_val and not re.fullmatch(r"[A-Z]{2,4}", initial_val):
        issues.append({
            "field": "Initial",
            "reason": "INVALID_INITIAL",
            "severity": "WARNING",
            "detail": f"Initials '{initial_val}' must be 2-4 uppercase letters",
        })

    # 10. Calculations validation
    if my_is_zero:
        if fields["Installments"]["value"] != "INVALID":
            issues.append({
                "field": "Installments",
                "reason": "CALCULATION_MISMATCH",
                "severity": "FATAL",
                "detail": "Installments must be 'INVALID' when MY=0",
            })
    else:
        inst_val = fields["Installments"]["value"].strip()
        if not inst_val or inst_val == "INVALID":
            issues.append({
                "field": "Installments",
                "reason": "INVALID_INSTALLMENTS",
                "severity": "FATAL",
                "detail": "Installments calculation was not performed",
            })
        if not fields["Amount in Words"]["value"].strip():
            issues.append({
                "field": "Amount in Words",
                "reason": "EMPTY_AMOUNT_WORDS",
                "severity": "FATAL",
                "detail": "Amount in words is empty",
            })

    # Deduplicate issues
    unique_issues: List[Dict[str, str]] = []
    seen = set()
    for issue in issues:
        key = (issue["field"], issue["reason"])
        if key not in seen:
            unique_issues.append(issue)
            seen.add(key)

    return unique_issues
