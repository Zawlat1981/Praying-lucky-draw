import json
import logging
import random
from pathlib import Path

import googleapiclient.errors
import psycopg
import streamlit as st

import backup
import drive_storage
import family_auth
import storage
import teaching

logger = logging.getLogger(__name__)
st.set_page_config(page_title="မိသားစုဝတ်ပြုခြင်း", page_icon="🙏")
family_auth.require_family_password()


@st.cache_data
def load_bible():
    path = Path(__file__).resolve().parent / "my_judson.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        {"book": item["book_name"], "chapter": item["chapter"], "verse": item["verse"], "text": item["text"]}
        for item in data["verses"]
    ]


def show_verse(verse):
    st.success(f"**{verse['book']} {verse['chapter']}:{verse['verse']}**")
    st.info(verse["text"])


try:
    config = st.secrets["postgresql"]
    storage.initialize(config)
    family_members = storage.list_members(config)
    custom_verses = storage.list_verses(config, "prayer_custom_verses")
    favorites = storage.list_verses(config, "prayer_favorites")
    bible = load_bible()
except (KeyError, OSError, ValueError, psycopg.Error):
    logger.exception("Could not initialize the prayer app")
    st.error("ဒေတာကို မဖတ်နိုင်ပါ။ PostgreSQL secrets၊ database connection နှင့် ကျမ်းစာဖိုင်ကို စစ်ဆေးပါ။")
    st.stop()

st.markdown("<h2 style='text-align: center; font-size: 28px;'>🙏 မိသားစုဝတ်ပြုခြင်းအစီအစဉ်</h2>", unsafe_allow_html=True)
if st.button("ထွက်မည်", key="family_logout"):
    st.session_state.clear()
    st.rerun()

if "save_msg" in st.session_state:
    st.success(st.session_state.pop("save_msg"))

with st.sidebar:
    st.header("⚙ အသစ်ထည့်ရန်")
    st.subheader("👥 မိသားစုဝင် အသစ်တိုးခြင်း")
    new_member = st.text_input("နာမည်အသစ်", key="family_member_input")
    if st.button("မိသားစုဝင်စာရင်းထဲသို့ ထည့်မည်"):
        name = new_member.strip()
        if not name:
            st.error("❌ နာမည် ထည့်ပါ!")
        elif len(name) > 190:
            st.error("နာမည်သည် စာလုံး ၁၉၀ ထက် မကျော်ရပါ။")
        else:
            try:
                if storage.save_member(config, name):
                    st.session_state["save_msg"] = f"✅ {name} ကို ထည့်ပြီးပါပြီ။"
                    st.toast(st.session_state["save_msg"], icon="👥")
                    st.balloons()
                    st.rerun()
                else:
                    st.warning(f"⚠️ {name} က စာရင်းထဲမှာ ရှိနေပြီးသားပါ!")
            except psycopg.Error:
                logger.exception("Could not save family member")
                st.error("မိသားစုဝင်ကို မသိမ်းနိုင်ပါ။")

    st.divider()
    st.subheader("📖 ကျမ်းချက်အသစ်ထည့်ခြင်း")
    new_book = st.text_input("ကျမ်းအမည်", key="bible_book")
    new_chap = st.number_input("အခန်းကြီး", min_value=1, step=1, key="bible_chap")
    new_verse = st.number_input("အခန်းငယ်", min_value=1, step=1, key="bible_verse")
    new_text = st.text_area("ကျမ်းစာသား", key="bible_text")
    if st.button("ကျမ်းစာဖိုင်ထဲသို့ သိမ်းမည်"):
        book, text = new_book.strip(), new_text.strip()
        if not book or not text:
            st.warning("⚠️ ကျမ်းအမည် နှင့် ကျမ်းစာသား ထည့်ပါ!")
        elif len(book) > 190:
            st.warning("ကျမ်းအမည်သည် စာလုံး ၁၉၀ ထက် မကျော်ရပါ။")
        else:
            entry = {"book": book, "chapter": int(new_chap), "verse": int(new_verse), "text": text}
            try:
                if storage.save_verse(config, "prayer_custom_verses", entry):
                    st.session_state["save_msg"] = "✅ ကျမ်းချက်အသစ်ကို သိမ်းပြီးပါပြီ။"
                    st.toast(st.session_state["save_msg"], icon="📖")
                    st.balloons()
                    st.rerun()
                else:
                    st.warning("ဤကျမ်းချက်ကို သိမ်းထားပြီးဖြစ်ပါသည်။")
            except psycopg.Error:
                logger.exception("Could not save custom verse")
                st.error("ကျမ်းချက်ကို မသိမ်းနိုင်ပါ။")

all_verses = bible + custom_verses
st.subheader(f"📖 ကျမ်းချက်ရွေးချယ်ခြင်း (စုစုပေါင်း {len(all_verses)} ချက်)")
st.caption("မြန်မာကျမ်းစာ Judson 1840 နှင့် အသစ်ထည့်ထားသော ကျမ်းချက်များ")

