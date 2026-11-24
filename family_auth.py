import hmac
import threading
import time

import streamlit as st

MAX_ATTEMPTS = 5
LOCK_SECONDS = 300


@st.cache_resource
def login_guard():
    return {"lock": threading.Lock(), "failures": []}


def authenticate():
    password = st.session_state.pop("family_password_input", "")
    configured = st.secrets.get("family", {}).get("password")
    guard = login_guard()
    with guard["lock"]:
        now = time.monotonic()
        guard["failures"] = [timestamp for timestamp in guard["failures"] if now - timestamp < LOCK_SECONDS]
        if len(guard["failures"]) >= MAX_ATTEMPTS:
            st.session_state["family_login_error"] = "ကြိုးစားမှုများလွန်းပါသည်။ ၅ မိနစ်ခန့်စောင့်ပြီး ပြန်ကြိုးစားပါ။"
        elif isinstance(configured, str) and len(configured) >= 16 and hmac.compare_digest(
            password.encode("utf-8"), configured.encode("utf-8")
        ):
            guard["failures"].clear()
            st.session_state["family_authenticated"] = True
            st.session_state.pop("family_login_error", None)
        else:
            guard["failures"].append(now)
            st.session_state["family_login_error"] = "Family password မမှန်ပါ။"


def require_family_password():
    password = st.secrets.get("family", {}).get("password")
    if not isinstance(password, str) or len(password) < 16:
        st.error("Streamlit Secrets ၏ [family] အောက်တွင် အနည်းဆုံး ၁၆ လုံးရှိသော password သတ်မှတ်ပါ။")
        st.code('[family]\npassword = "သီးခြား family password အနည်းဆုံး ၁၆ လုံး"')
        st.stop()
    if not st.session_state.get("family_authenticated"):
        st.title("🙏 မိသားစုဝတ်ပြုခြင်း")
        st.text_input("Family password", type="password", key="family_password_input")
        st.button("ဝင်မည်", key="family_login_submit", on_click=authenticate)
        if st.session_state.get("family_login_error"):
            st.error(st.session_state["family_login_error"])
        if not st.session_state.get("family_authenticated"):
            st.stop()
