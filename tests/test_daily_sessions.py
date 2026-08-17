"""Regression tests for the non-destructive daily watcher startup layer."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import unittest
from unittest.mock import patch

from run_pipeline import configure_daily_watch_session
from state_store import StateStore


class TestDailySessions(unittest.TestCase):
    def setUp(self) -> None:
        # A dedicated test database avoids touching the operator's live state.
        self.db_path = Path("output") / "test_daily_sessions.db"
        store = StateStore(self.db_path, starting_form_no=110, starting_file_no=28)
        store.reset_state(starting_form_no=110, starting_file_no=28)
        # The test fixture's audit history is isolated from the live database.
        with store.connection:
            store.connection.execute("DELETE FROM pipeline_sessions")
        store.close()

    def _store_with_forms_through_115(self) -> StateStore:
        store = StateStore(self.db_path, starting_form_no=110, starting_file_no=28)
        for number in range(110, 116):
            self.assertEqual(store.form_no_for(f"record-{number}"), number)
        return store

    def test_continuation_keeps_existing_sequence(self) -> None:
        store = self._store_with_forms_through_115()
        state_before = store.numbering_state()
        store.record_continuation_session()
        state_after = store.numbering_state()
        self.assertEqual(state_before["next_form_no"], 116)
        self.assertEqual(state_after["next_form_no"], 116)
        self.assertEqual(store.form_no_for("next-record"), 116)
        store.close()

    def test_new_session_keeps_history_and_starts_new_file_group(self) -> None:
        store = self._store_with_forms_through_115()
        store.start_daily_session(file_no=29, starting_form_no=116)
        self.assertEqual(store.numbering_state()["file_no"], 29)
        self.assertEqual(store.numbering_state()["next_form_no"], 116)
        self.assertEqual(store.form_no_for("new-day-record"), 116)
        self.assertEqual(store.get_highest_form_no(), 116)
        store.close()

    def test_existing_file_or_form_is_rejected(self) -> None:
        store = self._store_with_forms_through_115()
        store.start_daily_session(file_no=29, starting_form_no=116)
        self.assertEqual(store.form_no_for("already-allocated-116"), 116)
        valid, _ = store.validate_new_numbering(29, 117)
        self.assertFalse(valid)
        valid, _ = store.validate_new_numbering(30, 116)
        self.assertFalse(valid)
        store.close()

    def test_concurrent_allocations_are_unique(self) -> None:
        StateStore(self.db_path, starting_form_no=110).close()

        def allocate(index: int) -> int:
            store = StateStore(self.db_path, starting_form_no=110)
            try:
                return store.form_no_for(f"concurrent-{index}")
            finally:
                store.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            allocated = list(pool.map(allocate, range(8)))
        self.assertEqual(sorted(allocated), list(range(110, 118)))

    def test_startup_yes_continues_without_reset(self) -> None:
        store = self._store_with_forms_through_115()
        with patch("builtins.input", side_effect=["invalid", "Y"]):
            selected_file_no = configure_daily_watch_session(store)
        self.assertEqual(selected_file_no, 28)
        self.assertEqual(store.get_next_form_no(), 116)
        store.close()

    def test_startup_no_validates_then_persists_new_session(self) -> None:
        store = self._store_with_forms_through_115()
        with patch("builtins.input", side_effect=["N", "29", "116", "yes"]):
            selected_file_no = configure_daily_watch_session(store)
        self.assertEqual(selected_file_no, 29)
        self.assertEqual(store.numbering_state()["next_form_no"], 116)
        self.assertEqual(store.numbering_state()["file_no"], 29)
        store.close()


if __name__ == "__main__":
    unittest.main()
