"""Non-OCR business calculations for a structured 31-field record."""

from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any

from amount_words import amount_to_words


def calculate_fields(record: Dict[str, Any]) -> None:
    """Derive Initials, Months (MY), Installments, and Amount in Words."""
    fields = record["fields"]

    # 1. Calculate Initial from Title, First Name, Last Name
    title = fields["Title"]["value"].strip()
    first_name = fields["First Name"]["value"].strip()
    last_name = fields["Last Name"]["value"].strip()

    initial = "".join(
        val[0].upper() for val in (title, first_name, last_name) if val and val[0].isalpha()
    )
    fields["Initial"].update({
        "value": initial,
        "raw_text": initial,
        "confidence": 100.0,
        "needs_review": not bool(initial),
    })

    # 2. Compute Months (MY)
    issue_date = fields["Issue Date"]["value"].strip()
    renewal_date = fields["Renewal Date"]["value"].strip()
    contact = fields["Contact"]["value"].strip()

    months = None
    try:
        if issue_date and renewal_date:
            issue_year = datetime.strptime(issue_date, "%d/%m/%Y").year
            renewal_year = datetime.strptime(renewal_date, "%d/%m/%Y").year
            months = (renewal_year - issue_year) * 12
    except (ValueError, TypeError):
        months = None

    record["MY"] = months

    # 3. Special Case: MY == 0 -> Installments = "INVALID", Amount in Words = ""
    if months == 0:
        fields["Installments"].update({
            "value": "INVALID",
            "raw_text": "INVALID",
            "confidence": 100.0,
            "needs_review": False,
        })
        fields["Amount in Words"].update({
            "value": "",
            "raw_text": "",
            "confidence": 100.0,
            "needs_review": False,
        })
        return

    # 4. Incomplete or invalid calculation inputs
    if months is None or months < 0 or not contact.isdigit():
        fields["Installments"].update({
            "value": "",
            "raw_text": "",
            "confidence": 0.0,
            "needs_review": True,
        })
        fields["Amount in Words"].update({
            "value": "",
            "raw_text": "",
            "confidence": 0.0,
            "needs_review": True,
        })
        return

    # 5. Standard calculation: (Contact / MY) + 10.33 rounded down to 2 decimal places
    installment = (Decimal(contact) / Decimal(months) + Decimal("10.33")).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN
    )
    installment_value = f"{installment:.2f}"
    fields["Installments"].update({
        "value": installment_value,
        "raw_text": installment_value,
        "confidence": 100.0,
        "needs_review": False,
    })

    amount_words = amount_to_words(installment_value)
    fields["Amount in Words"].update({
        "value": amount_words,
        "raw_text": amount_words,
        "confidence": 100.0,
        "needs_review": False,
    })
