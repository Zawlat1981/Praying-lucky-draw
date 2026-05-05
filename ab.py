import streamlit as st
import random
import pandas as pd
from datetime import datetime
import os
import time

# --- ၁။ Configurations & Setup ---
st.set_page_config(page_title="မိသားစုဝတ်ပြုခြင်း", page_icon="🙏", layout="centered")

family_members = ["Haysharya", "Haythuya", "Aung Zaw Latt"]
history_file = "prayer_teaching_history.csv"

# ကျမ်းစာဖိုင်ကို Cache လုပ်ပြီး ဖတ်ခြင်း
@st.cache_data
def get_full_bible():
    url = "https://raw.githubusercontent.com/daandrei/bible-myanmar-json/master/myanmar_bible.json"
    return pd.read_json(url)

# --- ၂။ UI Header ---
st.title("🙏 မိသားစုဝတ်ပြုခြင်း အစီအစဉ်")
st.write("✨ ဒီနေ့ည ဆုတောင်းခြင်းနဲ့ နှုတ်ကပတ်တော် သွန်သင်ခြင်းအတွက် ဘုရားသခင် ဘယ်သူ့ကိုတာဝန်ပေးမလဲ ✨")

# --- ၃။ ကျမ်းချက်ကံစမ်းခြင်း အပိုင်း ---
st.markdown("### 📖 ယနေ့အတွက် နှုတ်ကပတ်တော်")

if st.button("ဘုရားသခင် ဘယ်ကျမ်းချက်ကို ပေးမလဲကြည့်မယ် 🎲"):
    with st.spinner('ကျမ်းစာအုပ်ထဲမှာ ရှာဖွေနေပါတယ်...'):
        try:
            bible = get_full_bible()
            random_row = bible.sample(n=1).iloc[0]
            # Session state ထဲမှာ သိမ်းထားမှ တခြား button နှိပ်ရင် ပျောက်မသွားမှာပါ
            st.session_state['verse_ref'] = f"{random_row['book']} {random_row['chapter']}:{random_row['verse']}"
            st.session_state['verse_text'] = random_row['text']
        except Exception as e:
            st.error("ကျမ်းစာဖတ်လို့မရပါ (အင်တာနက်စစ်ဆေးပါ)")

# ကျမ်းချက်ရှိရင် ပြပေးမယ်
if 'verse_ref' in st.session_state:
    st.success(f"**{st.session_state['verse_ref']}**")
    st.info(st.session_state['verse_text'])

st.markdown("---")

# --- ၄။ တာဝန်ကျသူ ရွေးချယ်ခြင်း အပိုင်း ---
if st.button("တာဝန်ပေးခြင်းခံရသူများ ရွေးချယ်ပါမည် ✨", key="spin_button"):
    with st.spinner('🎲 နာမည်များ ရွေးချယ်နေပါပြီ...'):
        time.sleep(7) # ၁၀ စက္ကန့်က ကြာလွန်းလို့ ၂ စက္ကန့်ပဲ ထားပေးလိုက်ပါတယ်
        selected = random.sample(family_members, 2)
        st.session_state['prayer_leader'] = selected[0]
        st.session_state['teacher'] = selected[1]
    st.balloons()

# ရွေးချယ်ပြီးသားရှိရင် ပြပေးမယ်
if 'prayer_leader' in st.session_state:
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="🙏 ဆုတောင်းခြင်း ဦးဆောင်သူ", value=st.session_state['prayer_leader'])
    with col2:
        st.metric(label="📖 တရားဟောပြော/သွန်သင်သူ", value=st.session_state['teacher'])

    st.markdown("---")
    
    # --- ၅။ မှတ်တမ်းသွင်းခြင်း Form ---
    with st.form("record_form"):
        st.write("📝 **ဝတ်ပြုခြင်း မှတ်တမ်းသွင်းရန်**")
        
        # ကျမ်းချက်ရှိရင် အလိုအလျောက် ခေါင်းစဉ်ထဲ ထည့်ပေးထားမယ်
        default_topic = st.session_state.get('verse_ref', "")
        topic = st.text_input("သွန်သင်ချက်/ဆုတောင်းချက် ခေါင်းစဉ်:", value=default_topic)
        
        submitted = st.form_submit_button("မှတ်တမ်းသိမ်းမည် ✅")
        
        if submitted and topic:
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_data = {
                "ရက်စွဲ": [current_date],
                "ဆုတောင်းခြင်းဦးဆောင်သူ": [st.session_state['prayer_leader']],
                "တရားဟောပြောသူ": [st.session_state['teacher']],
                "အကြောင်းအရာ": [topic]
            }
            df = pd.DataFrame(new_data)
            
            if not os.path.isfile(history_file):
                df.to_csv(history_file, index=False, encoding='utf-8')
            else:
                df.to_csv(history_file, mode='a', index=False, header=False, encoding='utf-8')
            st.success(f"✅ မှတ်တမ်း သိမ်းဆည်းပြီးပါပြီ။")

# --- ၆။ မှတ်တမ်းဟောင်းများ ပြသခြင်း ---
st.markdown("---")
st.subheader("📜 ဝတ်ပြုခြင်း မှတ်တမ်းဟောင်းများ")
if os.path.isfile(history_file):
    history_df = pd.read_csv(history_file)
    st.dataframe(history_df.sort_values(by="ရက်စွဲ", ascending=False), use_container_width=True)
else:
    st.write("မှတ်တမ်း မရှိသေးပါ။")
