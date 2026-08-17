"""Master 31-Field Record Extractor coordinating all specialized domain sub-extractors."""

from collections import OrderedDict
from typing import Any, Dict, List, Optional

from ocr.tokens import OCRToken, RawRecord
from extraction.address import extract_address_block
from extraction.dates import locate_date_tokens
from extraction.email import clean_email_token
from extraction.imei import extract_imei_pair
from extraction.mobile import (
    extract_file_ref,
    extract_mobile_model,
    extract_network_type,
    extract_reference_no,
    extract_service_provider,
    extract_sim_no,
)
from extraction.person import (
    EXACT_TITLES,
    extract_father_name,
    extract_gender,
    extract_names,
    extract_profession,
    extract_title,
)
from extraction.plan_card import extract_contact, extract_plan_and_card

FIELD_ORDER = (
    "File No", "Form No", "Title", "First Name", "Last Name", "Initial", "Email",
    "Father Name", "DOB", "Gender", "Profession", "Mailing Street", "City",
    "Postal Code", "Country", "Service Provider", "File Ref", "Reference No", "SIM No",
    "Network Type", "Mobile Model", "IMEI 1", "IMEI 2", "Plan Type", "Card Type",
    "Contact", "Issue Date", "Renewal Date", "Installments", "Amount in Words", "Remarks",
)


def build_field(
    tokens: Optional[List[OCRToken]] = None,
    value: Optional[str] = None,
    review: bool = False,
    variant: str = "standard",
) -> Dict[str, Any]:
    """Construct structured field dictionary with coordinates, confidence provenance, and review flags."""
    tokens = tokens or []
    raw = " ".join(t.text for t in tokens).strip()
    val = raw if value is None else str(value)

    # Calculate confidence from valid source word tokens (avoiding 0.0 from whitespace/punctuation)
    valid_confs = [t.confidence for t in tokens if t.confidence > 0]
    if valid_confs:
        conf = round(sum(valid_confs) / len(valid_confs), 2)
    elif tokens:
        conf = round(sum(t.confidence for t in tokens) / len(tokens), 2)
    else:
        conf = 100.0 if val else 0.0

    needs_review = review or (not tokens and not val) or (conf < 60.0 and bool(tokens))

    return {
        "value": val,
        "raw_text": raw,
        "confidence": conf,
        "needs_review": needs_review,
        "coordinates": [t.bbox.to_dict() for t in tokens],
        "source_tokens": [t.to_dict() for t in tokens],
        "variant": variant,
    }


