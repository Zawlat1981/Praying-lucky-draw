import json
import logging
import random
import time
from pathlib import Path

import psycopg
import streamlit as st

import backup
import storage

logger = logging.getLogger(__name__)
st.set_page_config(page_title="မိသားစုဝတ်ပြုခြင်း", page_icon="🙏")


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
                    time.sleep(1.5)
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
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.warning("ဤကျမ်းချက်ကို သိမ်းထားပြီးဖြစ်ပါသည်။")
            except psycopg.Error:
                logger.exception("Could not save custom verse")
                st.error("ကျမ်းချက်ကို မသိမ်းနိုင်ပါ။")

all_verses = bible + custom_verses
st.subheader(f"📖 ကျမ်းချက်ရွေးချယ်ခြင်း (စုစုပေါင်း {len(all_verses)} ချက်)")
st.caption("မြန်မာကျမ်းစာ Judson 1840 နှင့် အသစ်ထည့်ထားသော ကျမ်းချက်များ")
if st.button("ယနေ့အတွက် ကျမ်းချက် ဘာလဲ? ကြည့်မယ် 🎲"):
    st.session_state["selected_verse"] = random.choice(all_verses)

if "selected_verse" in st.session_state:
    selected_verse = st.session_state["selected_verse"]
    show_verse(selected_verse)
    if st.button("⭐ ဤကျမ်းချက်ကို မှတ်ထားမည်", key="save_drawn"):
        try:
            if storage.save_verse(config, "prayer_favorites", selected_verse):
                st.session_state["save_msg"] = "⭐ အကြိုက်ဆုံးကျမ်းချက်ကို သိမ်းပြီးပါပြီ။"
                st.rerun()
            else:
                st.warning("ဤကျမ်းချက်ကို မှတ်ထားပြီးဖြစ်ပါသည်။")
        except psycopg.Error:
            logger.exception("Could not save favorite verse")
            st.error("ကျမ်းချက်ကို မသိမ်းနိုင်ပါ။")

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

if favorites:
    for favorite in favorites:
        show_verse(favorite)
else:
    st.write("မှတ်ထားသော ကျမ်းချက် မရှိသေးပါ။")

st.divider()
st.subheader("✨ တာဝန်ကျသူ ရွေးချယ်ခြင်း")
if st.button("ဘယ်သူတွေ တာဝန်ကျမလဲ ကြည့်မယ် ✨"):
    if len(family_members) >= 2:
        my_bar = st.progress(0, text="🎲 နာမည်များ ရွေးချယ်နေပါပြီ... (ခေတ္တ စောင့်ပါ)")
        for percent_complete in range(100):
            time.sleep(0.05)
            my_bar.progress(percent_complete + 1, text="🎲 နာမည်များ ရွေးချယ်နေပါပြီ... (ခေတ္တ စောင့်ပါ)")
        st.session_state["leader"], st.session_state["teacher"] = random.sample(family_members, 2)
        st.balloons()
    else:
        st.error("မိသားစုဝင် အနည်းဆုံး ၂ ယောက်ရှိမှ ရွေးလို့ရမှာပါဗျ။")

if "leader" in st.session_state and "teacher" in st.session_state:
    st.subheader("🙏 ခွန်အားကြီးသော ဆုတောင်းခြင်း ဦးဆောင်သူ")
    st.write(st.session_state["leader"])
    st.subheader("📖 ရှင်သန်လွတ်မြောက်ခြင်းသို့ ကျမ်းစာအားဖြင့် လမ်းပြသွန်သင်သူ")
    st.write(st.session_state["teacher"])

backup.show_backup_controls(config)
