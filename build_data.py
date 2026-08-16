from pathlib import Path
from datetime import datetime

# Read OCR result
ocr_file = Path("output/ocr_result.txt")
text = ocr_file.read_text(encoding="utf-8")

# --------------------------------------------------
# Split into 4 records
# --------------------------------------------------

import re

lines = [line.strip() for line in text.splitlines() if line.strip()]

start_pattern = re.compile(r"^(Ms\.?|Mr\.?|MISS)\s+", re.IGNORECASE)

records = []
current = []

for line in lines:
    if start_pattern.match(line):
        if current:
            records.append(" ".join(current))
        current = [line]
    elif current:
        current.append(line)

if current:
    records.append(" ".join(current))


# --------------------------------------------------
# Extract basic fields
# --------------------------------------------------

def extract_record(record):

    fields = {
        "title": "",
        "first_name": "",
        "last_name": "",
        "email": "",
        "father_name": "",
        "dob": "",
        "gender": "",
        "profession": "",
        "mailing_street": "",
        "city": "",
        "postal_code": "",
        "country": "",
        "service_provider": "",
        "file_ref": "",
        "reference_no": "",
        "sim_no": "",
        "network_type": "",
        "mobile_model": "",
        "imei_1": "",
        "imei_2": "",
        "plan_type": "",
        "card_type": "",
        "contact": "",
        "issue_date": "",
        "renewal_date": "",
    }

    # Title
    m = re.match(r"^(Ms|Mr|MISS)\.?\s+", record, re.I)
    if not m:
        return fields

    fields["title"] = m.group(1)
    remaining = record[m.end():].strip()

    # Email
    email = re.search(r"\S+@\S+", remaining)

    # DOB
    dob = re.search(r"\b\d{2}/\d{2}/\d{4}\b", remaining)

    if not dob:
        return fields

    fields["dob"] = dob.group()

    # Text before DOB
    before_dob = remaining[:dob.start()].strip()

    # Name
    name_email_part = before_dob

    if email:
        fields["email"] = email.group()
        name_email_part = before_dob[:email.start()].strip()

    parts = name_email_part.split()

    if len(parts) >= 2:
        fields["first_name"] = parts[0]
        fields["last_name"] = parts[1]

    # Father name = text between email and DOB
    if email:
        father = before_dob[email.end():].strip()
        if father:
            fields["father_name"] = father

    # After DOB
    after_dob = remaining[dob.end():].strip()

    # Gender
    gender = re.search(r"\b(Male|Female)\b", after_dob, re.I)

    if gender:
        fields["gender"] = gender.group(1).capitalize()

    # Profession
    profession_patterns = [
        r"Self\s+Employed",
        r"Professional",
        r"Others",
        r"Service",
    ]

    for pattern in profession_patterns:
        p = re.search(pattern, after_dob, re.I)
        if p:
            fields["profession"] = p.group()
            break

    # Dates
    dates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", record)

    if len(dates) >= 2:
        fields["issue_date"] = dates[-2]
        fields["renewal_date"] = dates[-1]

    # Contact / currency
    money = re.findall(r"[£€]\s*\d+(?:\.\d+)?", record)

    if money:
        fields["contact"] = re.sub(r"[£€\s]", "", money[-1])

    return fields


# --------------------------------------------------
# Calculate values
# --------------------------------------------------

from decimal import Decimal, ROUND_DOWN

def calculate(fields):

    issue = fields["issue_date"]
    renewal = fields["renewal_date"]

    if issue and renewal:
        try:
            issue_year = datetime.strptime(
                issue, "%d/%m/%Y"
            ).year
            renewal_year = datetime.strptime(
                renewal, "%d/%m/%Y"
            ).year
            my = (renewal_year - issue_year) * 12
        except (ValueError, TypeError):
            my = None
    else:
        my = None

    fields["MY"] = my

    if my == 0:
        fields["installments"] = "INVALID"
    elif my is not None and fields["contact"]:
        try:
            installment = (Decimal(str(fields["contact"])) / Decimal(my) + Decimal("10.33")).quantize(
                Decimal("0.01"), rounding=ROUND_DOWN
            )
            fields["installments"] = f"{installment:.2f}"
        except Exception:
            fields["installments"] = ""
    else:
        fields["installments"] = ""

    return fields


# --------------------------------------------------
# Run
# --------------------------------------------------

print()
print("=" * 80)
print(f"FOUND {len(records)} RECORDS")
print("=" * 80)

for number, record in enumerate(records, 1):

    fields = extract_record(record)
    fields = calculate(fields)

    print()
    print("=" * 80)
    print(f"RECORD {number}")
    print("=" * 80)

    for key, value in fields.items():
        print(f"{key:18}: {value}")