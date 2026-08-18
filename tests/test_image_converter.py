"""Tests for HD conversion, proof storage, and F6 script rebuilding."""

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from extraction.extractor import FIELD_ORDER
from ocr.image_converter import MAX_UPSCALE, convert_image_for_ocr
from run_pipeline import rebuild_ahk_from_latest_output, write_conversion_proof
from state_store import StateStore


class TestImageConverter(unittest.TestCase):
    def test_converter_creates_high_resolution_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "form.png"
            output_path = root / "archive" / "hd" / "form_hd.png"
            source = Image.new("RGB", (1200, 600), "white")
            ImageDraw.Draw(source).rectangle((100, 100, 900, 180), fill="black")
            source.save(source_path)

            report = convert_image_for_ocr(source_path, output_path)

            self.assertTrue(output_path.exists())
            self.assertEqual(report.converted_size, (3600, 1800))
            self.assertEqual(report.scale, 3.0)

    def test_converter_caps_the_upscale_factor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "small.png"
            output_path = root / "small_hd.png"
            Image.new("RGB", (100, 50), "white").save(source_path)

            report = convert_image_for_ocr(source_path, output_path)

            self.assertEqual(report.scale, MAX_UPSCALE)

    def test_proof_and_rebuild_include_a_review_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.png"
            hd_path = root / "archive" / "hd" / "source_hd.png"
            Image.new("RGB", (1000, 500), "white").save(source_path)
            conversion = convert_image_for_ocr(source_path, hd_path)
            proof = write_conversion_proof(conversion, StateStore.file_hash(source_path))

            fields = {name: {"value": f"record-{i}"} for i, name in enumerate(FIELD_ORDER)}
            review_record = {
                "record_number": 1,
                "form_no": 1,
                "status": "REVIEW_REQUIRED",
                "fingerprint": "review-record",
                "fields": fields,
            }
            (root / "review.json").write_text(
                json.dumps({"records": [review_record]}), encoding="utf-8"
            )
            count, review_count = rebuild_ahk_from_latest_output(root)
            script = (root / "data_entry.ahk").read_text(encoding="utf-8")

            self.assertTrue(hd_path.with_suffix(".json").exists())
            self.assertEqual(proof["converted_sha256"], StateStore.file_hash(hd_path))
            self.assertEqual((count, review_count), (1, 1))
            self.assertIn("scanned_records[1] :=", script)


if __name__ == "__main__":
    unittest.main()
