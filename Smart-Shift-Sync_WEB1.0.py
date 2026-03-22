import streamlit as st
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- 設定 (Google Cloud Consoleで作成した情報を入力) ---
CLIENT_CONFIG = {
    "web": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "YOUR_CLIENT_SECRET",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost:8501"] # デプロイ後はURLを変更
    }
}
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# --- 1. ポータル接続ロジック ---
class PortalScraper:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://crew-p.usj.co.jp"
        self.headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, Gecko) Version/15.0 Mobile Safari"}

    def login(self, user_id, password):
        url = f"{self.base_url}/cws/mbl/MblActLogin@act=submit"
        payload = {"user_id": str(user_id), "password": str(password), "submit": " 　Login　 "}
        try:
            res = self.session.post(url, data=payload, headers=self.headers, timeout=10)
            res.encoding = "shift_jis"
            return "メインメニュー" in res.text or "main menu" in res.text
        except: return False

    def get_options(self):
        url = f"{self.base_url}/cws/mbl/MblActSftReqSftConfirm"
        res = self.session.get(url, headers=self.headers)
        res.encoding = "shift_jis"
        soup = BeautifulSoup(res.text, "html.parser")
        return [{"label": a.text.strip(), "url": f"{self.base_url}/cws/mbl/{a.get('href')}"} 
                for a in soup.find_all("a") if re.search(r"\d{1,2}/\d{1,2}", a.text)]

# --- 2. 解析・計算ロジック ---
def parse_text(year, text):
    events = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    date_re = re.compile(r"(\d{1,2})/(\d{1,2})\([^)]+\)")
    time_re = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")
    work_h_re = re.compile(r"\((\d+)h(\d*)m?\)")

    for i, line in enumerate(lines):
        date_m = date_re.search(line)
        if date_m:
            month, day = map(int, date_m.groups())
            start_t, end_t, work_h, pos = None, None, 0.0, ""
            for j in range(i+1, min(i+10, len(lines))):
                if date_re.search(lines[j]): break
                tm = time_re.search(lines[j])
                if tm:
                    start_t, end_t = tm.groups()
                    h_match = work_h_re.search(lines[j])
                    if h_match:
                        h = int(h_match.group(1))
                        m = int(h_match.group(2)) if h_match.group(2).isdigit() else 0
                        work_h = h + (m / 60.0)
                elif not pos and not any(x in lines[j] for x in ["メイン", "Ver", "シフト"]):
                    pos = lines[j]
            if start_t:
                s_dt = datetime(year, month, day, *map(int, start_t.split(":")))
                e_dt = datetime(year, month, day, *map(int, end_t.split(":")))
                if e_dt <= s_dt: e_dt += timedelta(days=1)
                events.append({"subject": pos, "start": s_dt, "end": e_dt, "hours": work_h})
    return events

def calc_pay(events, wage):
    total = 0.0
    for e in events:
        # 基本給
        total += e["hours"] * wage
        # 深夜手当 (22:00 - 05:00) 0.25倍増
        curr = e["start"]
        while curr < e["end"]:
            if curr.hour >= 22 or curr.hour < 5:
                total += (0.25 / 4) * wage # 15分単位
            curr += timedelta(minutes=15)
    return int(total)

# --- 3. Streamlit UI ---
st.set_page_config(page_title="USJ Shift Sync", layout="wide")
st.title("🎢 USJ Shift Sync Online")

# サイドバー設定 (一回限り)
with st.sidebar:
    st.header("設定")
    hourly_wage = st.number_input("時給 (円)", value=1290)
    target_year = st.number_input("対象年", value=datetime.now().year)
    st.divider()
    st.caption("ブラウザを閉じると全データが破棄されます。")

# メインコンテンツ
tab1, tab2 = st.tabs(["データ取得", "カレンダー同期"])

with tab1:
    method = st.radio("入力方法", ["ポータルから自動取得", "テキスト貼り付け"])
    raw_data = ""

    if method == "ポータルから自動取得":
        with st.form("login"):
            u_id = st.text_input("クルーID")
            u_pw = st.text_input("パスワード", type="password")
            if st.form_submit_button("ログイン"):
                scraper = PortalScraper()
                if scraper.login(u_id, u_pw):
                    st.session_state.opts = scraper.get_options()
                    st.session_state.scraper = scraper
                    st.success("ログイン成功！月を選択してください。")
                else: st.error("ログイン失敗")
        
        if "opts" in st.session_state:
            sel = st.selectbox("対象期間", [o["label"] for o in st.session_state.opts])
            if st.button("シフトを読み込む"):
                url = next(o["url"] for o in st.session_state.opts if o["label"] == sel)
                raw_data = st.session_state.scraper.fetch_portal_data(url)
    else:
        raw_data = st.text_area("ポータルの内容をコピペしてください", height=200)

    if raw_data:
        st.session_state.events = parse_text(target_year, raw_data)
        st.success(f"{len(st.session_state.events)}件のシフトを検出")

# 分析表示
if "events" in st.session_state and st.session_state.events:
    st.divider()
    c1, c2 = st.columns(2)
    total_pay = calc_pay(st.session_state.events, hourly_wage)
    c1.metric("概算給与 (深夜手当込)", f"¥{total_pay:,}")
    c2.metric("総労働時間", f"{sum(e['hours'] for e in st.session_state.events):.1f} h")
    
    df = pd.DataFrame([{
        "日付": e["start"].strftime("%m/%d"),
        "時間": f"{e['start'].strftime('%H:%M')}-{e['end'].strftime('%H:%M')}",
        "内容": e["subject"],
        "実働": f"{e['hours']}h"
    } for e in st.session_state.events])
    st.table(df)

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
                st.success("Googleカレンダーへの同期が完了しました！")
                st.balloons()
