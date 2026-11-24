import base64
import hashlib
import hmac
import io
import json
import logging
import secrets
import time

import google.auth.transport.requests
import googleapiclient.discovery
import googleapiclient.http
import googleapiclient.errors
import psycopg
import streamlit as st
from cryptography.fernet import Fernet, InvalidToken
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

import storage

logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_NAME = "Family Worship App Recordings"
MAX_RECORDING_BYTES = 200 * 1024 * 1024


def _settings():
    settings = st.secrets.get("drive", {})
    required = ("client_id", "client_secret", "redirect_uri", "token_encryption_key")
    if any(not isinstance(settings.get(name), str) or not settings[name].strip() for name in required):
        raise ValueError("Google Drive OAuth settings are missing")
    return settings


def _fernet(settings):
    try:
        return Fernet(settings["token_encryption_key"].encode("ascii"))
    except (ValueError, UnicodeEncodeError) as error:
        raise ValueError("Invalid Drive token encryption key") from error


def _flow(settings, state=None):
    client_config = {
        "web": {
            "client_id": settings["client_id"],
            "client_secret": settings["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings["redirect_uri"]],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES, state=state)
    flow.redirect_uri = settings["redirect_uri"]
    return flow


def _make_oauth_state(settings):
    payload = base64.urlsafe_b64encode(
        json.dumps({"nonce": secrets.token_urlsafe(24), "expires": int(time.time()) + 600}).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(settings["token_encryption_key"].encode("ascii"), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def _verify_oauth_state(settings, state):
    try:
        payload, signature = state.split(".", 1)
        expected = hmac.new(
            settings["token_encryption_key"].encode("ascii"), payload.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        return int(json.loads(decoded)["expires"]) >= int(time.time())
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return False


def _save_encrypted_credentials(config, credentials):
    settings = _settings()
    encrypted = _fernet(settings).encrypt(credentials.to_json().encode("utf-8")).decode("ascii")
    with storage.connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO prayer_app_settings (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                ("drive_credentials", encrypted),
            )


def _load_credentials(config):
    settings = _settings()
    with storage.connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT value FROM prayer_app_settings WHERE key = %s", ("drive_credentials",))
            row = cursor.fetchone()
    if row is None:
        return None
    try:
        token_json = _fernet(settings).decrypt(row["value"].encode("ascii")).decode("utf-8")
        credentials = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("Could not decrypt Google Drive credentials") from error
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(google.auth.transport.requests.Request())
        _save_encrypted_credentials(config, credentials)
    return credentials if credentials.valid else None


def handle_callback(config, query_params):
    settings = _settings()
    state = str(query_params.get("state", ""))
    if not _verify_oauth_state(settings, state):
        raise ValueError("Google OAuth state does not match")
    if query_params.get("error"):
        raise ValueError("Google authorization was not completed")
    code = query_params.get("code")
    if not code:
        raise ValueError("Google OAuth authorization code is missing")
    flow = _flow(settings)
    flow.fetch_token(code=code)
    if not flow.credentials.refresh_token:
        raise ValueError("Google did not provide a refresh token; revoke app access and reconnect")
    _save_encrypted_credentials(config, flow.credentials)


def authorization_url():
    settings = _settings()
    state = _make_oauth_state(settings)
    flow = _flow(settings, state=state)
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url


def _drive_service(config):
    credentials = _load_credentials(config)
    if credentials is None:
        raise ValueError("Google Drive is not connected")
    return googleapiclient.discovery.build("drive", "v3", credentials=credentials, cache_discovery=False)


def _setting(config, key):
    with storage.connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT value FROM prayer_app_settings WHERE key = %s", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None


def _set_setting(config, key, value):
    with storage.connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO prayer_app_settings (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value),
            )


def _folder_id(config, service):
    folder_id = _setting(config, "drive_folder_id")
    if folder_id:
        return folder_id
    response = service.files().list(
        q=f"name = '{FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        spaces="drive",
        fields="files(id,name)",
        pageSize=10,
    ).execute()
    folders = response.get("files", [])
    if folders:
        folder_id = folders[0]["id"]
    else:
        folder = service.files().create(
            body={"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
            fields="id",
        ).execute()
        folder_id = folder["id"]
    _set_setting(config, "drive_folder_id", folder_id)
    return folder_id


def upload_recording(config, session_id, role, uploaded_file):
    if role not in ("prayer", "teaching"):
        raise ValueError("Invalid recording role")
    if uploaded_file.size <= 0 or uploaded_file.size > MAX_RECORDING_BYTES:
        raise ValueError("Recording must be between 1 byte and 200 MiB")
    service = _drive_service(config)
    folder_id = _folder_id(config, service)
    filename = f"worship-{session_id}-{role}.wav"
    media = googleapiclient.http.MediaIoBaseUpload(
        io.BytesIO(uploaded_file.getvalue()),
        mimetype=uploaded_file.type or "audio/wav",
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )
    result = service.files().create(
        body={"name": filename, "parents": [folder_id]},
        media_body=media,
        fields="id,name,size,mimeType",
    ).execute()
    return result["id"]


def delete_recording(config, file_id):
    service = _drive_service(config)
    service.files().delete(fileId=file_id).execute()


def download_recording(config, file_id):
    service = _drive_service(config)
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = googleapiclient.http.MediaIoBaseDownload(buffer, request, chunksize=8 * 1024 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk()
        if buffer.tell() > MAX_RECORDING_BYTES:
            raise ValueError("Recording exceeds the 200 MiB playback limit")
    return buffer.getvalue()


def show_drive_connection(config):
    st.subheader("☁️ အသံဖိုင်အတွက် Google Drive")
    try:
        query = st.query_params
        if query.get("code") or query.get("error"):
            handle_callback(config, query)
            st.query_params.clear()
            st.success("Google Drive ချိတ်ဆက်ပြီးပါပြီ။")
            st.rerun()
        credentials = _load_credentials(config)
        if credentials:
            st.success("Google Drive ချိတ်ဆက်ထားပါသည်။ အသံဖိုင်များကို ချိတ်ထားသော Drive ထဲ သီးသန့်သိမ်းပါမည်။")
        else:
            url = authorization_url()
            st.link_button("Google Drive ချိတ်ဆက်ရန်", url)
            st.caption("Google account authorization လိုအပ်ပါသည်။ Client secret ကို chat သို့ မပို့ပါနှင့်။")
    except (KeyError, OSError, ValueError, psycopg.Error, googleapiclient.errors.HttpError):
        logger.exception("Could not connect Google Drive")
        st.error("Google Drive မချိတ်ဆက်နိုင်ပါ။ OAuth Secrets နှင့် connection ကို စစ်ဆေးပါ။")
