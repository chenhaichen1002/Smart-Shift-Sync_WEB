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
        "redirect_uris": ["https://smart-shift-syncweb-mmahtfwspadpxywkmsxetf.streamlit.app"] 
    }
}
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# --- 改良版解析ロジック ---
def parse_schedule_text(year, text):
    events = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    
    # 日付 (3/1(Su))
    date_re = re.compile(r"(\d{1,2})/(\d{1,2})\([^)]+\)")
    # 時間 (9:15-19:45)
    time_re = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")
    # 実働時間 (8h30) または (9h)
    work_h_re = re.compile(r"\((\d+)h(\d*)m?\)")

    i = 0
    while i < len(lines):
        date_m = date_re.search(lines[i])
        if date_m:
            month, day = map(int, date_m.groups())
            start_t, end_t, work_h, pos = None, None, 0.0, ""
            
            # 日付行の次から探索
            j = i + 1
            while j < len(lines) and not date_re.search(lines[j]):
                line = lines[j]
                
                # 時間と実働時間の抽出
                tm = time_re.search(line)
                if tm and "[休" not in line: # 休憩時間の行を除外
                    start_t, end_t = tm.groups()
                    h_match = work_h_re.search(line)
                    if h_match:
                        h = int(h_match.group(1))
                        m = int(h_match.group(2)) if h_match.group(2) and h_match.group(2).isdigit() else 0
                        work_h = h + (m / 60.0)
                
                # 勤務内容の抽出 (DKM L等)
                elif not any(x in line for x in ["休", "メイン", "Ver", "シフト"]):
                    if not pos: pos = line
                j += 1
            
            if start_t:
                s_dt = datetime(year, month, day, *map(int, start_t.split(":")))
                e_dt = datetime(year, month, day, *map(int, end_t.split(":")))
                if e_dt <= s_dt: e_dt += timedelta(days=1)
                
                events.append({
                    "subject": pos if pos else "勤務",
                    "start": s_dt,
                    "end": e_dt,
                    "hours": work_h
                })
            i = j - 1
        i += 1
    return events

def calc_pay(events, wage):
    total = 0.0
    for e in events:
        total += e["hours"] * wage
        # 深夜手当 (22時-5時)
        curr = e["start"]
        while curr < e["end"]:
            if curr.hour >= 22 or curr.hour < 5:
                total += (0.25 / 4) * wage
            curr += timedelta(minutes=15)
    return int(total)

# --- UI ---
st.set_page_config(page_title="Shift Sync Online", layout="wide")
st.title("🎢 Shift Sync Online")

with st.sidebar:
    st.header("⚙️ 設定")
    hourly_wage = st.number_input("時給 (円)", value=1290)
    target_year = st.number_input("対象年", value=datetime.now().year)
    st.divider()
    st.caption("データは保存されません。")

tab1, tab2 = st.tabs(["データ入力", "Google同期"])

with tab1:
    st.info("💡 ログイン機能は現在調整中です。テキスト貼り付けをご利用ください。")
    raw_data = st.text_area("解析するテキストを貼り付けてください", height=250, placeholder="3/1(Su)\n9:15-19:45 (8h30)...")

    if raw_data:
        events = parse_schedule_text(target_year, raw_data)
        if events:
            st.session_state.events = events
            st.success(f"{len(events)} 件のシフトを検出しました")
            
            c1, c2 = st.columns(2)
            total_p = calc_pay(events, hourly_wage)
            c1.metric("概算給与 (深夜手当込)", f"¥{total_p:,}")
            c2.metric("総労働時間", f"{sum(e['hours'] for e in events):.2f} h")
            
            df = pd.DataFrame([{
                "日付": e["start"].strftime("%m/%d(%a)"),
                "時間": f"{e['start'].strftime('%H:%M')}-{e['end'].strftime('%H:%M')}",
                "内容": e["subject"],
                "実働": f"{e['hours']}h"
            } for e in events])
            st.table(df)
        else:
            st.error("シフトを検出できませんでした。形式を確認してください。")

with tab2:
    if "events" in st.session_state:
        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=CLIENT_CONFIG["web"]["redirect_uris"][0])
        auth_url, _ = flow.authorization_url(prompt='consent')
        st.link_button("Googleアカウントを認証して同期", auth_url, type="primary")

        if "code" in st.query_params:
            if st.button("同期を実行する"):
                flow.fetch_token(code=st.query_params["code"])
                service = build("calendar", "v3", credentials=flow.credentials)
                for e in st.session_state.events:
                    service.events().insert(calendarId="primary", body={
                        "summary": e["subject"],
                        "start": {"dateTime": e["start"].isoformat(), "timeZone": "Asia/Tokyo"},
                        "end": {"dateTime": e["end"].isoformat(), "timeZone": "Asia/Tokyo"}
                    }).execute()
                st.success("同期完了！")
                st.balloons()
