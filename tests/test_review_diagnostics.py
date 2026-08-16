"""Tests for transparent record-review diagnostics."""

import unittest

from run_pipeline import attach_review_evidence


class TestReviewDiagnostics(unittest.TestCase):
    def test_field_evidence_exposes_validation_reason(self) -> None:
        record = {
            "record_number": 1,
            "fields": {
                "Postal Code": {
                    "value": "BNI 2FN", "raw_text": "BNI 2FN", "confidence": 16.0,
                },
                "Email": {"value": "person@example.com", "raw_text": "person@example.com", "confidence": 90.0},
            },
        }
        attach_review_evidence(record, [{"field": "Postal Code", "reason": "LOW_OCR_CONFIDENCE", "detail": "low"}])
        self.assertEqual(record["fields"]["Postal Code"]["validation"], "REVIEW")
        self.assertEqual(record["fields"]["Postal Code"]["failure_reasons"], ["LOW_OCR_CONFIDENCE"])
        self.assertEqual(record["fields"]["Email"]["validation"], "PASS")
        self.assertEqual(record["fields"]["Email"]["targeted_ocr"]["decision"], "NOT_REQUIRED")


if __name__ == "__main__":
    unittest.main()
