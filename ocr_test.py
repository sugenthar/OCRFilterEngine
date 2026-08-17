import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

# Tesseract path
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# Image
image_path = r"images\sample.png"

# Open image
image = Image.open(image_path)

# Convert to grayscale
image = image.convert("L")

# Increase size
width, height = image.size
image = image.resize((width * 2, height * 2))

# Increase contrast
contrast = ImageEnhance.Contrast(image)
image = contrast.enhance(1.5)

# Sharpen
image = image.filter(ImageFilter.SHARPEN)

# OCR
text = pytesseract.image_to_string(
    image,
    config="--psm 6"
)

print("\n===== IMPROVED OCR RESULT =====\n")
print(text)
print("\n===============================\n")

# Save processed image for inspection
image.save("output/processed.png")

# Save OCR text
with open("output/ocr_result.txt", "w", encoding="utf-8") as file:
    file.write(text)

print("OCR result saved to output/ocr_result.txt")
print("Processed image saved to output/processed.png")