import json
import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from unittest.mock import MagicMock, patch

import psycopg
from streamlit.testing.v1 import AppTest

import backup
import family_auth
import storage


class BackupTest(unittest.TestCase):
    def setUp(self):
        self.verse = {"book": "Test", "chapter": 1, "verse": 2, "text": "Test text"}
        self.history = {
            "id": str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "verse": self.verse,
            "leader": "A",
            "teacher": "B",
            "teaching": {
                "title": "Title",
                "theme": "Theme",
                "reading": "Reading",
                "outline": ["One point"],
                "discussion": "Discussion",
                "application": "Application",
                "prayer": "Prayer",
                "source_note": "Offline",
            },
            "prayer_audio_file_id": "drive-audio-id",
            "teaching_audio_file_id": None,
        }
        self.data = {
            "version": 2,
            "members": ["A", "B"],
            "custom_verses": [self.verse],
            "favorites": [self.verse],
            "history": [self.history],
        }
        self.config = {"host": "example", "user": "user", "password": "password", "database": "db"}

    def test_backup_contains_consistent_application_data(self):
        db = MagicMock()
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect = [
            [{"name": "A"}, {"name": "B"}],
            [self.verse],
            [self.verse],
            [
                {
                    **self.history,
                    "id": UUID(self.history["id"]),
                    "created_at": datetime.fromisoformat(self.history["created_at"]),
                }
            ],
        ]
        with patch.object(storage.psycopg, "connect", return_value=db):
            exported = json.loads(backup.create_backup(self.config))
        for field in ("version", "members", "custom_verses", "favorites", "history"):
            self.assertEqual(exported[field], self.data[field])
        self.assertIn("REPEATABLE READ READ ONLY", cursor.execute.call_args_list[0].args[0])
        db.commit.assert_called_once()

    def test_restore_merges_and_counts_new_entries(self):
        db = MagicMock()
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = lambda *args: setattr(
            cursor,
            "rowcount",
            0 if args[0].startswith("INSERT INTO prayer_members") and args[1] == ("A",) else 1,
        )
        with patch.object(storage.psycopg, "connect", return_value=db):
            counts = backup.restore_backup(self.config, self.data)
        self.assertEqual(counts, {"members": 1, "custom_verses": 1, "favorites": 1, "history": 1})
        self.assertTrue(all("ON CONFLICT" in call.args[0] for call in cursor.execute.call_args_list))
        db.commit.assert_called_once()

    def test_invalid_backup_is_rejected_before_connection(self):
        for data in (
            {"version": 2, "members": [], "custom_verses": [], "favorites": []},
            {**self.data, "history": [{**self.history, "created_at": "not a date"}]},
            {**self.data, "history": [{**self.history, "teaching": {}}]},
            {**self.data, "members": [""]},
            {**self.data, "favorites": [{**self.verse, "chapter": True}]},
            {**self.data, "favorites": [{**self.verse, "text": "bad\0text"}]},
        ):
            with self.subTest(data=data), patch.object(storage.psycopg, "connect") as connect:
                with self.assertRaises(ValueError):
                    backup.restore_backup(self.config, data)
                connect.assert_not_called()

    def test_restore_failure_rolls_back_everything(self):
        db = MagicMock()
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = [None, psycopg.Error("failure")]
        with patch.object(storage.psycopg, "connect", return_value=db):
            with self.assertRaises(psycopg.Error):
                backup.restore_backup(self.config, self.data)
        db.rollback.assert_called_once()
        db.commit.assert_not_called()

    def test_backup_login_and_logout(self):
        backup.login_guard.clear()
        with (
            patch("streamlit.secrets", {"postgresql": {}, "family": {"password": "long-family-password"}, "backup": {"admin_password": "long-test-password"}}),
            patch.object(family_auth, "require_family_password"),
            patch.object(storage, "initialize"),
            patch.object(storage, "list_members", return_value=["A", "B"]),
            patch.object(storage, "list_verses", return_value=[]),
            patch.object(storage, "count_worship_sessions", return_value=0),
            patch.object(storage, "list_worship_sessions", return_value=[]),
        ):
            app = AppTest.from_file("ab.py", default_timeout=20)
            app.run()
            self.assertFalse(any(b.label == "Backup ဖိုင် ပြင်ဆင်မည်" for b in app.button))
            app.text_input(key="backup_password_input").set_value("wrong")
            next(b for b in app.button if b.label == "ဝင်မည်").click().run()
            self.assertTrue(any("password" in error.value for error in app.error))
            app.text_input(key="backup_password_input").set_value("long-test-password")
            next(b for b in app.button if b.label == "ဝင်မည်").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any(b.label == "Backup ဖိုင် ပြင်ဆင်မည်" for b in app.button))
            next(b for b in app.button if b.label == "Admin ထွက်မည်").click().run()
            self.assertFalse(any(b.label == "Backup ဖိုင် ပြင်ဆင်မည်" for b in app.button))

    def test_admin_lockout_after_repeated_failures(self):
        backup.login_guard.clear()
        state = {}
        with (
            patch.object(backup.st, "session_state", state),
            patch.object(backup.st, "secrets", {"backup": {"admin_password": "long-test-password"}}),
            patch.object(backup.time, "monotonic", return_value=1000),
        ):
            for _ in range(backup.MAX_ATTEMPTS):
                state["backup_password_input"] = "wrong"
                backup.authenticate()
            state["backup_password_input"] = "long-test-password"
            backup.authenticate()
            self.assertNotIn("backup_auth", state)
            self.assertIn("၅", state["backup_login_error"])
        backup.login_guard.clear()


if __name__ == "__main__":
    unittest.main()
