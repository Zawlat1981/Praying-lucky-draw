import streamlit as st
import random
import pandas as pd
from datetime import datetime
import os
import time  # အချိန်ဆိုင်းဖို့အတွက် ထည့်ရပါတယ်

# ၁။ မိသားစုဝင်များ စာရင်း
family_members = ["Haysharya", "Haythuya", "Aung Zaw Latt"]
history_file = "prayer_teaching_history.csv"

# Page Configuration (စာမျက်နှာကို ကျယ်ကျယ်လေးဖြစ်အောင်လုပ်တာပါ)
st.set_page_config(page_title="မိသားစုဝတ်ပြုခြင်း", page_icon="🙏", layout="centered")

st.title("🙏 မိသားစုဝတ်ပြုခြင်း အစီအစဉ်")
st.write("✨ ဒီနေ့ည ဆုတောင်းခြင်းနဲ့ နှုတ်ကပတ်တော် သွန်သင်ခြင်းအတွက် ဘုရားသခင် ဘယ်သူ့ကိုတာဝန်ပေးမလဲ ✨")

# ၂။ ကံစမ်းမဲနှိုက်ရန် ခလုတ်
if st.button("တာဝန်ပေးခြင်းခံရသူများ ရွေးချယ်ပါမည် ✨", key="spin_button", help="နှိပ်လိုက်ရင် နာမည်တွေ လည်ပါလိမ့်မယ်"):
    # --- ရုပ်ထွက် အားကောင်းအောင် လုပ်တဲ့အပိုင်း ---
    with st.spinner('🎲 နာမည်များ ကိုစတင်ရွေးချယ်နေပါပြီ... အချိန်ပြည့်ဖို့ စောင့်နေပါတယ်...'):
        # ၃ စက္ကန့်လောက် နာမည်တွေ လည်နေတဲ့ ပုံစံမျိုးလုပ်ဖို့ ဆိုင်းထားတာပါ
        time.sleep(10) 

        # တကယ့် ရွေးချယ်မှုလုပ်တာပါ
        selected = random.sample(family_members, 2)
        st.session_state['prayer_leader'] = selected[0]
        st.session_state['teacher'] = selected[1]
    
    # ရလဒ်ထွက်လာတဲ့အခါမှာ Balloons ပျံခိုင်းတာပါ
    st.balloons()
    st.success("🎲 ကံစမ်းမဲ နှိုက်ခြင်း ပြီးဆုံးပါပြီ!")

# ၃။ ရွေးချယ်ခံရသူများကို လှလှပပ ပြသခြင်း
if 'prayer_leader' in st.session_state:
    st.markdown("---")
    st.subheader("🎉 ဒီနေ့ညအတွက် တာဝန်ကျသူများ")
    
    # Columns ၂ ခု ခွဲပြီး ပြတာပါ
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(label="🙏 ဆုတောင်းခြင်း ဦးဆောင်သူ", value=st.session_state['prayer_leader'])
        st.info(f"**{st.session_state['prayer_leader']}** က ဆုတောင်းပေးရပါမယ်။")

    with col2:
        st.metric(label="📖 တရားဟောပြော/သွန်သင်သူ", value=st.session_state['teacher'])
        st.warning(f"**{st.session_state['teacher']}** က တရားဟော/သွန်သင်ပေးရပါမယ်။")

    st.markdown("---")
    # ၄။ အကြောင်းအရာ မှတ်တမ်းတင်ခြင်း
    with st.form("record_form"):
        st.write("📝 **ဝတ်ပြုခြင်း မှတ်တမ်းသွင်းရန်**")
        topic = st.text_input("ဒီနေ့ညရဲ့ သွန်သင်ချက်/ဆုတောင်းချက် ခေါင်းစဉ် (ဥပမာ- ကျန်းမာရေး၊ ဖိလိပ္ပိ ၄:၁၃):")
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
            
            # File ထဲသို့ သိမ်းခြင်း
            if not os.path.isfile(history_file):
                df.to_csv(history_file, index=False, encoding='utf-8')
            else:
                df.to_csv(history_file, mode='a', index=False, header=False, encoding='utf-8')
            st.success(f"✅ {current_date} အတွက် မှတ်တမ်း သိမ်းဆည်းပြီးပါပြီ။")

# ၅။ မှတ်တမ်းဟောင်းများကို ပြသခြင်း (အောက်နားမှာ Table နဲ့ပြတာပါ)
st.markdown("---")
st.subheader("📜 ဝတ်ပြုခြင်း မှတ်တမ်းဟောင်းများ")
if os.path.isfile(history_file):
    history_df = pd.read_csv(history_file)
    # ဇယားကို ပိုဖတ်ရလွယ်အောင် Date အလိုက် နောက်ဆုံးကနေ အရင်ပြတာပါ
    st.dataframe(history_df.sort_values(by="ရက်စွဲ", ascending=False), use_container_width=True)
else:
    st.write("မှတ်တမ်း မရှိသေးပါခင်ဗျာ။")
