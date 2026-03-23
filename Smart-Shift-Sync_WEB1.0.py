import streamlit as st
import re
from datetime import datetime, timedelta

# --- ページ設定 (スマホ対応) ---
st.set_page_config(
    page_title="Smart Shift Sync",
    page_icon="📅",
    layout="centered", # スマホで中央に収まるように
    initial_sidebar_state="collapsed"
)

# --- カスタムCSS (スマホ最適化) ---
st.markdown("""
    <style>
    .main { max-width: 600px; margin: 0 auto; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #0073e6; color: white; }
    .salary-box { background-color: #f0f8ff; padding: 15px; border-radius: 10px; border: 1px solid #0073e6; }
    @media (max-width: 480px) {
        h1 { font-size: 1.5rem !important; }
        .stMarkdown { font-size: 0.9rem; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- ロジック関数 ---

def calculate_salary(start_str, end_str, hourly_wage):
    """深夜手当(22:00-05:00)を考慮した給与計算"""
    fmt = "%H:%M"
    start = datetime.strptime(start_str, fmt)
    end = datetime.strptime(end_str, fmt)
    
    # 終了が開始より前（深夜またぎ）の場合の日時調整
    if end <= start:
        end += timedelta(days=1)
    
    total_hours = (end - start).total_seconds() / 3600
    
    # 深夜時間帯の判定 (22:00 - 29:00として計算)
    night_start = datetime.strptime("22:00", fmt)
    night_end = datetime.strptime("05:00", fmt) + timedelta(days=1)
    
    overlap_start = max(start, night_start)
    overlap_end = min(end, night_end)
    
    night_hours = max(0, (overlap_end - overlap_start).total_seconds() / 3600)
    normal_hours = total_hours - night_hours
    
    salary = (normal_hours * hourly_wage) + (night_hours * hourly_wage * 1.25)
    return int(salary), total_hours

def parse_shift_text(text):
    """テキストから時間とポジションを抽出"""
    # 例: "10:00-19:00 [レジ]" または "10:00〜19:00 レジ"
    pattern = r"(\d{1,2}:\d{2})[-〜](\d{1,2}:\d{2})\s*\[?(.*?)\]?$"
    lines = text.strip().split('\n')
    results = []
    
    for line in lines:
        match = re.search(pattern, line.strip())
        if match:
            results.append({
                "start": match.group(1),
                "end": match.group(2),
                "pos": match.group(3) if match.group(3) else "勤務"
            })
    return results

# --- メインUI ---

st.title("🚀 Smart Shift Sync")

# セッション状態でログイン管理 (ダミーフラグ)
if 'google_auth' not in st.session_state:
    st.session_state.google_auth = False

# STEP 1: Google認証 (未認証の場合)
if not st.session_state.google_auth:
    st.subheader("Step 1: Googleカレンダー連携")
    st.info("同期を開始するには、まずGoogleアカウントの権限を許可してください。")
    
    if st.button("Googleアカウントでログイン"):
        # 本来はここでGoogle OAuthのURLへリダイレクト
        # 今回はテスト用にフラグをTrueにする処理
        st.session_state.google_auth = True
        st.rerun()

# STEP 2: 解析 & 同期 (認証済みの場合)
else:
    st.subheader("Step 2: シフト解析")
    
    with st.expander("設定", expanded=False):
        wage = st.number_input("時給設定 (円)", value=1200, step=10)
    
    input_data = st.text_area("シフトを貼り付けてください", placeholder="例: 10:00-19:00 [レジ]", height=150)
    
    if input_data:
        shifts = parse_shift_text(input_data)
        
        if shifts:
            st.write("### 解析結果")
            total_est_salary = 0
            
            for s in shifts:
                salary, hours = calculate_salary(s['start'], s['end'], wage)
                total_est_salary += salary
                
                with st.container():
                    st.markdown(f"**{s['pos']}** | {s['start']} - {s['end']} ({hours}h)")
                    st.caption(f"概算給与: ¥{salary:,}")
                    st.divider()
            
            st.markdown(f"""
                <div class="salary-box">
                    <strong>合計見込み給与: ¥{total_est_salary:,}</strong><br>
                    <small>※深夜手当(25%)を含む概算です。</small>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("Googleカレンダーに同期する"):
                with st.spinner("同期中..."):
                    # ここにGoogle Calendar APIへの登録ロジックを記述
                    st.success("同期が完了しました！カレンダーを確認してください。")
                    
        else:
            st.warning("シフトの形式が解析できませんでした。")

    if st.button("ログアウト / 権限解除"):
        st.session_state.google_auth = False
        st.rerun()

st.divider()
st.caption("© 2026 Chen - Smart Shift Sync (Web v1.1)")
