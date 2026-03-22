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

# --- 解析ロジック ---
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
                elif not any(x in line for x in ["休", "メイン", "Ver", "シフト"]):
                    if not pos: pos = line
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
                total += (0.25 / 4) * wage
            curr += timedelta(minutes=15)
    return int(total)

# --- UI ---
st.set_page_config(page_title="Shift Sync", page_icon="📅")

# モバイルで見やすくするためのカスタムCSS
st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    button { width: 100% !important; height: 3rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("🎢 Shift Sync Online")

# サイドバーはスマホだと隠れるので、重要な設定をメイン画面上部へ
with st.expander("⚙️ 設定 (時給・年)", expanded=False):
    hourly_wage = st.number_input("時給 (円)", value=1290)
    target_year = st.number_input("対象年", value=datetime.now().year)

tab1, tab2 = st.tabs(["📋 入力・解析", "🚀 Google同期"])

with tab1:
    st.caption("調整中: ログイン機能 / 推奨: テキスト貼り付け")
    # 入力されると自動で解析が走る（ボタン不要）
    raw_data = st.text_area("内容を貼り付けてください", height=250, placeholder="3/1(Su)...")

    if raw_data:
        events = parse_schedule_text(target_year, raw_data)
        if events:
            st.session_state.events = events
            
            # 結果表示 (スマホで並んで見えるように)
            total_p = calc_pay(events, hourly_wage)
            total_h = sum(e['hours'] for e in events)
            
            m1, m2 = st.columns(2)
            m1.metric("概算給与", f"¥{total_p:,}")
            m2.metric("総労働時間", f"{total_h:.2f}h")
            
            with st.expander("詳細リストを表示", expanded=True):
                df = pd.DataFrame([{
                    "日付": e["start"].strftime("%m/%d"),
                    "時間": f"{e['start'].strftime('%H:%M')}-{e['end'].strftime('%H:%M')}",
                    "内容": e["subject"],
                    "実働": f"{e['hours']}h"
                } for e in events])
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning("シフトが見つかりません。")

with tab2:
    if "events" in st.session_state:
        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=CLIENT_CONFIG["web"]["redirect_uris"][0])
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        st.write("1. まずは権限を許可してください")
        st.link_button("🔑 Googleアカウントを認証", auth_url)

        auth_code = st.query_params.get("code")
        if auth_code:
            st.divider()
            st.write("2. 認証に成功しました！カレンダーに書き込みますか？")
            if st.button("📤 同期を実行する"):
                try:
                    with st.spinner("同期中..."):
                        flow.fetch_token(code=auth_code)
                        service = build("calendar", "v3", credentials=flow.credentials)
                        for e in st.session_state.events:
                            service.events().insert(calendarId="primary", body={
                                "summary": e["subject"],
                                "start": {"dateTime": e["start"].isoformat(), "timeZone": "Asia/Tokyo"},
                                "end": {"dateTime": e["end"].isoformat(), "timeZone": "Asia/Tokyo"},
                            }).execute()
                    st.success("成功しました！")
                    st.balloons()
                    st.query_params.clear()
                except:
                    st.error("エラー。再度「認証」からお願いします。")
                    st.query_params.clear()
    else:
        st.info("「入力・解析」タブでデータを貼り付けてください。")
