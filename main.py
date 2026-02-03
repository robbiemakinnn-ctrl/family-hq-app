import streamlit as st
import pandas as pd
import time
import datetime
from streamlit_gsheets import GSheetsConnection

# --- 🎨 CONFIG ---
st.set_page_config(page_title="Family HQ", page_icon="🏠", layout="centered")

st.markdown("""
    <style>
    .stButton button {
        height: 70px;
        width: 100%;
        font-size: 20px !important;
        font-weight: 600 !important;
        border-radius: 12px !important;
        margin-bottom: 8px;
    }
    header {visibility: hidden;}
    .stProgress > div > div > div > div {
        background-color: #ffd700;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 💾 DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    # Force reload data (ttl=0) to ensure we see updates immediately
    df_bal = conn.read(worksheet="Sheet1", usecols=[0,1,2,3,4], ttl=0)
    # Handle potential empty history
    try:
        df_hist = conn.read(worksheet="History", ttl=0)
    except:
        df_hist = pd.DataFrame(columns=["Date", "User", "Msg", "Val"])
    return df_bal, df_hist

def save_data(df_bal, df_hist):
    conn.update(worksheet="Sheet1", data=df_bal)
    conn.update(worksheet="History", data=df_hist)
    st.cache_data.clear()

# --- 📅 LOGIC ---
def get_week_info():
    start_date = datetime.date(2026, 2, 2)
    today = datetime.date.today()
    days_passed = (today - start_date).days
    week_num = 1 + (days_passed // 7)
    is_even = (week_num % 2 == 0)
    return week_num, ("Lauren" if is_even else "Rob"), ("Noah" if is_even else "Eva")

def process_transaction(user, action, value, is_vault=False, is_fine=False):
    df_bal, df_hist = get_data()
    
    # Locate User Row
    idx = df_bal[df_bal['User'] == user].index[0]
    pot_idx = df_bal[df_bal['User'] == 'House_Pot'].index[0]

    msg = ""
    
    if is_vault:
        if df_bal.at[idx, 'Balance'] >= value:
            df_bal.at[idx, 'Balance'] -= value
            df_bal.at[idx, 'Vault'] += value
            msg = f"{user}: Saved to Vault"
        else:
            st.error("Not enough cash!")
            return
    elif is_fine:
        df_bal.at[idx, 'Balance'] -= abs(value)
        df_bal.at[pot_idx, 'Balance'] += abs(value)
        msg = f"{user}: Fined £{abs(value)}"
    else:
        df_bal.at[idx, 'Balance'] += value
        if value > 0: # Add XP
            df_bal.at[idx, 'XP'] += value
        msg = f"{user}: {action}"

    # Add to History (Top of list)
    new_row = pd.DataFrame([{
        "Date": datetime.datetime.now().strftime("%d/%m %H:%M"),
        "User": user, "Msg": msg, "Val": value
    }])
    df_hist = pd.concat([new_row, df_hist], ignore_index=True)

    save_data(df_bal, df_hist)
    
    if value > 0: st.toast(f"✅ Earned £{value}!"); st.balloons()
    elif value < 0: st.toast(f"🔻 Spent £{abs(value)}")
    time.sleep(1)
    st.rerun()

# --- 🖥️ INTERFACE ---
try:
    df_bal, df_hist = get_data()
except Exception as e:
    st.error("⚠️ Database connecting... please refresh in 10s.")
    st.stop()

week_num, parent_turn, kid_turn = get_week_info()
house_pot = df_bal.loc[df_bal['User'] == 'House_Pot', 'Balance'].values[0]

tab1, tab2, tab3 = st.tabs(["📱 Remote", "🏆 Vault", "📊 Stats"])

with tab1:
    c1, c2, c3 = st.columns([2, 1, 1])
    c1.metric("🍯 Pot", f"£{house_pot}")
    c2.info(f"📅 Wk {week_num}")
    c3.warning(f"Turn: {parent_turn[:3]} / {kid_turn[:3]}")
    st.divider()

    if "selected_user" not in st.session_state: st.session_state.selected_user = "Rob"
    col_r, col_l, col_e, col_n = st.columns(4)
    def set_u(n): st.session_state.selected_user = n
    
    if col_r.button("🔴\nRob", type="primary" if st.session_state.selected_user=="Rob" else "secondary"): set_u("Rob")
    if col_l.button("🟣\nLoz", type="primary" if st.session_state.selected_user=="Lauren" else "secondary"): set_u("Lauren")
    if col_e.button("🔵\nEva", type="primary" if st.session_state.selected_user=="Eva" else "secondary"): set_u("Eva")
    if col_n.button("🟢\nNoah", type="primary" if st.session_state.selected_user=="Noah" else "secondary"): set_u("Noah")

    curr = st.session_state.selected_user
    u_data = df_bal[df_bal['User'] == curr].iloc[0]
    
    st.subheader(f"{curr}'s Dashboard")
    c_wal, c_xp = st.columns(2)
    c_wal.metric("💵 Wallet", f"£{u_data['Balance']}")
    c_xp.metric("⭐ XP", f"{u_data['XP']}")

    if curr in ["Rob", "Lauren"]:
        c_main, c_side = st.columns([2, 1])
        with c_main:
            if curr == parent_turn:
                if st.button("🍳 Kitchen (+£2)"): process_transaction(curr, "Kitchen", 2)
                if st.button("🛁 Bathroom (+£1)"): process_transaction(curr, "Bathroom", 1)
            else: st.info("Not your week!")
        with c_side:
            if st.button("🍕 Pot\n£5"):
                if house_pot >= 5:
                    idx = df_bal[df_bal['User'] == 'House_Pot'].index[0]
                    df_bal.at[idx, 'Balance'] -= 5
                    save_data(df_bal, df_hist)
                    st.rerun()
    elif curr in ["Eva", "Noah"]:
        if st.button("🛏️ Bedroom (XP)"): process_transaction(curr, "Bedroom", 0)
        if curr == kid_turn:
            if st.button("📺 Living Room (+£2)"): process_transaction(curr, "Living Room", 2)
        else: st.caption("Living Room Locked")
        st.divider()
        c_pay, c_fine = st.columns(2)
        with c_pay: 
            if st.button("💸 Pay £5"): 
                if u_data['Balance'] >= 5: process_transaction(curr, "Paid Cash", -5)
        with c_fine:
            if st.button("🚫 Fine £2"): process_transaction(curr, "Fine", 2, is_fine=True)

with tab2:
    st.header("🏆 Savings")
    for k in ["Eva", "Noah"]:
        kd = df_bal[df_bal['User'] == k].iloc[0]
        prog = min(kd['Vault'] / kd['Vault_Goal'], 1.0)
        st.subheader(f"{k}: £{kd['Vault']} / £{kd['Vault_Goal']}")
        st.progress(prog)
        if st.session_state.selected_user == k:
            amt = st.number_input(f"Deposit {k}", 1, 20, key=k)
            if st.button(f"🔒 Lock £{amt}", key=f"b{k}"): process_transaction(k, "Vault", amt, is_vault=True)

with tab3:
    st.header("📊 History")
    st.dataframe(df_hist.head(10), hide_index=True)
