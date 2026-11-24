import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

import storage
import family_auth


class PrayerAppTest(unittest.TestCase):
    def app(self):
        app = AppTest.from_file("ab.py", default_timeout=20)
        return app.run()

    def test_member_and_custom_verse_remain_in_new_session(self):
        members = ["A", "B"]
        verses = []

        def save_member(config, name):
            members.append(name)
            return True

        def save_verse(config, table, verse):
            self.assertEqual(table, "prayer_custom_verses")
            verses.append(verse.copy())
            return True

        with (
            patch("streamlit.secrets", {"postgresql": {}, "family": {"password": "long-family-password"}}),
            patch.object(family_auth, "require_family_password"),
            patch.object(storage, "initialize"),
            patch.object(storage, "list_members", side_effect=lambda config: members.copy()),
            patch.object(storage, "list_verses", side_effect=lambda config, table: verses.copy() if table == "prayer_custom_verses" else []),
            patch.object(storage, "save_member", side_effect=save_member),
            patch.object(storage, "save_verse", side_effect=save_verse),
            patch.object(storage, "count_worship_sessions", return_value=0),
            patch.object(storage, "list_worship_sessions", return_value=[]),
        ):
            app = self.app()
            app.text_input(key="family_member_input").set_value("C")
            next(button for button in app.button if button.label == "မိသားစုဝင်စာရင်းထဲသို့ ထည့်မည်").click().run()
            app.text_input(key="bible_book").set_value("Test Book")
            app.text_area(key="bible_text").set_value("Test verse")
            next(button for button in app.button if button.label == "ကျမ်းစာဖိုင်ထဲသို့ သိမ်းမည်").click().run()
            self.assertEqual(members, ["A", "B", "C"])
            self.assertEqual(verses[0]["text"], "Test verse")
            new_session = self.app()
            self.assertFalse(new_session.exception)
            self.assertTrue(any("31045" in item.value for item in new_session.subheader))
            self.assertIn("Test Book", new_session.selectbox[0].options)

    def test_draw_and_favorite_survive_new_session(self):
        favorites = []
        sessions = []

        def save_verse(config, table, verse):
            self.assertEqual(table, "prayer_favorites")
            favorites.append(verse.copy())
            return True

        def save_session(config, verse, leader, teacher_person, outline):
            sessions.append(
                {
                    "id": "session-1",
                    "created_at": datetime.now(timezone.utc),
                    "verse": verse,
                    "leader": leader,
                    "teacher": teacher_person,
                    "teaching": outline,
                    "prayer_audio_file_id": None,
                    "teaching_audio_file_id": None,
                }
            )
            return "session-1"

        with (
            patch("streamlit.secrets", {"postgresql": {}, "family": {"password": "long-family-password"}}),
            patch.object(family_auth, "require_family_password"),
            patch.object(storage, "initialize"),
            patch.object(storage, "list_members", return_value=["A", "B"]),
            patch.object(storage, "list_verses", side_effect=lambda config, table: favorites if table == "prayer_favorites" else []),
            patch.object(storage, "save_verse", side_effect=save_verse),
            patch.object(storage, "save_worship_session", side_effect=save_session),
            patch.object(storage, "list_worship_sessions", side_effect=lambda config, limit=20, offset=0: sessions[offset:offset + limit]),
            patch.object(storage, "count_worship_sessions", side_effect=lambda config: len(sessions)),
            patch("time.sleep"),
        ):
            app = self.app()
            self.assertFalse(app.exception)
            self.assertTrue(any("31044" in item.value for item in app.subheader))
            next(button for button in app.button if button.label.startswith("ကျမ်းချက်နှင့် တာဝန်ကျသူများ")).click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(sessions), 1)
            self.assertTrue(sessions[0]["teaching"]["title"])
            next(button for button in app.button if button.label == "⭐ ရွေးထားသောကျမ်းချက်ကို မှတ်ထားမည်").click().run()
            self.assertEqual(len(favorites), 1)
            new_session = self.app()
            self.assertFalse(new_session.exception)
            self.assertTrue(any(favorites[0]["text"] == item.value for item in new_session.info))

    def test_database_error_does_not_report_success(self):
        import psycopg

        with (
            patch("streamlit.secrets", {"postgresql": {}, "family": {"password": "long-family-password"}}),
            patch.object(family_auth, "require_family_password"),
            patch.object(storage, "initialize"),
            patch.object(storage, "list_members", return_value=["A", "B"]),
            patch.object(storage, "list_verses", return_value=[]),
            patch.object(storage, "save_worship_session", side_effect=psycopg.Error("database unavailable")),
            patch.object(storage, "count_worship_sessions", return_value=0),
            patch.object(storage, "list_worship_sessions", return_value=[]),
            patch("time.sleep"),
        ):
            app = self.app()
            next(button for button in app.button if button.label.startswith("ကျမ်းချက်နှင့် တာဝန်ကျသူများ")).click().run()
            self.assertTrue(app.error)
            self.assertFalse(any("History ထဲ သိမ်းပြီးပါပြီ" in item.value for item in app.success))

    def test_database_transaction_commits_or_rolls_back(self):
        db = MagicMock()
        with (
            patch.object(storage.psycopg, "connect", return_value=db) as connect,
        ):
            with storage.connection({"host": "example", "user": "user", "password": "password", "database": "db"}):
                pass
            self.assertEqual(connect.call_args.kwargs["sslmode"], "verify-full")
            self.assertEqual(connect.call_args.kwargs["sslrootcert"], storage.certifi.where())
            db.commit.assert_called_once()
            db.close.assert_called_once()
            db.reset_mock()
            with self.assertRaises(ValueError):
                with storage.connection({"host": "example", "user": "user", "password": "password", "database": "db"}):
                    raise ValueError("failure")
            db.rollback.assert_called_once()
            db.commit.assert_not_called()
            db.close.assert_called_once()
            with storage.connection({"host": "example", "user": "user", "password": "password", "database": "db", "ca_certificate": "test CA"}):
                ca_file = Path(connect.call_args.kwargs["sslrootcert"])
                self.assertEqual(ca_file.read_text(encoding="utf-8"), "test CA")
            self.assertFalse(ca_file.exists())


if __name__ == "__main__":
    unittest.main()
