"""Tesseract OCR Engine wrapper and standard execution."""

import os
from pathlib import Path
from typing import List, Optional, Tuple, Union

from PIL import Image
import pytesseract
from pytesseract import Output

from ocr.preprocessing import (
    preprocess_variant_a,
    preprocess_variant_b,
    preprocess_variant_c,
    preprocess_variant_d_binarized,
)
from ocr.tokens import BoundingBox, OCRToken

DEFAULT_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
LOW_CONFIDENCE_THRESHOLD = 50.0


class TesseractEngine:
    def __init__(self, tesseract_cmd: Optional[str] = None) -> None:
        if tesseract_cmd and os.path.exists(tesseract_cmd):
            self.tesseract_cmd = tesseract_cmd
        elif os.path.exists(DEFAULT_TESSERACT_PATH):
            self.tesseract_cmd = DEFAULT_TESSERACT_PATH
        else:
            self.tesseract_cmd = "tesseract"
        pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

    def run_ocr(
        self,
        image_input: Union[Path, str, Image.Image],
        variant: str = "A",
        psm: int = 6,
        oem: int = 3,
        custom_config: str = "",
        coordinate_scale: float = 1.0,
    ) -> Tuple[List[OCRToken], float]:
        """Execute OCR and map token coordinates to the original source image.

        ``coordinate_scale`` is the uniform enlargement applied by the HD image
        conversion stage before OCR starts.
        """
        if isinstance(image_input, (str, Path)):
            with Image.open(image_input) as img:
                orig_image = img.copy()
        elif isinstance(image_input, Image.Image):
            orig_image = image_input.copy()
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        if variant.upper() == "A":
            proc_img, scale = preprocess_variant_a(orig_image)
        elif variant.upper() == "B":
            proc_img, scale = preprocess_variant_b(orig_image)
        elif variant.upper() == "C":
            proc_img, scale = preprocess_variant_c(orig_image)
        elif variant.upper() == "D":
            proc_img, scale = preprocess_variant_d_binarized(orig_image)
        else:
            proc_img = orig_image
            scale = 1.0

        config = f"--psm {psm} --oem {oem} {custom_config}".strip()
        data = pytesseract.image_to_data(proc_img, output_type=Output.DICT, config=config)

        tokens: List[OCRToken] = []
        n_boxes = len(data["text"])
        for i in range(n_boxes):
            text = str(data["text"][i]).strip()
            if not text:
                continue

            try:
                conf = float(data["conf"][i])
            except (ValueError, TypeError):
                conf = -1.0

            if conf < 0:
                continue

            # Invert OCR preprocessing and HD conversion scales so field
            # regions remain aligned with the original form image.
            total_scale = scale * max(coordinate_scale, 0.0001)
            orig_x = int(round(data["left"][i] / total_scale))
            orig_y = int(round(data["top"][i] / total_scale))
            orig_w = int(round(data["width"][i] / total_scale))
            orig_h = int(round(data["height"][i] / total_scale))

            bbox = BoundingBox(x=orig_x, y=orig_y, width=orig_w, height=orig_h)
            token = OCRToken(
                text=text,
                bbox=bbox,
                confidence=round(conf, 2),
                needs_review=conf < LOW_CONFIDENCE_THRESHOLD,
                block_num=int(data.get("block_num", [0])[i]),
                par_num=int(data.get("par_num", [0])[i]),
                line_num=int(data.get("line_num", [0])[i]),
                word_num=int(data.get("word_num", [0])[i]),
                variant=variant,
            )
            tokens.append(token)

        return tokens, scale