def extract_31_fields(raw_record: RawRecord, file_no: str, form_no: int) -> Dict[str, Any]:
    """Extract all 31 fields from a segmented RawRecord."""
    tokens = raw_record.all_tokens()
    fields = OrderedDict((name, build_field()) for name in FIELD_ORDER)
    fields["File No"] = build_field([], str(file_no))
    fields["Form No"] = build_field([], str(form_no))
    fields["Remarks"] = build_field([], "Not Applicable")

    if not tokens:
        return {
            "record_number": raw_record.record_number,
            "form_no": form_no,
            "fields": fields,
            "MY": None,
        }

    # 1. Dates & Email Anchors
    all_dates = locate_date_tokens(tokens)
    dob_idx, dob_val, dob_tok = (all_dates[0][0], all_dates[0][1], all_dates[0][2]) if all_dates else (None, "", None)

    email_idx = next((i for i, t in enumerate(tokens) if "@" in t.text), None)
    pre_last_name = ""
    if email_idx is not None:
        email_val, pre_last_name = clean_email_token(tokens[email_idx].text)
        fields["Email"] = build_field([tokens[email_idx]], email_val)

    # 2. Title & Names
    title_val, title_toks, name_start_idx = extract_title(tokens, start_idx=0)
    title_field = build_field(title_toks, title_val)
    # If title matched exact closed dictionary, mark verified
    if title_val.lower() in EXACT_TITLES and title_field["confidence"] < 60.0:
        title_field["confidence"] = 85.0
        title_field["needs_review"] = False
    fields["Title"] = title_field

    name_end_idx = email_idx if email_idx is not None else (dob_idx if dob_idx is not None else len(tokens))
    first_val, first_toks, last_val, last_toks = extract_names(tokens, name_start_idx, name_end_idx, pre_last_name)
    fields["First Name"] = build_field(first_toks, first_val)
    fields["Last Name"] = build_field(last_toks, last_val)

    # 3. Father Name, DOB, Gender, Profession
    if dob_idx is not None and dob_tok is not None:
        fields["DOB"] = build_field([dob_tok], dob_val)

    father_val, father_toks = extract_father_name(tokens, email_idx, dob_idx)
    if father_val:
        fields["Father Name"] = build_field(father_toks, father_val)

    gender_val, gender_toks, gender_idx = extract_gender(tokens)
    if gender_val:
        fields["Gender"] = build_field(gender_toks, gender_val)

    prof_start = (gender_idx + 1) if gender_idx is not None else ((dob_idx + 1) if dob_idx is not None else 0)
    prof_val, prof_toks, prof_end = extract_profession(tokens, prof_start)
    if prof_val:
        fields["Profession"] = build_field(prof_toks, prof_val)

    # 4. Service Provider & Address Block
    prov_val, prov_toks, file_ref_prefix, prov_idx = extract_service_provider(tokens, prof_end)
    if prov_val:
        fields["Service Provider"] = build_field(prov_toks, prov_val)

    addr_end = prov_idx if prov_idx < len(tokens) else len(tokens)
    s_val, s_toks, c_val, c_toks, p_val, p_toks, cnt_val, cnt_toks = extract_address_block(tokens, prof_end, addr_end)
    if s_val:
        fields["Mailing Street"] = build_field(s_toks, s_val)
    if c_val:
        fields["City"] = build_field(c_toks, c_val)
    if p_val:
        fields["Postal Code"] = build_field(p_toks, p_val)
    if cnt_val:
        fields["Country"] = build_field(cnt_toks, cnt_val)

    # 5. Mobile Model, SIM, Network, Reference, File Ref
    after_prov = (prov_idx + 1) if prov_idx < len(tokens) else prof_end
    fref_val, fref_toks, after_fref = extract_file_ref(tokens, after_prov, file_ref_prefix)
    if fref_val:
        fields["File Ref"] = build_field(fref_toks, fref_val)

    ref_val, ref_toks, after_ref = extract_reference_no(tokens, after_fref)
    if ref_val:
        fields["Reference No"] = build_field(ref_toks, ref_val)

    sim_val, sim_toks, after_sim = extract_sim_no(tokens, after_ref)
    if sim_val:
        fields["SIM No"] = build_field(sim_toks, sim_val)

    net_val, net_toks, after_net = extract_network_type(tokens, after_sim)
    if net_val:
        fields["Network Type"] = build_field(net_toks, net_val)

    model_val, model_toks, after_model = extract_mobile_model(tokens, after_net)
    if model_val:
        fields["Mobile Model"] = build_field(model_toks, model_val)

    # 6. Plan, Card, Contact, Dates, IMEI 1, IMEI 2
    end_dates = all_dates[1:] if len(all_dates) > 1 else []
    first_end_date_idx = end_dates[0][0] if end_dates else len(tokens)

    # Locate contact currency token
    contact_search_start = after_model
    contact_val, contact_toks, contact_idx = extract_contact(tokens, contact_search_start, first_end_date_idx)
    if contact_val:
        fields["Contact"] = build_field(contact_toks, contact_val)

    # Plan and Card
    plan_val, plan_toks, plan_idx, card_val, card_toks, card_idx = extract_plan_and_card(
        tokens, after_model, contact_idx, first_end_date_idx
    )
    if plan_val:
        fields["Plan Type"] = build_field(plan_toks, plan_val)
    if card_val:
        fields["Card Type"] = build_field(card_toks, card_val)

    # IMEI 1 & IMEI 2 extraction
    imei_limit = plan_idx if plan_idx is not None else (card_idx if card_idx is not None else (contact_idx or first_end_date_idx))
    imei1_val, imei1_toks, imei2_val, imei2_toks = extract_imei_pair(tokens, after_model, imei_limit)
    if imei1_val:
        fields["IMEI 1"] = build_field(imei1_toks, imei1_val)
    if imei2_val:
        fields["IMEI 2"] = build_field(imei2_toks, imei2_val)

    # Issue Date & Renewal Date
    if len(all_dates) >= 3:
        issue_idx, issue_val, issue_tok = all_dates[-2]
        renewal_idx, renewal_val, renewal_tok = all_dates[-1]
        fields["Issue Date"] = build_field([issue_tok], issue_val)
        fields["Renewal Date"] = build_field([renewal_tok], renewal_val)
    elif len(all_dates) == 2:
        fields["Issue Date"] = build_field([all_dates[0][2]], all_dates[0][1])
        fields["Renewal Date"] = build_field([all_dates[1][2]], all_dates[1][1])

    return {
        "record_number": raw_record.record_number,
        "form_no": form_no,
        "fields": fields,
        "MY": None,
    }
