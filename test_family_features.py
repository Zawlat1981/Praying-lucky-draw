import base64
import hashlib
import unittest
from unittest.mock import MagicMock, PropertyMock, patch
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet
from oauthlib.oauth2 import InvalidGrantError

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
        settings = {"token_encryption_key": Fernet.generate_key().decode()}
        with patch.object(drive_storage.time, "time", return_value=1000):
            state = drive_storage._make_oauth_state(settings, "test-verifier")
        with patch.object(drive_storage.time, "time", return_value=1001):
            self.assertEqual(drive_storage._oauth_verifier(settings, state), "test-verifier")
            with self.assertRaises(ValueError):
                drive_storage._oauth_verifier(settings, state[:20] + ("A" if state[20] != "A" else "B") + state[21:])
        with patch.object(drive_storage.time, "time", return_value=1601):
            with self.assertRaises(ValueError):
                drive_storage._oauth_verifier(settings, state)

    def test_oauth_callback_uses_the_original_pkce_verifier(self):
        settings = {
            "client_id": "test-client",
            "client_secret": "test-secret",
            "redirect_uri": "https://example.streamlit.app/",
            "token_encryption_key": Fernet.generate_key().decode(),
        }
        credentials = MagicMock(refresh_token="refresh-token")
        captured = {}

        def fetch_token(flow, **kwargs):
            captured["verifier"] = flow.code_verifier
            captured["code"] = kwargs["code"]

        with (
            patch.object(drive_storage, "_settings", return_value=settings),
            patch.object(drive_storage.Flow, "fetch_token", autospec=True, side_effect=fetch_token),
            patch.object(drive_storage.Flow, "credentials", new_callable=PropertyMock, return_value=credentials),
            patch.object(drive_storage, "_save_encrypted_credentials") as save,
        ):
            params = parse_qs(urlparse(drive_storage.authorization_url()).query)
            state = params["state"][0]
            drive_storage.handle_callback({}, {"state": state, "code": "authorization-code"})
            verifier = captured["verifier"]
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode().rstrip("=")
            self.assertEqual(params["code_challenge"], [challenge])
            self.assertNotIn(verifier, state)
            self.assertEqual(captured["code"], "authorization-code")
            save.assert_called_once_with({}, credentials)

    def test_rejected_oauth_code_is_cleared_and_reported(self):
        query = {"code": "expired-code", "state": "state"}
        with (
            patch.object(drive_storage.st, "query_params", query),
            patch.object(drive_storage.st, "subheader"),
            patch.object(drive_storage.st, "error") as error,
            patch.object(drive_storage, "handle_callback", side_effect=InvalidGrantError()),
        ):
            drive_storage.show_drive_connection({})
            self.assertEqual(query, {})
            error.assert_called_once()

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
