import pytesseract
import re
from PIL import Image
from pytesseract import Output

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

IMAGE = r"images\sample.png"

img = Image.open(IMAGE)

data = pytesseract.image_to_data(
    img,
    output_type=Output.DICT,
    config="--psm 6"
)

words = []

for i, text in enumerate(data["text"]):

    text = text.strip()

    if not text:
        continue

    try:
        confidence = float(data["conf"][i])
    except:
        confidence = 0

    if confidence < 0:
        continue

    words.append({
        "text": text,
        "x": int(data["left"][i]),
        "y": int(data["top"][i])
    })


# --------------------------------------------------
# Group words into rows
# --------------------------------------------------

rows = []

for word in sorted(words, key=lambda w: (w["y"], w["x"])):

    placed = False

    for row in rows:

        if abs(word["y"] - row["y"]) <= 15:
            row["words"].append(word)
            placed = True
            break

    if not placed:
        rows.append({
            "y": word["y"],
            "words": [word]
        })


rows.sort(key=lambda r: r["y"])

for row in rows:
    row["words"].sort(key=lambda w: w["x"])


# --------------------------------------------------
# Remove rows that contain only OCR artifacts
# --------------------------------------------------

clean_rows = []

for row in rows:

    text = " ".join(
        w["text"] for w in row["words"]
    ).strip()

    # Ignore tiny artifact-only rows
    if text in ["—", "©", "-", "- - - -"]:
        continue

    clean_rows.append({
        "y": row["y"],
        "text": text,
        "words": row["words"]
    })


# --------------------------------------------------
# We expect 12 useful rows = 4 records × 3 rows
# --------------------------------------------------

print()
print("=" * 100)
print("RECORD ROW STRUCTURE")
print("=" * 100)

print(f"\nUseful rows found: {len(clean_rows)}")

for i, row in enumerate(clean_rows):

    print()
    print(f"ROW {i + 1}")
    print(f"Y    : {row['y']}")
    print(f"TEXT : {row['text']}")


# --------------------------------------------------
# Group every 3 rows into one record
# --------------------------------------------------

if len(clean_rows) != 12:

    print()
    print("WARNING:")
    print("Expected 12 useful rows.")
    print("Please do not continue to AHK yet.")

else:

    records = []

    for i in range(0, len(clean_rows), 3):

        record = {
            "row1": clean_rows[i]["text"],
            "row2": clean_rows[i + 1]["text"],
            "row3": clean_rows[i + 2]["text"]
        }

        records.append(record)


    print()
    print("=" * 100)
    print("GROUPED RECORDS")
    print("=" * 100)

    for number, record in enumerate(records, 1):

        print()
        print("=" * 80)
        print(f"RECORD {number}")
        print("=" * 80)

        print("ROW 1:")
        print(record["row1"])

        print("\nROW 2:")
        print(record["row2"])

        print("\nROW 3:")
        print(record["row3"])