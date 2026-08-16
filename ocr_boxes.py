import pytesseract
from PIL import Image
from pytesseract import Output

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

image = Image.open(r"images\sample.png")

data = pytesseract.image_to_data(
    image,
    output_type=Output.DICT,
    config="--psm 6"
)

print()
print("=" * 80)
print("OCR WORD COORDINATES")
print("=" * 80)

for i, word in enumerate(data["text"]):

    word = word.strip()

    if not word:
        continue

    confidence = data["conf"][i]

    print(
        f"{word:30} "
        f"x={data['left'][i]:4} "
        f"y={data['top'][i]:4} "
        f"w={data['width'][i]:4} "
        f"h={data['height'][i]:4} "
        f"conf={confidence}"
    )