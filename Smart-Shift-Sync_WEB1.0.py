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

# --- 解析ロジック (既存のものを流用) ---
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

# --- 認証Flowのキャッシュ管理 (これが重要) ---
@st.cache_resource
def get_flow():
    return Flow.from_client_config(
        CLIENT_CONFIG, 
        scopes=SCOPES, 
        redirect_uri=CLIENT_CONFIG["web"]["redirect_uris"][0]
    )

# --- UI ---
st.set_page_config(page_title="Shift Sync", page_icon="📅")
st.title("🎢 Shift Sync Online")

# セッション管理
if "events" not in st.session_state: st.session_state.events = []

# パラメータ取得
query_params = st.query_params
auth_code = query_params.get("code")

tab1, tab2 = st.tabs(["📋 解析", "🚀 同期"])

with tab1:
    raw_data = st.text_area("内容を貼り付けてください", height=200)
    if raw_data:
        st.session_state.events = parse_schedule_text(datetime.now().year, raw_data)
        if st.session_state.events:
            st.success(f"{len(st.session_state.events)}件解析完了")
            st.dataframe(pd.DataFrame([{"日付": e["start"].strftime("%m/%d"), "内容": e["subject"]} for e in st.session_state.events]))

with tab2:
    if not st.session_state.events:
        st.info("解析を先にしてください")
    else:
        flow = get_flow()
        
        # 状況に応じた表示切り替え
        if not auth_code:
            auth_url, _ = flow.authorization_url(prompt='consent')
            st.write("手順1: Googleで許可を与えてください")
            st.link_button("🔑 Google認証を開始", auth_url, use_container_width=True)
        else:
            st.success("✅ 認証コードを取得しました！")
            if st.button("手順2: カレンダーに同期を実行", type="primary", use_container_width=True):
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
                    st.success("成功！カレンダーを確認してください。")
                    st.balloons()
                    st.query_params.clear()
                except Exception as e:
                    st.error(f"エラー: 再度『認証を開始』からやり直してください。")
                    st.query_params.clear()
