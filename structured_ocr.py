import pytesseract
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
# Group words into visual rows
# --------------------------------------------------

rows = []

for word in sorted(words, key=lambda w: (w["y"], w["x"])):

    placed = False

    for row in rows:

        # Same visual line if Y difference <= 15 pixels
        if abs(word["y"] - row["y"]) <= 15:
            row["words"].append(word)
            placed = True
            break

    if not placed:
        rows.append({
            "y": word["y"],
            "words": [word]
        })


# Sort rows
rows.sort(key=lambda r: r["y"])


# Sort words inside each row by X
for row in rows:
    row["words"].sort(key=lambda w: w["x"])


# --------------------------------------------------
# Display clean rows
# --------------------------------------------------

print()
print("=" * 100)
print("CLEAN OCR ROWS")
print("=" * 100)

for number, row in enumerate(rows, 1):

    text = " ".join(
        word["text"]
        for word in row["words"]
    )

    print(
        f"ROW {number:02} | "
        f"Y={row['y']:4} | "
        f"{text}"
    )