import hashlib
import hmac
import json
import logging
import threading
import time
from datetime import datetime, timezone

import psycopg
import streamlit as st

import storage

logger = logging.getLogger(__name__)
MAX_BACKUP_BYTES = 20 * 1024 * 1024
MAX_ATTEMPTS = 5
LOCK_SECONDS = 300


def validate_backup(data):
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Invalid backup version")
    for field in ("members", "custom_verses", "favorites"):
        if not isinstance(data.get(field), list):
            raise ValueError(f"Invalid {field}")
    for name in data["members"]:
        if not isinstance(name, str) or not name.strip() or len(name) > 190 or "\x00" in name:
            raise ValueError("Invalid member")
    for field in ("custom_verses", "favorites"):
        for item in data[field]:
            if not isinstance(item, dict):
                raise ValueError(f"Invalid {field} entry")
            book, text = item.get("book"), item.get("text")
            if not isinstance(book, str) or not book.strip() or len(book) > 190 or "\x00" in book:
                raise ValueError("Invalid book")
            if not isinstance(text, str) or not text.strip() or "\x00" in text:
                raise ValueError("Invalid verse text")
            for key in ("chapter", "verse"):
                if type(item.get(key)) is not int or not 1 <= item[key] <= 2147483647:
                    raise ValueError(f"Invalid {key}")
    return data


def create_backup(config):
    with storage.connection(config) as db:
        with db.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SELECT name FROM prayer_members ORDER BY name")
            members = [row["name"] for row in cursor.fetchall()]
            cursor.execute("SELECT book, chapter, verse, text FROM prayer_custom_verses ORDER BY book, chapter, verse")
            custom_verses = cursor.fetchall()
            cursor.execute("SELECT book, chapter, verse, text FROM prayer_favorites ORDER BY book, chapter, verse")
            favorites = cursor.fetchall()
    data = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "members": members,
        "custom_verses": custom_verses,
        "favorites": favorites,
    }
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def restore_backup(config, data):
    validate_backup(data)
    counts = {"members": 0, "custom_verses": 0, "favorites": 0}
    with storage.connection(config) as db:
        with db.cursor() as cursor:
            for name in data["members"]:
                cursor.execute(
                    "INSERT INTO prayer_members (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                    (name,),
                )
                counts["members"] += cursor.rowcount
            for field, table in (("custom_verses", "prayer_custom_verses"), ("favorites", "prayer_favorites")):
                for verse in data[field]:
                    storage.add_verse(cursor, table, verse)
                    counts[field] += cursor.rowcount
    return counts


@st.cache_resource
def login_guard():
    return {"lock": threading.Lock(), "failures": []}


def authenticate():
    password = st.session_state.pop("backup_password_input", "")
    configured = st.secrets.get("backup", {}).get("admin_password")
    guard = login_guard()
    with guard["lock"]:
        now = time.monotonic()
        guard["failures"] = [t for t in guard["failures"] if now - t < LOCK_SECONDS]
        if len(guard["failures"]) >= MAX_ATTEMPTS:
            st.session_state["backup_login_error"] = "ကြိုးစားမှုများလွန်းပါသည်။ ၅ မိနစ်ခန့် စောင့်ပြီး ပြန်ကြိုးစားပါ။"
        elif isinstance(configured, str) and hmac.compare_digest(password.encode("utf-8"), configured.encode("utf-8")):
            guard["failures"].clear()
            st.session_state["backup_auth"] = hashlib.sha256(configured.encode("utf-8")).hexdigest()
            st.session_state.pop("backup_login_error", None)
        else:
            guard["failures"].append(now)
            st.session_state["backup_login_error"] = "Admin password မမှန်ပါ။"


def show_backup_controls(config):
    st.divider()
    st.subheader("🔐 Database Backup & Restore")
    password = st.secrets.get("backup", {}).get("admin_password")
    if not isinstance(password, str) or len(password) < 16:
        st.error("Backup admin password ကို Streamlit Secrets တွင် အနည်းဆုံး ၁၆ လုံး သတ်မှတ်ပါ။")
        return
    expected = hashlib.sha256(password.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(st.session_state.get("backup_auth", ""), expected):
        st.session_state.pop("backup_data", None)
        with st.form("backup_login"):
            st.text_input("Admin password", type="password", key="backup_password_input")
            st.form_submit_button("ဝင်မည်", on_click=authenticate)
        if st.session_state.get("backup_login_error"):
            st.error(st.session_state["backup_login_error"])
        return

    st.caption("မိသားစုဝင်များ၊ ထည့်ထားသော ကျမ်းချက်များနှင့် အကြိုက်ဆုံးကျမ်းချက်များကို သိမ်းပါမည်။")
    if st.button("Backup ဖိုင် ပြင်ဆင်မည်"):
        try:
            data = create_backup(config)
            if len(data) > MAX_BACKUP_BYTES:
                st.session_state.pop("backup_data", None)
                st.error("Backup သည် 20 MB ထက်ကြီးနေပါသည်။ Database backup ကို provider မှတစ်ဆင့် ယူပါ။")
            else:
                st.session_state["backup_data"] = data
        except psycopg.Error:
            logger.exception("Could not create backup")
            st.error("Backup မပြုလုပ်နိုင်ပါ။ Database connection ကို စစ်ပါ။")
    if "backup_data" in st.session_state:
        st.download_button(
            "📥 Backup ဒေါင်းလုဒ်လုပ်မည်",
            st.session_state["backup_data"],
            file_name=f"prayer-backup-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-UTC.json",
            mime="application/json",
        )

    st.write("Restore လုပ်လျှင် လက်ရှိဒေတာကို မဖျက်ဘဲ backup မှ အသစ်များကို ပေါင်းထည့်ပါမည်။")
    uploaded = st.file_uploader("Backup JSON ဖိုင်ရွေးပါ", type="json", key="backup_upload")
    if uploaded is not None:
        if uploaded.size > MAX_BACKUP_BYTES:
            st.error("Backup ဖိုင်သည် 20 MB ထက် မကျော်ရပါ။")
        else:
            try:
                data = validate_backup(json.loads(uploaded.getvalue().decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
                st.error("Backup ဖိုင်ပုံစံ မမှန်ပါ။ ဤ app မှထုတ်ထားသော ဖိုင်ကို အသုံးပြုပါ။")
            else:
                st.caption(f"မိသားစုဝင် {len(data['members'])}၊ ကျမ်းချက် {len(data['custom_verses'])}၊ အကြိုက်ဆုံး {len(data['favorites'])}")
                confirm = st.checkbox("လက်ရှိဒေတာနှင့် ပေါင်းထည့်ရန် အတည်ပြုပါ")
                if st.button("📤 Restore လုပ်မည်", disabled=not confirm):
                    try:
                        counts = restore_backup(config, data)
                        st.session_state["save_msg"] = (
                            f"Restore ပြီးပါပြီ။ မိသားစုဝင် {counts['members']}၊ "
                            f"ကျမ်းချက် {counts['custom_verses']}၊ အကြိုက်ဆုံး {counts['favorites']} ခု အသစ်ထည့်ပြီးပါပြီ။"
                        )
                        st.session_state.pop("backup_data", None)
                        st.rerun()
                    except psycopg.Error:
                        logger.exception("Could not restore backup")
                        st.error("Restore မအောင်မြင်ပါ။ ဒေတာတစ်စိတ်တစ်ပိုင်းကို မသိမ်းပါ။")
    if st.button("Admin ထွက်မည်"):
        st.session_state.pop("backup_auth", None)
        st.session_state.pop("backup_data", None)
        st.rerun()
