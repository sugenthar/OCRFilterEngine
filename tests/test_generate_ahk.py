"""Tests for the scan-to-AHK v2 generator."""

from pathlib import Path
import tempfile
import unittest

from extraction.extractor import FIELD_ORDER
from generate_ahk import generate_ahk


class TestGenerateAhk(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_path = Path(self.temp_dir.name) / "test_data_entry.ahk"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

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
        self.assertIn("current_record_index += 1", script)
        self.assertNotIn("if (index < values.Length)", script)

    def test_review_records_are_written_to_the_script(self) -> None:
        generate_ahk(
            [self.record("VALIDATED", "approved"), self.record("REVIEW_REQUIRED", "do-not-enter")],
            self.output_path,
        )
        script = self.output_path.read_text(encoding="utf-8")
        self.assertIn("approved-1", script)
        self.assertIn("do-not-enter", script)
        self.assertIn('status: "REVIEW_REQUIRED"', script)

    def test_review_only_batch_is_written(self) -> None:
        generate_ahk([self.record("REVIEW_REQUIRED", "do-not-enter")], self.output_path)
        script = self.output_path.read_text(encoding="utf-8")
        self.assertIn("do-not-enter", script)
        self.assertIn("scanned_records[1] :=", script)

    def test_empty_scan_explains_how_to_continue(self) -> None:
        generate_ahk([], self.output_path)
        script = self.output_path.read_text(encoding="utf-8")
        self.assertIn("No scanned record available. Process an image first.", script)

    def test_f6_uses_the_currently_active_window(self) -> None:
        generate_ahk([self.record("VALIDATED", "approved")], self.output_path)
        script = self.output_path.read_text(encoding="utf-8")
        self.assertNotIn("TARGET_WINDOW_TITLE", script)
        self.assertNotIn("Open the configured data-entry form first.", script)
        self.assertIn('target_window := WinExist("A")', script)


if __name__ == "__main__":
    unittest.main()
