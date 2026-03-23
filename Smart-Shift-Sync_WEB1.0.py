import streamlit as st
import re
import pandas as pd
import json
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

# --- 解析ロジック (ポジション抽出を強化) ---
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
                # ポジション（DKM L等）の抽出
                elif not any(x in line for x in ["休", "メイン", "Ver", "シフト", "ログアウト", "確定", "▲"]):
                    if line and not pos and not line.startswith("※"):
                        pos = line
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

# --- 給料計算 (深夜25%増) ---
def calc_pay(events, wage):
    total = 0.0
    for e in events:
        total += e["hours"] * wage
        curr = e["start"]
        while curr < e["end"]:
            if curr.hour >= 22 or curr.hour < 5:
                total += (0.25 / 4) * wage
            curr += timedelta(minutes=15)
    return int(total)

# --- UI ---
st.set_page_config(page_title="Shift Sync Online", layout="centered")
st.markdown("<style>.stMetric {background-color: #f0f2f6; padding: 15px; border-radius: 10px;} .stButton button {width: 100%; height: 3.5rem; font-weight: bold;} textarea {font-size: 16px !important;}</style>", unsafe_allow_html=True)
st.title("🎢 Shift Sync Online")

# セッション管理
if "creds_json" not in st.session_state: st.session_state.creds_json = None

# --- 認証処理 (一回切りを徹底) ---
flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=CLIENT_CONFIG["web"]["redirect_uris"][0])
auth_code = st.query_params.get("code")

# 認証がまだ、かつURLにcodeがある場合のみトークン交換
if not st.session_state.creds_json and auth_code:
    try:
        flow.fetch_token(code=auth_code)
        st.session_state.creds_json = flow.credentials.to_json()
        st.query_params.clear() # codeを消してリロードループを止める
        st.rerun()
    except Exception:
        # 失敗したらcodeを消して初期画面に戻す
        st.query_params.clear()
        st.rerun()

# 画面表示の分岐
if not st.session_state.creds_json:
    st.info("👋 最初にGoogle連携をお願いします")
    auth_url, _ = flow.authorization_url(prompt='consent')
    st.link_button("🔑 Googleアカウントを認証", auth_url, type="primary")
    st.stop()

# --- 認証済み：メイン機能 ---
st.success("✅ Google連携済み")

with st.expander("⚙️ 設定 (時給・年)", expanded=False):
    hourly_wage = st.number_input("時給 (円)", value=1290)
    target_year = st.number_input("対象年", value=datetime.now().year)

raw_data = st.text_area("内容を貼り付けてください", height=200)

if raw_data:
    events = parse_schedule_text(target_year, raw_data)
    if events:
        pay = calc_pay(events, hourly_wage)
        total_h = sum(e['hours'] for e in events)
        
        c1, c2 = st.columns(2)
        c1.metric("概算給与", f"¥{pay:,}")
        c2.metric("総労働時間", f"{total_h:.2f}h")
        
        df = pd.DataFrame([{"日付": e["start"].strftime("%m/%d"), "内容": e["subject"], "実働": f"{e['hours']}h"} for e in events])
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("🚀 カレンダーへ同期"):
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_info(json.loads(st.session_state.creds_json))
            service = build("calendar", "v3", credentials=creds)
            
            with st.spinner("同期中..."):
                for e in events:
                    service.events().insert(calendarId="primary", body={
                        "summary": e["subject"],
                        "start": {"dateTime": e["start"].isoformat(), "timeZone": "Asia/Tokyo"},
                        "end": {"dateTime": e["end"].isoformat(), "timeZone": "Asia/Tokyo"},
                    }).execute()
            st.success("完了！")
            st.balloons()
