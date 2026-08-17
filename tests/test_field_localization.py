"""Tests for label-first, geometry-bounded field localization."""

import unittest

from ocr.field_localization import locate_field_regions
from ocr.tokens import BoundingBox, OCRRow, OCRToken, RawRecord


def token(text: str, x: int, y: int) -> OCRToken:
    return OCRToken(text=text, bbox=BoundingBox(x, y, 35, 12), confidence=90.0)


class TestFieldLocalization(unittest.TestCase):
    def test_locates_imei_and_postcode_to_the_right_of_labels(self) -> None:
        record = RawRecord(
            record_number=1,
            rows=[
                OCRRow(y=10, words=[token("IMEI", 10, 10), token("1", 52, 10), token("490154203237518", 100, 10)]),
                OCRRow(y=40, words=[token("Post", 10, 40), token("Code", 55, 40), token("BN1", 120, 40), token("2FN", 160, 40)]),
            ],
        )
        regions = locate_field_regions(record)
        self.assertEqual(regions["IMEI 1"].anchor_label, "IMEI 1")
        self.assertEqual(regions["IMEI 1"].value_bbox.x, 100)
        self.assertEqual(regions["Postal Code"].value_bbox.x, 120)

    def test_does_not_create_region_without_a_label(self) -> None:
        record = RawRecord(record_number=1, rows=[OCRRow(y=10, words=[token("490154203237518", 100, 10)])])
        self.assertNotIn("IMEI 1", locate_field_regions(record))


if __name__ == "__main__":
    unittest.main()
