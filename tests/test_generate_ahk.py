"""Tests for the minimal, validated-record-only AHK v2 generator."""

from pathlib import Path
import unittest

from extraction.extractor import FIELD_ORDER
from generate_ahk import generate_ahk


class TestGenerateAhk(unittest.TestCase):
    def setUp(self) -> None:
        self.output_path = Path("output") / "test_data_entry.ahk"

    @staticmethod
    def record(status: str, marker: str) -> dict:
        return {
            "status": status,
            "fields": {
                field_name: {"value": f"{marker}-{position}"}
                for position, field_name in enumerate(FIELD_ORDER, start=1)
            },
        }

    def test_only_f6_and_escape_are_registered(self) -> None:
        generate_ahk([self.record("VALIDATED", "approved")], self.output_path)
        script = self.output_path.read_text(encoding="utf-8")
        self.assertIn("F6::{", script)
        self.assertIn("Esc::{", script)
        for key in ("F7", "F8", "F9", "F10", "F11", "F12"):
            self.assertNotIn(f"{key}::", script)

    def test_record_values_are_31_fields_in_existing_order(self) -> None:
        generate_ahk([self.record("VALIDATED", "approved")], self.output_path)
        script = self.output_path.read_text(encoding="utf-8")
        expected_names = ", ".join(f'\"{name}\"' for name in FIELD_ORDER)
        self.assertIn(expected_names, script)
        self.assertIn("if (index < 31)", script)
        self.assertNotIn("if (index < values.Length)", script)

    def test_review_records_are_not_embedded(self) -> None:
        generate_ahk(
            [self.record("VALIDATED", "approved"), self.record("REVIEW_REQUIRED", "do-not-enter")],
            self.output_path,
        )
        script = self.output_path.read_text(encoding="utf-8")
        self.assertIn("approved-1", script)
        self.assertNotIn("do-not-enter", script)

    def test_empty_validated_batch_is_safe(self) -> None:
        generate_ahk([self.record("REVIEW_REQUIRED", "do-not-enter")], self.output_path)
        script = self.output_path.read_text(encoding="utf-8")
        self.assertIn("No VALIDATED record available.", script)
        self.assertNotIn("do-not-enter", script)


if __name__ == "__main__":
    unittest.main()
