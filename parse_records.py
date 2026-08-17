import re
from pathlib import Path

# Read OCR result
ocr_file = Path("output/ocr_result.txt")
text = ocr_file.read_text(encoding="utf-8")

# Split into lines
lines = text.splitlines()

records = []
current_record = []

# A new record starts with Ms., Mr. or MISS
start_pattern = re.compile(r"^(Ms\.?|Mr\.?|MISS)\b", re.IGNORECASE)

for line in lines:
    line = line.strip()

    if not line:
        continue

    # New person/record detected
    if start_pattern.match(line):
        # Save previous record
        if current_record:
            records.append(" ".join(current_record))

        current_record = [line]

    else:
        # Continue current record
        if current_record:
            current_record.append(line)

# Save final record
if current_record:
    records.append(" ".join(current_record))


print(f"\nFound {len(records)} records\n")

for number, record in enumerate(records, start=1):
    print("=" * 70)
    print(f"RECORD {number}")
    print("=" * 70)
    print(record)
    print()