"""Durable SQLite State Store with concurrency protection and atomic sequence allocation.

SEQUENCE RULES:
- Form No increments strictly PER RECORD.
- File No increments strictly PER 4 IMAGES: File No = starting_file_no + (image_count // 4)
- Form No continues sequentially across all images without gaps or collisions.
"""

import hashlib
from pathlib import Path
import sqlite3
import time
from datetime import datetime
from typing import Dict, Optional, Tuple


class StateStore:
    def __init__(
        self,
        path: Path,
        starting_form_no: int = 110,
        starting_file_no: int = 28,
        timeout: float = 30.0,
    ) -> None:
        self.db_path = Path(path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.connection = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=self.timeout,
        )
        self.connection.row_factory = sqlite3.Row
        self._init_db(starting_form_no, starting_file_no)

    def _begin_immediate(self, retries: int = 5) -> None:
        """Acquire SQLite's write lock before reading and allocating a sequence number."""
        for attempt in range(retries):
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == retries - 1:
                    raise
                time.sleep(0.05 * (attempt + 1))

    def _init_db(self, starting_form_no: int, starting_file_no: int) -> None:
        try:
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.execute("PRAGMA synchronous=NORMAL")
            self.connection.execute(f"PRAGMA busy_timeout={int(self.timeout * 1000)}")
        except sqlite3.OperationalError:
            pass

        with self.connection:
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            self.connection.execute(
                """CREATE TABLE IF NOT EXISTS images (
                    sha256 TEXT PRIMARY KEY,
                    file_no INTEGER,
                    path TEXT NOT NULL,
                    processed_at TEXT DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            self.connection.execute(
                """CREATE TABLE IF NOT EXISTS records (
                    fingerprint TEXT PRIMARY KEY,
                    form_no INTEGER UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            self.connection.execute(
                """CREATE TABLE IF NOT EXISTS pipeline_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_date TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    file_no INTEGER NOT NULL,
                    starting_form_no INTEGER NOT NULL,
                    last_form_no INTEGER,
                    status TEXT NOT NULL
                )"""
            )
            self.connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pipeline_sessions_started_at "
                "ON pipeline_sessions(started_at DESC)"
            )
            # Migration check: Ensure file_no column exists in images table
            cursor = self.connection.execute("PRAGMA table_info(images)")
            columns = [row[1] for row in cursor.fetchall()]
            if "file_no" not in columns:
                self.connection.execute("ALTER TABLE images ADD COLUMN file_no INTEGER")

        self.repair_and_sync_state(starting_form_no, starting_file_no)

    def repair_and_sync_state(
        self,
        fallback_starting_form: int = 110,
        fallback_starting_file: int = 28,
    ) -> Tuple[int, int]:
        """Detect and synchronize sequence states for both Form No and File No."""
        with self.connection:
            # Form No sync
            max_form_row = self.connection.execute("SELECT max(form_no) FROM records").fetchone()
            max_form_existing = int(max_form_row[0]) if (max_form_row and max_form_row[0] is not None) else None

            form_setting_row = self.connection.execute("SELECT value FROM settings WHERE key = 'next_form_no'").fetchone()
            current_form_setting = int(form_setting_row[0]) if (form_setting_row and form_setting_row[0]) else fallback_starting_form

            if max_form_existing is not None and current_form_setting <= max_form_existing:
                repaired_form_next = max_form_existing + 1
            else:
                repaired_form_next = max(current_form_setting, fallback_starting_form)

            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('next_form_no', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(repaired_form_next), str(repaired_form_next)),
            )

            # Starting File No sync
            file_setting_row = self.connection.execute("SELECT value FROM settings WHERE key = 'starting_file_no'").fetchone()
            if not file_setting_row:
                self.connection.execute(
                    "INSERT INTO settings(key, value) VALUES ('starting_file_no', ?)",
                    (str(fallback_starting_file),),
                )
                current_file_base = fallback_starting_file
            else:
                current_file_base = int(file_setting_row[0])

            count_row = self.connection.execute("SELECT count(*) FROM images").fetchone()
            image_count = int(count_row[0]) if (count_row and count_row[0] is not None) else 0
            repaired_file_next = current_file_base + (image_count // 4)

            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('next_file_no', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(repaired_file_next), str(repaired_file_next)),
            )
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('file_group_start_count', ?) "
                "ON CONFLICT(key) DO NOTHING",
                ("0",),
            )

            return repaired_form_next, repaired_file_next

    def reset_state(self, starting_form_no: int = 110, starting_file_no: int = 28) -> None:
        """Reset sequence counters and clear database tables."""
        with self.connection:
            self.connection.execute("DELETE FROM records")
            self.connection.execute("DELETE FROM images")
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('starting_file_no', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(starting_file_no), str(starting_file_no)),
            )
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('next_form_no', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(starting_form_no), str(starting_form_no)),
            )
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('next_file_no', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(starting_file_no), str(starting_file_no)),
            )
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('file_group_start_count', '0') "
                "ON CONFLICT(key) DO UPDATE SET value = '0'"
            )

    @staticmethod
    def file_hash(path: Path) -> str:
        """Calculate SHA256 digest of file content."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def image_seen(self, digest: str) -> bool:
        """Check if an image hash has already been processed."""
        with self.connection:
            row = self.connection.execute("SELECT 1 FROM images WHERE sha256 = ?", (digest,)).fetchone()
            return row is not None

    def mark_image_processed(self, digest: str, file_no: int, path: Path) -> None:
        """Record processed image hash, allocated File No, and path."""
        with self.connection:
            self.connection.execute(
                "INSERT INTO images(sha256, file_no, path) VALUES (?, ?, ?) ON CONFLICT(sha256) DO UPDATE SET file_no = ?, path = ?",
                (digest, file_no, str(path), file_no, str(path)),
            )

    def get_highest_form_no(self) -> Optional[int]:
        with self.connection:
            row = self.connection.execute("SELECT max(form_no) FROM records").fetchone()
            return int(row[0]) if (row and row[0] is not None) else None

    def get_next_form_no(self) -> int:
        with self.connection:
            row = self.connection.execute("SELECT value FROM settings WHERE key = 'next_form_no'").fetchone()
            return int(row[0]) if (row and row[0] is not None) else 110

    def get_highest_file_no(self) -> Optional[int]:
        with self.connection:
            row = self.connection.execute("SELECT max(file_no) FROM images").fetchone()
            return int(row[0]) if (row and row[0] is not None) else None

    def get_next_file_no(self) -> int:
        with self.connection:
            base_row = self.connection.execute("SELECT value FROM settings WHERE key = 'starting_file_no'").fetchone()
            base_file_no = int(base_row[0]) if (base_row and base_row[0] is not None) else 28
            count_row = self.connection.execute("SELECT count(*) FROM images").fetchone()
            image_count = int(count_row[0]) if (count_row and count_row[0] is not None) else 0
            group_start_row = self.connection.execute(
                "SELECT value FROM settings WHERE key = 'file_group_start_count'"
            ).fetchone()
            group_start_count = int(group_start_row[0]) if group_start_row else 0
            return base_file_no + (max(0, image_count - group_start_count) // 4)

    def get_or_allocate_file_no(self, digest: str, starting_file_no: int = 28) -> int:
        """Atomically allocate or retrieve File No for an image according to the 4-images-per-file rule."""
        with self.connection:
            row = self.connection.execute("SELECT file_no FROM images WHERE sha256 = ?", (digest,)).fetchone()
            if row and row[0] is not None:
                return int(row[0])

            base_row = self.connection.execute("SELECT value FROM settings WHERE key = 'starting_file_no'").fetchone()
            base_file_no = int(base_row[0]) if (base_row and base_row[0] is not None) else starting_file_no

            count_row = self.connection.execute("SELECT count(*) FROM images").fetchone()
            image_count = int(count_row[0]) if (count_row and count_row[0] is not None) else 0
            group_start_row = self.connection.execute(
                "SELECT value FROM settings WHERE key = 'file_group_start_count'"
            ).fetchone()
            group_start_count = int(group_start_row[0]) if group_start_row else 0
            assigned_file_no = base_file_no + (max(0, image_count - group_start_count) // 4)

            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('next_file_no', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(assigned_file_no), str(assigned_file_no)),
            )
            return assigned_file_no

    def form_no_for(self, fingerprint: str) -> int:
        """Atomically allocate or retrieve unique Form No for a record fingerprint."""
        self._begin_immediate()
        try:
            row = self.connection.execute("SELECT form_no FROM records WHERE fingerprint = ?", (fingerprint,)).fetchone()
            if row:
                self.connection.commit()
                return int(row[0])

            max_row = self.connection.execute("SELECT max(form_no) FROM records").fetchone()
            max_existing = int(max_row[0]) if (max_row and max_row[0] is not None) else None

            settings_row = self.connection.execute("SELECT value FROM settings WHERE key = 'next_form_no'").fetchone()
            current_setting = int(settings_row[0]) if (settings_row and settings_row[0]) else 110

            if max_existing is not None and current_setting <= max_existing:
                assigned_form_no = max_existing + 1
            else:
                assigned_form_no = current_setting

            # Ensure collision-free increment
            while self.connection.execute("SELECT 1 FROM records WHERE form_no = ?", (assigned_form_no,)).fetchone() is not None:
                assigned_form_no += 1

            self.connection.execute(
                "INSERT INTO records(fingerprint, form_no, status) VALUES (?, ?, 'PENDING')",
                (fingerprint, assigned_form_no),
            )
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('next_form_no', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(assigned_form_no + 1), str(assigned_form_no + 1)),
            )
            self.connection.commit()
            return assigned_form_no
        except Exception:
            self.connection.rollback()
            raise

    def set_record_status(self, fingerprint: str, status: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE records SET status = ? WHERE fingerprint = ?", (status, fingerprint))

    def set_next_form_no(self, form_no: int) -> int:
        with self.connection:
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('next_form_no', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(form_no), str(form_no)),
            )
            return form_no

    def set_starting_file_no(self, file_no: int) -> int:
        with self.connection:
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('starting_file_no', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(file_no), str(file_no)),
            )
            return file_no

    def numbering_state(self) -> Dict[str, Optional[int]]:
        """Return the SQLite-authoritative state displayed by the daily startup UI."""
        return {
            "file_no": self.get_next_file_no(),
            "last_file_no": self.get_highest_file_no(),
            "last_form_no": self.get_highest_form_no(),
            "next_form_no": self.get_next_form_no(),
        }

    def file_no_exists(self, file_no: int) -> bool:
        with self.connection:
            row = self.connection.execute(
                "SELECT 1 FROM images WHERE file_no = ? LIMIT 1", (file_no,)
            ).fetchone()
            if row is not None:
                return True
            row = self.connection.execute(
                "SELECT 1 FROM pipeline_sessions WHERE file_no = ? LIMIT 1", (file_no,)
            ).fetchone()
            return row is not None

    def validate_new_numbering(self, file_no: int, starting_form_no: int) -> Tuple[bool, str]:
        """Reject a proposed session that could overlap historical allocations."""
        if file_no <= 0 or starting_form_no <= 0:
            return False, "File No and Starting Form No must be positive integers."
        if self.file_no_exists(file_no):
            return False, f"File No {file_no} already exists. Choose a different File No."
        highest_form = self.get_highest_form_no()
        if highest_form is not None and starting_form_no <= highest_form:
            return False, (
                f"Form No {starting_form_no} is already allocated or below the next safe number "
                f"({highest_form + 1})."
            )
        return True, ""

    def start_daily_session(self, file_no: int, starting_form_no: int, started_at: Optional[datetime] = None) -> int:
        """Persist a non-destructive daily configuration and begin a fresh 4-image file group."""
        valid, reason = self.validate_new_numbering(file_no, starting_form_no)
        if not valid:
            raise ValueError(reason)
        timestamp = started_at or datetime.now().astimezone()
        with self.connection:
            image_count = int(self.connection.execute("SELECT count(*) FROM images").fetchone()[0])
            cursor = self.connection.execute(
                "INSERT INTO pipeline_sessions(session_date, started_at, file_no, starting_form_no, last_form_no, status) "
                "VALUES (?, ?, ?, ?, ?, 'ACTIVE')",
                (
                    timestamp.date().isoformat(), timestamp.isoformat(), file_no,
                    starting_form_no, self.get_highest_form_no(),
                ),
            )
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('starting_file_no', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(file_no), str(file_no)),
            )
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('next_form_no', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(starting_form_no), str(starting_form_no)),
            )
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('file_group_start_count', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(image_count), str(image_count)),
            )
            return int(cursor.lastrowid)

    def record_continuation_session(self, started_at: Optional[datetime] = None) -> int:
        """Audit a continued watcher startup without changing its numbering state."""
        timestamp = started_at or datetime.now().astimezone()
        state = self.numbering_state()
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO pipeline_sessions(session_date, started_at, file_no, starting_form_no, last_form_no, status) "
                "VALUES (?, ?, ?, ?, ?, 'ACTIVE')",
                (timestamp.date().isoformat(), timestamp.isoformat(), state["file_no"],
                 state["next_form_no"], state["last_form_no"]),
            )
            return int(cursor.lastrowid)

    def set_next_file_no(self, file_no: int) -> int:
        with self.connection:
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES ('next_file_no', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (str(file_no), str(file_no)),
            )
            return file_no

    def close(self) -> None:
        if self.connection:
            self.connection.close()
