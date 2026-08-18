"""Comprehensive verification test suite for Field Localization, Targeted OCR, Validation, and F6 Pipeline."""

from pathlib import Path
import tempfile
import unittest

from PIL import Image

from calculations import calculate_fields
from extract_fields import extract_record
from extraction.extractor import FIELD_ORDER, build_field
from extraction.imei import extract_imei_pair
from extraction.mobile import extract_mobile_model
from extraction.postcode import is_valid_postcode, repair_postcode_characters
from generate_ahk import generate_ahk
from ocr.field_localization import FieldRegion, attach_token_span_regions, locate_field_regions
from ocr.targeted_ocr import run_multi_pass_targeted_ocr
from ocr.tokens import BoundingBox, OCRRow, OCRToken, RawRecord
from run_pipeline import create_debug_image, process_image, record_fingerprint
from state_store import StateStore
from validator import validate_record


def tok(text: str, x: int, y: int, w: int = 40, h: int = 15, conf: float = 90.0) -> OCRToken:
    return OCRToken(text=text, bbox=BoundingBox(x, y, w, h), confidence=conf)


class TestMasterPipeline(unittest.TestCase):
    def test_1_label_detection_exact_and_fuzzy(self):
        record = RawRecord(
            record_number=1,
            rows=[
                OCRRow(y=10, words=[tok("1MEI", 10, 10), tok("1:", 45, 10), tok("490154203237518", 100, 10)]),
                OCRRow(y=30, words=[tok("Postcode:", 10, 30), tok("BN1", 100, 30), tok("2FN", 140, 30)]),
                OCRRow(y=50, words=[tok("Ref", 10, 50), tok("No.:", 45, 50), tok("Vfone12345", 100, 50)]),
            ],
        )
        regions = locate_field_regions(record)
        self.assertIn("IMEI 1", regions)
        self.assertIn("Postal Code", regions)
        self.assertIn("Reference No", regions)

    def test_2_field_region_generation_same_row_and_stacked(self):
        row = OCRRow(
            y=10,
            words=[
                tok("IMEI 1:", 10, 10), tok("490154203237518", 65, 10),
                tok("IMEI 2:", 200, 10), tok("*@S!S-12345", 265, 10),
            ],
        )
        record = RawRecord(record_number=1, rows=[row])
        regions = locate_field_regions(record)
        self.assertIn("IMEI 1", regions)
        self.assertIn("IMEI 2", regions)
        self.assertLess(regions["IMEI 1"].value_bbox.right, 200)
        self.assertEqual(regions["IMEI 2"].value_bbox.x, 265)

    def test_3_imei1_region_localization(self):
        row = OCRRow(y=20, words=[tok("IMEI", 10, 20), tok("No", 45, 20), tok("1:", 70, 20), tok("352098001234567", 100, 20)])
        regions = locate_field_regions(RawRecord(record_number=1, rows=[row]))
        self.assertIn("IMEI 1", regions)
        self.assertEqual(regions["IMEI 1"].value_bbox.x, 100)

    def test_4_imei2_region_localization(self):
        row = OCRRow(y=20, words=[tok("IMEI", 10, 20), tok("2:", 50, 20), tok("#SS#-521315-9", 100, 20)])
        regions = locate_field_regions(RawRecord(record_number=1, rows=[row]))
        self.assertIn("IMEI 2", regions)
        self.assertEqual(regions["IMEI 2"].value_bbox.x, 100)

    def test_5_postal_code_region_localization(self):
        row = OCRRow(y=15, words=[tok("Post", 10, 15), tok("Code:", 50, 15), tok("LS16", 110, 15), tok("8AG", 150, 15)])
        regions = locate_field_regions(RawRecord(record_number=1, rows=[row]))
        self.assertIn("Postal Code", regions)
        self.assertEqual(regions["Postal Code"].value_bbox.x, 110)

    def test_6_reference_number_region_localization(self):
        row = OCRRow(y=15, words=[tok("Reference", 10, 15), tok("Number:", 70, 15), tok("HuWh570p", 150, 15)])
        regions = locate_field_regions(RawRecord(record_number=1, rows=[row]))
        self.assertIn("Reference No", regions)
        self.assertEqual(regions["Reference No"].value_bbox.x, 150)

    def test_7_model_imei_separation_brand_and_model(self):
        tokens = [tok("Nokia", 0, 0), tok("7210", 50, 0), tok("490154203237518", 100, 0)]
        model_val, model_toks, next_idx = extract_mobile_model(tokens, 0)
        self.assertEqual(model_val, "Nokia 7210")
        self.assertEqual(next_idx, 2)
        imei1, _, _, _ = extract_imei_pair(tokens, next_idx, len(tokens))
        self.assertEqual(imei1, "490154203237518")

    def test_A_model_preceding_imei_standalone(self):
        # T722 943826 - 52 - 988142 - 5
        tokens = [
            tok("T722", 0, 0),
            tok("943826", 50, 0),
            tok("-", 100, 0),
            tok("52", 110, 0),
            tok("-", 140, 0),
            tok("988142", 150, 0),
            tok("-", 200, 0),
            tok("5", 210, 0),
        ]
        model_val, model_toks, next_idx = extract_mobile_model(tokens, 0)
        self.assertEqual(model_val, "T722")
        self.assertEqual(next_idx, 1)
        imei1, imei1_toks, _, _ = extract_imei_pair(tokens, next_idx, len(tokens))
        digits = "".join(c for c in imei1 if c.isdigit())
        self.assertEqual(digits, "943826529881425")
        self.assertEqual(len(digits), 15)

    def test_B_strict_length_rejection(self):
        record_18 = {
            "record_number": 1,
            "fields": {
                name: build_field([], "val" if name != "IMEI 1" else "722943826529881425")
                for name in FIELD_ORDER
            },
        }
        issues = validate_record(record_18)
        self.assertTrue(any(i["reason"] == "INVALID_IMEI1" for i in issues))

    def test_C_numeric_whitelist_pass_executed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            img_path = Path(temp_dir) / "crop_test.png"
            Image.new("RGB", (200, 50), color="white").save(img_path)
            res = run_multi_pass_targeted_ocr(img_path, "IMEI 1", BoundingBox(5, 5, 180, 40))
            self.assertTrue(res["attempted"])
            runs = res.get("runs", [])
            # Assert that at least one whitelist=True pass was executed
            has_whitelist_run = any(run.get("whitelist") is True for run in runs)
            self.assertTrue(has_whitelist_run, "Expected at least one whitelist=True OCR pass for IMEI 1")

    def test_D_no_blind_cropping(self):
        # Empty tokens without label or region produces FIELD_REGION_NOT_LOCATED
        field_data: dict = {}
        attach_token_span_regions(field_data)
        self.assertNotIn("IMEI 1", field_data)

    def test_E_model_conflict_separation(self):
        # Even if T722 is in the span passed to extract_imei_pair, it is excluded
        tokens = [
            tok("T722", 0, 0),
            tok("943826", 50, 0),
            tok("-", 100, 0),
            tok("52", 110, 0),
            tok("-", 140, 0),
            tok("988142", 150, 0),
            tok("-", 200, 0),
            tok("5", 210, 0),
        ]
        imei1, imei1_toks, _, _ = extract_imei_pair(tokens, 0, len(tokens))
        digits = "".join(c for c in imei1 if c.isdigit())
        self.assertEqual(digits, "943826529881425")
        self.assertEqual(len(digits), 15)

    def test_9_postcode_ambiguity(self):
        self.assertFalse(is_valid_postcode("BNI 2FN"))
        self.assertFalse(is_valid_postcode("BN] 2FN"))

    def test_10_postcode_contextual_correction(self):
        repaired = repair_postcode_characters("BNI 2FN")
        self.assertEqual(repaired, "BN1 2FN")
        self.assertTrue(is_valid_postcode(repaired))

    def test_11_field_confidence_provenance(self):
        tokens = [
            tok("139", 0, 0, conf=90.0),
            tok("Kings", 45, 0, conf=95.0),
            tok("Road", 95, 0, conf=93.0),
        ]
        f_dict = build_field(tokens, "139 Kings Road")
        self.assertAlmostEqual(f_dict["confidence"], 92.67, places=1)
        self.assertIn("source_tokens", f_dict)
        self.assertEqual(len(f_dict["source_tokens"]), 3)

    def test_12_debug_image_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            img_path = Path(temp_dir) / "test.png"
            Image.new("RGB", (300, 200), color="white").save(img_path)
            record = {
                "record_number": 1,
                "fields": {
                    "IMEI 1": {
                        "coordinates": [{"x": 10, "y": 10, "width": 50, "height": 15}],
                        "field_region": {
                            "region": {"x": 10, "y": 10, "width": 50, "height": 15},
                            "anchor_bbox": {"x": 0, "y": 10, "width": 10, "height": 15},
                            "anchor_label": "IMEI 1",
                        },
                    },
                },
            }
            out_img = create_debug_image(img_path, record)
            self.assertTrue(out_img.exists())

    def test_H_f6_including_review_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ahk_path = Path(temp_dir) / "data_entry.ahk"
            fields = {name: {"value": f"review_{i}"} for i, name in enumerate(FIELD_ORDER)}
            review_rec = {"record_number": 1, "status": "REVIEW_REQUIRED", "fields": fields}
            generate_ahk([review_rec], ahk_path, review_count=1)
            content = ahk_path.read_text(encoding="utf-8")
            self.assertIn("review_required_count := 1", content)
            self.assertIn("scanned_records[1] :=", content)

    def test_15_f6_accepting_validated_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ahk_path = Path(temp_dir) / "data_entry.ahk"
            fields = {name: {"value": f"val_{i}"} for i, name in enumerate(FIELD_ORDER)}
            val_rec = {"record_number": 1, "status": "VALIDATED", "fields": fields}
            generate_ahk([val_rec], ahk_path, review_count=0)
            content = ahk_path.read_text(encoding="utf-8")
            self.assertIn("scanned_records[1] :=", content)
            self.assertIn("val_0", content)

    def test_16_no_form_increment_during_retry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            store = StateStore(db_path)
            try:
                store.reset_state(starting_form_no=110, starting_file_no=28)
                fp = "test_fingerprint_123"
                f1 = store.form_no_for(fp)
                f2 = store.form_no_for(fp)
                self.assertEqual(f1, 110)
                self.assertEqual(f2, 110)
            finally:
                store.close()

    def test_17_existing_31_field_output_compatibility(self):
        record = RawRecord(record_number=1, rows=[OCRRow(y=10, words=[tok("Mr", 0, 10), tok("John", 30, 10)])])
        extracted = extract_record(record.to_dict(), "28", 110)
        self.assertEqual(len(extracted["fields"]), 31)
        self.assertEqual(list(extracted["fields"].keys()), list(FIELD_ORDER))


if __name__ == "__main__":
    unittest.main()