st.subheader("✨ ယနေ့ဝတ်ပြုမှုအတွက် ရွေးချယ်ခြင်း")
if len(family_members) < 2:
    st.warning("တာဝန်ကျသူရွေးရန် မိသားစုဝင် အနည်းဆုံး ၂ ယောက် ထည့်ပါ။")
elif st.button("ကျမ်းချက်နှင့် တာဝန်ကျသူများ ကံစမ်းရွေးမည် 🎲"):
    selected_verse = random.choice(all_verses)
    leader, teacher_person = random.sample(family_members, 2)
    outline = teaching.make_outline(selected_verse)
    try:
        session_id = storage.save_worship_session(config, selected_verse, leader, teacher_person, outline)
        st.session_state["current_session_id"] = session_id
        st.session_state["save_msg"] = "ဝတ်ပြုမှုရွေးချယ်မှုကို History ထဲ သိမ်းပြီးပါပြီ။"
        st.balloons()
        st.rerun()
    except psycopg.Error:
        logger.exception("Could not save worship session")
        st.error("ရွေးချယ်မှုကို History ထဲ မသိမ်းနိုင်ပါ။ Database connection ကို စစ်ပါ။")

current_session_id = st.session_state.get("current_session_id")
if current_session_id:
    try:
        current = next(
            (item for item in storage.list_worship_sessions(config, limit=100) if str(item["id"]) == current_session_id),
            None,
        )
    except psycopg.Error:
        logger.exception("Could not load current worship session")
        current = None
    if current:
        st.markdown("### 🙏 ဝတ်ပြုမှုအစီအစဉ်")
        show_verse(current["verse"])
        st.markdown(f"**ဆုတောင်းဦးဆောင်သူ:** {current['leader']}")
        st.markdown(f"**ကျမ်းစာအားဖြင့် လမ်းပြသွန်သင်သူ:** {current['teacher']}")
        st.markdown(f"#### {current['teaching']['title']}")
        st.write(current["teaching"]["theme"])
        st.write(current["teaching"]["reading"])
        for index, point in enumerate(current["teaching"]["outline"], 1):
            st.write(f"{index}. {point}")
        st.write(f"**ဆွေးနွေးရန်:** {current['teaching']['discussion']}")
        st.write(f"**လက်တွေ့ကျင့်သုံးရန်:** {current['teaching']['application']}")
        st.write(f"**ဆုတောင်းရန်:** {current['teaching']['prayer']}")
        st.caption(current["teaching"]["source_note"])

