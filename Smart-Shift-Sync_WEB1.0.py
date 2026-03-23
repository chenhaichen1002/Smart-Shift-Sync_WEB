import streamlit as st
import re
import pandas as pd
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- 設定 ---
CLIENT_CONFIG = {
    "web": {
        "client_id": "721743236712-giicql65qcqqli90lhit6th8omoqtndl.apps.googleusercontent.com",
        "client_secret": "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",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["https://smart-shift-syncweb-mmahtfwspadpxywkmsxetf.streamlit.app/"]
    }
}
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# --- 解析・給与計算ロジック (ポジション解析強化) ---
def parse_schedule_text(year, text):
    events = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    date_re = re.compile(r"(\d{1,2})/(\d{1,2})\([^)]+\)")
    time_re = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")
    work_h_re = re.compile(r"\((\d+)h(\d*)m?\)")

    i = 0
    while i < len(lines):
        date_m = date_re.search(lines[i])
        if date_m:
            month, day = map(int, date_m.groups())
            start_t, end_t, work_h, pos = None, None, 0.0, ""
            j = i + 1
            while j < len(lines) and not date_re.search(lines[j]):
                line = lines[j]
                tm = time_re.search(line)
                if tm and "[休" not in line:
                    start_t, end_t = tm.groups()
                    h_match = work_h_re.search(line)
                    if h_match:
                        h = int(h_match.group(1))
                        m = int(h_match.group(2)) if h_match.group(2).isdigit() else 0
                        work_h = h + (m / 60.0)
                # ポジション（DKM L等）を確実に拾うロジック
                elif not any(x in line for x in ["休", "メイン", "Ver", "シフト", "ログアウト"]):
                    if line and not pos: 
                        pos = line # 最初に見つかった単語をポジションとする
                j += 1
            
            if start_t:
                try:
                    s_dt = datetime(year, month, day, *map(int, start_t.split(":")))
                    e_dt = datetime(year, month, day, *map(int, end_t.split(":")))
                    if e_dt <= s_dt: e_dt += timedelta(days=1)
                    events.append({"subject": pos if pos else "勤務", "start": s_dt, "end": e_dt, "hours": work_h})
                except: pass
            i = j - 1
        i += 1
    return events

def calc_pay(events, wage):
    total = 0.0
    for e in events:
        total += e["hours"] * wage
        curr = e["start"]
        while curr < e["end"]:
            if curr.hour >= 22 or curr.hour < 5:
                total += (0.25 / 4) * wage # 深夜手当 0.25倍
            curr += timedelta(minutes=15)
    return int(total)

# --- UI設定 ---
st.set_page_config(page_title="Shift Sync", layout="centered")

# スマホ向けCSS調整
st.markdown("""
    <style>
    .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
    .stButton button { width: 100%; height: 3.5rem; font-weight: bold; }
    textarea { font-size: 16px !important; } /* スマホのズーム防止 */
    </style>
    """, unsafe_allow_html=True)

st.title("🎢 Shift Sync Online")

# セッション状態
if "events" not in st.session_state: st.session_state.events = []
if "creds" not in st.session_state: st.session_state.creds = None

# --- 新しい流れ：1. Google権限請求 ---
flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=CLIENT_CONFIG["web"]["redirect_uris"][0])
auth_code = st.query_params.get("code")

if not st.session_state.creds:
    if not auth_code:
        st.warning("⚠️ 最初にGoogle連携が必要です")
        auth_url, _ = flow.authorization_url(prompt='consent')
        st.link_button("🔑 Googleアカウントを認証", auth_url, type="primary")
        st.stop() # 認証されるまで下の画面を出さない
    else:
        try:
            flow.fetch_token(code=auth_code)
            st.session_state.creds = flow.to_json() # メモリに保持
            st.query_params.clear()
            st.rerun()
        except:
            st.error("認証エラー。再度お試しください。")
            st.query_params.clear()
            st.stop()

# --- 2. 解析・給与計算セクション ---
st.success("✅ Google認証済み")

with st.expander("⚙️ 時給設定", expanded=False):
    hourly_wage = st.number_input("時給 (円)", value=1290)
    target_year = st.number_input("年", value=datetime.now().year)

raw_data = st.text_area("シフト内容を貼り付け", height=200, placeholder="3/1(Su)...")

if raw_data:
    st.session_state.events = parse_schedule_text(target_year, raw_data)
    if st.session_state.events:
        # 給与計算表示
        pay = calc_pay(st.session_state.events, hourly_wage)
        hrs = sum(e['hours'] for
