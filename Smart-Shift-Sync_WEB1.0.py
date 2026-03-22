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

# --- 解析・給与計算ロジック ---
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

# --- UI設定 ---
st.set_page_config(page_title="Shift Sync", page_icon="📅")
st.title("🎢 Shift Sync Online")

# セッション状態の初期化
if "events" not in st.session_state: st.session_state.events = []
if "auth_code" not in st.session_state: st.session_state.auth_code = None

# URLからcodeを取得して保持
current_code = st.query_params.get("code")
if current_code:
    st.session_state.auth_code = current_code

with st.sidebar:
    st.header("⚙️ 設定")
    hourly_wage = st.number_input("時給 (円)", value=1290)
    target_year = st.number_input("対象年", value=datetime.now().year)

tab1, tab2 = st.tabs(["📋 解析", "🚀 同期"])

with tab1:
    raw_data = st.text_area("内容を貼り付けてください", height=250)
    if raw_data:
        st.session_state.events = parse_schedule_text(target_year, raw_data)
        if st.session_state.events:
            p = calc_pay(st.session_state.events, hourly_wage)
            h = sum(e['hours'] for e in st.session_state.events)
            st.metric("概算給与", f"¥{p:,}")
            st.metric("総労働時間", f"{h:.2f}h")
            st.dataframe(pd.DataFrame([{
                "日付": e["start"].strftime("%m/%d"),
                "内容": e["subject"],
                "実働": f"{e['hours']}h"
            } for e in st.session_state.events]), use_container_width=True)

with tab2:
    if not st.session_state.events:
        st.info("先に解析を完了させてください。")
    else:
        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, redirect_uri=CLIENT_CONFIG["web"]["redirect_uris"][0])
        auth_url, _ = flow.authorization_url(prompt='consent')

        # ステップ1: 認証ボタン
        st.link_button("1. Googleで認証する", auth_url, use_container_width=True)

        # ステップ2: 同期実行（codeが保持されている場合のみ表示）
        if st.session_state.auth_code:
            st.success("✅ 認証を確認しました。")
            if st.button("2. カレンダーに同期を実行", type="primary", use_container_width=True):
                try:
                    with st.spinner("同期中..."):
                        flow.fetch_token(code=st.session_state.auth_code)
                        service = build("calendar", "v3", credentials=flow.credentials)
                        for e in st.session_state.events:
                            service.events().insert(calendarId="primary", body={
                                "summary": e["subject"],
                                "start": {"dateTime": e["start"].isoformat(), "timeZone": "Asia/Tokyo"},
                                "end": {"dateTime": e["end"].isoformat(), "timeZone": "Asia/Tokyo"},
                            }).execute()
                        st.success("完了しました！")
                        st.balloons()
                        # 使用済みコードをクリア
                        st.session_state.auth_code = None
                        st.query_params.clear()
                except Exception as ex:
                    st.error("認証の有効期限が切れた可能性があります。もう一度手順1からやり直してください。")
                    st.session_state.auth_code = None
                    st.query_params.clear()