with st.sidebar:
    st.divider()
    st.subheader("⭐ အကြိုက်ဆုံးကျမ်းချက်များ")
    with st.expander("ကျမ်းချက်ကို ရှာပြီး မှတ်ထားရန်"):
        books = list(dict.fromkeys(item["book"] for item in all_verses))
        book = st.selectbox("ကျမ်းအမည်", books)
        chapters = sorted({item["chapter"] for item in all_verses if item["book"] == book})
        chapter = st.selectbox("အခန်းကြီး", chapters)
        matches = [item for item in all_verses if item["book"] == book and item["chapter"] == chapter]
        chosen = st.selectbox(
            "အခန်းငယ်",
            range(len(matches)),
            format_func=lambda index: f"{matches[index]['verse']} — {matches[index]['text'][:80]}",
        )
        show_verse(matches[chosen])
        if st.button("⭐ ရွေးထားသောကျမ်းချက်ကို မှတ်ထားမည်"):
            try:
                if storage.save_verse(config, "prayer_favorites", matches[chosen]):
                    st.session_state["save_msg"] = "⭐ အကြိုက်ဆုံးကျမ်းချက်ကို သိမ်းပြီးပါပြီ။"
                    st.rerun()
                else:
                    st.warning("ဤကျမ်းချက်ကို မှတ်ထားပြီးဖြစ်ပါသည်။")
            except psycopg.Error:
                logger.exception("Could not save favorite verse")
                st.error("ကျမ်းချက်ကို မသိမ်းနိုင်ပါ။")

    for favorite in favorites:
        with st.expander(f"⭐ {favorite['book']} {favorite['chapter']}:{favorite['verse']}"):
            show_verse(favorite)
    if not favorites:
        st.write("မှတ်ထားသော ကျမ်းချက် မရှိသေးပါ။")

    st.divider()
    st.subheader("🕰️ ဝတ်ပြုမှု History")
    try:
        history_count = storage.count_worship_sessions(config)
        page_size = 20
        page_count = (history_count + page_size - 1) // page_size
        page = min(st.session_state.get("history_page", 0), max(page_count - 1, 0))
        st.session_state["history_page"] = page
        previous, page_label, following = st.columns([1, 2, 1])
        if previous.button("← ရှေ့", disabled=page <= 0):
            st.session_state["history_page"] -= 1
            st.rerun()
        page_label.caption(f"{page + 1 if page_count else 0} / {page_count} · စုစုပေါင်း {history_count}")
        if following.button("နောက် →", disabled=page + 1 >= page_count):
            st.session_state["history_page"] += 1
            st.rerun()
        records = storage.list_worship_sessions(config, limit=page_size, offset=page * page_size)
    except psycopg.Error:
        logger.exception("Could not load worship history")
        records = []
        st.error("History ဖတ်မရပါ။ Database connection ကို စစ်ပါ။")

    if records:
        options = {str(item["id"]): item for item in records}
        chosen_id = st.selectbox(
            "ပြန်ကြည့်ရန် ဝတ်ပြုမှုရွေးပါ",
            list(options),
            format_func=lambda session_id: (
                f"{options[session_id]['created_at'].astimezone().strftime('%Y-%m-%d %H:%M')} · "
                f"{options[session_id]['verse']['book']} {options[session_id]['verse']['chapter']}:"
                f"{options[session_id]['verse']['verse']} · {options[session_id]['leader']} / "
                f"{options[session_id]['teacher']}"
            ),
        )
        selected = options[chosen_id]
        show_verse(selected["verse"])
        st.markdown(f"**ဆုတောင်းဦးဆောင်သူ:** {selected['leader']}")
        st.markdown(f"**ကျမ်းစာအားဖြင့် လမ်းပြသွန်သင်သူ:** {selected['teacher']}")
        st.markdown(f"#### {selected['teaching']['title']}")
        st.write(selected["teaching"]["theme"])
        for index, point in enumerate(selected["teaching"]["outline"], 1):
            st.write(f"{index}. {point}")
        st.write(f"**ဆွေးနွေးရန်:** {selected['teaching']['discussion']}")
        st.write(f"**လက်တွေ့ကျင့်သုံးရန်:** {selected['teaching']['application']}")
        st.caption(selected["teaching"]["source_note"])

        with st.expander("🎙️ ရွေးချယ်ပါက အသံဖမ်းပြီး Google Drive တွင် သိမ်းရန်"):
            drive_storage.show_drive_connection(config)
            audio_jobs = (
                ("prayer", "ဆုတောင်းဦးဆောင်သူ၏ အသံ", selected["prayer_audio_file_id"]),
                ("teaching", "သွန်သင်သူ၏ အသံ", selected["teaching_audio_file_id"]),
            )
            for role, label, file_id in audio_jobs:
                st.markdown(f"**{label}**")
                audio = None
                try:
                    audio = st.audio_input("Record ကိုနှိပ်မှ အသံဖမ်းမည်", key=f"audio_{role}_{chosen_id}")
                except (OSError, RuntimeError):
                    logger.exception("Audio recording widget is unavailable")
                    st.error("ဤ browser တွင် အသံဖမ်းမရပါ။ Microphone ခွင့်ပြုချက်နှင့် browser ကို စစ်ပါ။")
                if audio is not None:
                    if audio.size > drive_storage.MAX_RECORDING_BYTES:
                        st.error("ဖိုင်အရွယ်အစားသည် 200 MiB ထက် ကျော်နေပါသည်။")
                    elif st.button(f"☁️ {label} ကို Drive ထဲသိမ်းမည်", key=f"upload_{role}_{chosen_id}"):
                        uploaded_id = None
                        try:
                            uploaded_id = drive_storage.upload_recording(config, chosen_id, role, audio)
                            if not storage.save_session_audio(config, chosen_id, role, uploaded_id):
                                raise ValueError("Worship history record no longer exists")
                            st.success("အသံဖိုင်ကို Google Drive တွင် သိမ်းပြီးပါပြီ။")
                            st.rerun()
                        except (KeyError, OSError, ValueError, psycopg.Error, googleapiclient.errors.HttpError):
                            logger.exception("Could not save worship recording")
                            if uploaded_id:
                                try:
                                    drive_storage.delete_recording(config, uploaded_id)
                                except (OSError, ValueError, psycopg.Error, googleapiclient.errors.HttpError):
                                    logger.exception("Could not remove orphaned Drive recording")
                            st.error("အသံဖိုင်ကို မသိမ်းနိုင်ပါ။ Drive connection နှင့် network ကို စစ်ပါ။")
                if file_id:
                    if st.button(f"▶️ {label} ဖွင့်မည်", key=f"play_{role}_{chosen_id}"):
                        try:
                            st.session_state[f"play_audio_{role}_{chosen_id}"] = drive_storage.download_recording(config, file_id)
                        except (KeyError, OSError, ValueError, psycopg.Error, googleapiclient.errors.HttpError):
                            logger.exception("Could not load worship recording")
                            st.error("အသံဖိုင်ကို ဖွင့်မရပါ။ Drive connection ကို စစ်ပါ။")
                    if f"play_audio_{role}_{chosen_id}" in st.session_state:
                        st.audio(st.session_state[f"play_audio_{role}_{chosen_id}"], format="audio/wav")
            st.caption("စတင်/ရပ်ရန်ကို ကိုယ်တိုင်နှိပ်ပါ။ Browser, network နှင့် upload အရွယ်အစားကန့်သတ်ချက်များ ရှိနိုင်ပါသည်။")

with st.sidebar:
    st.divider()
    backup.show_backup_controls(config)
