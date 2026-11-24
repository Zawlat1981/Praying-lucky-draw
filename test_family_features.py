import unittest
from unittest.mock import patch

import drive_storage
import family_auth
import teaching


class FamilyFeatureTest(unittest.TestCase):
    def test_teaching_outline_uses_selected_reference_and_offline_prompts(self):
        outline = teaching.make_outline(
            {"book": "ယောဟန်", "chapter": 3, "verse": 16, "text": "test"}
        )
        self.assertIn("ယောဟန် 3:16", outline["title"])
        self.assertEqual(len(outline["outline"]), 3)
        self.assertIn("တိုက်ရိုက်ကူးထားခြင်း မဟုတ်", outline["source_note"])

    def test_drive_oauth_state_is_signed_and_expires(self):
        settings = {"token_encryption_key": "test-key-not-used-for-fernet-here"}
        with patch.object(drive_storage.time, "time", return_value=1000):
            state = drive_storage._make_oauth_state(settings)
        with patch.object(drive_storage.time, "time", return_value=1001):
            self.assertTrue(drive_storage._verify_oauth_state(settings, state))
            self.assertFalse(drive_storage._verify_oauth_state(settings, state + "tampered"))
        with patch.object(drive_storage.time, "time", return_value=1601):
            self.assertFalse(drive_storage._verify_oauth_state(settings, state))

    def test_family_password_is_required_and_authenticated_sessions_pass(self):
        state = {}
        with (
            patch.object(family_auth.st, "session_state", state),
            patch.object(family_auth.st, "secrets", {"family": {"password": "a-family-password-longer-than-16"}}),
            patch.object(family_auth.st, "stop", side_effect=RuntimeError("stopped")) as stop,
        ):
            with self.assertRaises(RuntimeError):
                family_auth.require_family_password()
            stop.assert_called_once()
            state["family_authenticated"] = True
            family_auth.require_family_password()


if __name__ == "__main__":
    unittest.main()
