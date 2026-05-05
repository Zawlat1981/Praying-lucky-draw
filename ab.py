import streamlit as st
import random
import pandas as pd
from datetime import datetime
import os
import json
import time

# --- ၁။ Setup နှင့် Data သိမ်းဆည်းမည့်ဖိုင်များ ---
BIBLE_FILE = 'bible.json'
FAMILY_FILE = 'family.json'

# ကျမ်းစာဖိုင် ဖတ်ရန်/သိမ်းရန်
def load_bible():
    if os.path.exists(BIBLE_FILE):
        with open(BIBLE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if data else []
    return [{"book": "ယောဟန်", "chapter": 3, "verse": 16, "text": "ဘုရားသခင်သည် လောကီသားတို့ကို ချစ်တော်မူ၏။"}]

# မိသားစုဝင်ဖိုင် ဖတ်ရန်/သိမ်းရန်
def load_family():
    if os.path.exists(FAMILY_FILE):
        with open(FAMILY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return ["Haysharya", "Haythuya", "Aung Zaw Latt"]

bible_list = load_bible()
family_members = load_family()

# --- ၂။ App UI Configuration ---
st.set_page_config(page_title="မိသားစုဝတ်ပြုခြင်း", page_icon="🙏")

# ခေါင်းစဉ်ကို ဖုန်းမှာကြည့်ရ အဆင်ပြေအောင် အရွယ်အစား ချိန်ညှိခြင်း
st.markdown("<h2 style='text-align: center; font-size: 28px;'>🙏 မိသားစုဝတ်ပြုခြင်းအစီအစဉ်</h2>", unsafe_allow_html=True)

# --- ၃။ Sidebar (ကျမ်းချက်နှင့် မိသားစုဝင် အသစ်တိုးရန်) ---
with st.sidebar:
    st.header("⚙️ အသစ်ထည့်ရန်")
    
    # မိသားစုဝင်တိုးရန်
    st.subheader("👥 မိသားစုဝင် အသစ်တိုးခြင်း")
    new_member = st.text_input("နာမည်အသစ်")
    if st.button("မိသားစုဝင်စာရင်းထဲသို့ ထည့်မည်"):
        if new_member and new_member not in family_members:
            family_members.append(new_member)
            with open(FAMILY_FILE, 'w', encoding='utf-8') as f:
                json.dump(family_members, f, ensure_ascii=False, indent=4)
            st.success(f"✅ {new_member} ကို ထည့်ပြီးပါပြီ။")
            st.rerun()

    st.divider()
    
    # ကျမ်းချက်တိုးရန်
    st.subheader("📖 ကျမ်းချက်အသစ်ထည့်ခြင်း")
    new_book = st.text_input("ကျမ်းအမည်")
    new_chap = st.number_input("အခန်းကြီး", min_value=1, step=1)
    new_verse = st.number_input("အခန်းငယ်", min_value=1, step=1)
    new_text = st.text_area("ကျမ်းစာသား")
    if st.button("ကျမ်းစာဖိုင်ထဲသို့ သိမ်းမည်"):
        if new_book and new_text:
            new_entry = {"book": new_book, "chapter": int(new_chap), "verse": int(new_verse), "text": new_text}
            bible_list.append(new_entry)
            with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
                json.dump(bible_list, f, ensure_ascii=False, indent=4)
            st.success("✅ ကျမ်းချက်အသစ်ကို သိမ်းပြီးပါပြီ။")
            st.rerun()

# --- ၄။ ကျမ်းချက်ကံစမ်းခြင်း ---
st.subheader(f"📖 ကျမ်းချက်ကံစမ်းခြင်း (စုစုပေါင်း {len(bible_list)} ချက်)")
if st.button("ယနေ့အတွက် ကျမ်းချက် ဘာလဲ? ကြည့်မယ် 🎲"):
    res = random.choice(bible_list)
    st.session_state['v_ref'] = f"{res['book']} {res['chapter']}:{res['verse']}"
    st.session_state['v_text'] = res['text']

if 'v_ref' in st.session_state:
    st.success(f"**{st.session_state['v_ref']}**")
    st.info(st.session_state['v_text'])

st.divider()

# --- ၅။ တာဝန်ကျသူ ရွေးချယ်ခြင်း (၇ စက္ကန့် စောင့်ဆိုင်းချိန်) ---
st.subheader("✨ တာဝန်ကျသူ ရွေးချယ်ခြင်း")
if st.button("ဘယ်သူတွေ တာဝန်ကျမလဲ ကြည့်မယ် ✨"):
    if len(family_members) >= 2:
        progress_text = "🎲 နာမည်များ ရွေးချယ်နေပါပြီ... (၇ စက္ကန့် စောင့်ပါ)"
        my_bar = st.progress(0, text=progress_text)
        
        # ၇ စက္ကန့် စောင့်ရန် (Loading bar ပြပေးခြင်း)
        for percent_complete in range(100):
            time.sleep(0.07) # 0.07 * 100 = 7 seconds
            my_bar.progress(percent_complete + 1, text=progress_text)
        
        selected = random.sample(family_members, 2)
        st.session_state['leader'] = selected[0]
        st.session_state['teacher'] = selected[1]
        st.balloons()
    else:
        st.error("မိသားစုဝင် အနည်းဆုံး ၂ ယောက်ရှိမှ ရွေးလို့ရမှာပါဗျ။")

# ရလဒ်များကို ပြသခြင်း
if 'leader' in st.session_state and 'teacher' in st.session_state:
    st.markdown(f"### 🎤 ဦးဆောင်သူ: **{st.session_state['leader']}**")
    st.markdown(f"### 📖 ကျမ်းစာဝေငှသူ: **{st.session_state['teacher']}**")
