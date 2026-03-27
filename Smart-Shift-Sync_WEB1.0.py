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

# --- 認証Flowのキャッシュ管理 ---
@st.cache_resource
def get_flow():
    return Flow.from_client_config(
        CLIENT_CONFIG, 
        scopes=SCOPES, 
        redirect_uri=CLIENT_CONFIG["web"]["redirect_uris"][0]
    )

# --- UI設定 ---
st.set_page_config(page_title="Shift Sync", page_icon="📅")
st.title("🎢 Shift Sync Online")

# セッション状態の初期化
if "events" not in st.session_state:
    st.session_state.events = []

# URLから認証コードを取得
auth_code = st.query_params.get("code")

# タブの作成（認証後は自動で同期タブを推奨）
tab1, tab2 = st.tabs(["📋 解析", "🚀 同期"])

with tab1:
    raw_data = st.text_area("シフト内容を貼り付けてください", height=200, placeholder="05/20(月)...\n09:00 - 17:00...")
    if raw_data:
        st.session_state.events = parse_schedule_text(datetime.now().year, raw_data)
        if st.session_state.events:
            st.success(f"✅ {len(st.session_state.events)}件のイベントを解析しました。")
            df = pd.DataFrame([
                {"日付": e["start"].strftime("%m/%d"), "時間": f"{e['start'].strftime('%H:%M')}~", "内容": e["subject"]} 
                for e in st.session_state.events
            ])
            st.dataframe(df, use_container_width=True)
            st.info("上の「🚀 同期」タブに切り替えてください。")

with tab2:
    if not st.session_state.events:
        st.warning("先に「解析」タブでデータを入力してください。")
    else:
        flow = get_flow()
        
        if not auth_code:
            # まだ認証していない場合
            auth_url, _ = flow.authorization_url(prompt='consent')
            st.subheader("ステップ1: Google認証")
            st.write("カレンダーへの書き込み許可が必要です。下のボタンを押すとGoogleのログイン画面に移動します。")
            
            # カスタムHTMLボタン（target="_self" で同じタブで開く）
            button_style = """
                <a href="{url}" target="_self" style="
                    display: inline-block;
                    padding: 0.5em 1em;
                    text-decoration: none;
                    background-color: #FF4B4B;
                    color: white;
                    border-radius: 0.5rem;
                    width: 100%;
                    text-align: center;
                    font-weight: bold;
                    border: none;
                ">🔑 Google認証を開始（同じタブで開く）</a>
            """
            st.markdown(button_style.format(url=auth_url), unsafe_allow_html=True)
            
        else:
            # 認証コードがURLにある場合
            st.success("✅ Googleとの連携準備が整いました。")
            st.subheader("ステップ2: カレンダー同期")
            
            if st.button("カレンダーに一括登録する", type="primary", use_container_width=True):
                try:
                    with st.spinner("Googleカレンダーに登録中..."):
                        # トークンの取得
                        flow.fetch_token(code=auth_code)
                        credentials = flow.credentials
                        service = build("calendar", "v3", credentials=credentials)
                        
                        # イベントの登録
                        for e in st.session_state.events:
                            event_body = {
                                "summary": e["subject"],
                                "start": {"dateTime": e["start"].isoformat(), "timeZone": "Asia/Tokyo"},
                                "end": {"dateTime": e["end"].isoformat(), "timeZone": "Asia/Tokyo"},
                            }
                            service.events().insert(calendarId="primary", body=event_body).execute()
                            
                    st.balloons()
                    st.success("すべてのシフトをカレンダーに登録しました！")
                    
                    # 完了後にパラメータをクリア（リロードされる）
                    st.query_params.clear()
                    
                except Exception as ex:
                    st.error("エラーが発生しました。認証の有効期限が切れた可能性があります。")
                    st.info("もう一度『認証を開始』からやり直してください。")
                    # 失敗時もパラメータをクリアしてリセットしやすくする
                    if st.button("リセットしてやり直す"):
                        st.query_params.clear()
