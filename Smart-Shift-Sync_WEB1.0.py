<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Shift Sync</title>
    <style>
        :root {
            --primary-color: #0073e6;
            --accent-color: #2ecc71;
            --bg-color: #f4f7f9;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background-color: var(--bg-color);
            line-height: 1.6;
        }
        header {
            background: var(--primary-color);
            color: white;
            padding: 1rem;
            text-align: center;
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        main {
            padding: 15px;
            max-width: 600px; /* スマホで見やすい幅に制限 */
            margin: 0 auto;
        }
        section {
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        h2 {
            color: var(--primary-color);
            font-size: 1.25rem;
            border-bottom: 2px solid var(--bg-color);
            padding-bottom: 10px;
            margin-top: 0;
        }
        /* ワークフローの改善（番号付き） */
        .step-box {
            background: #eef6ff;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            border-left: 4px solid var(--primary-color);
        }
        .app-link {
            display: block;
            background: var(--primary-color);
            color: white;
            text-align: center;
            padding: 12px;
            text-decoration: none;
            border-radius: 8px;
            margin: 10px 0;
            font-weight: bold;
        }
        .salary-info {
            background: #fff9db;
            padding: 10px;
            border-radius: 5px;
            font-size: 0.9em;
        }
        footer {
            text-align: center;
            padding: 20px;
            font-size: 0.8rem;
            color: #666;
        }
        /* スマホ向け調整 */
        @media (max-width: 480px) {
            h1 { font-size: 1.5rem; }
            section { padding: 15px; }
        }
    </style>
</head>
<body>
    <header>
        <h1>Smart Shift Sync</h1>
    </header>
    <main>
        <section>
            <h2>ご利用の流れ (改善版)</h2>
            <p>同期ミスを防ぐため、以下の手順で操作してください：</p>
            <div class="step-box">
                <strong>Step 1: Google認証</strong><br>
                最初にカレンダーへの書き込み権限を許可します。
            </div>
            <div class="step-box">
                <strong>Step 2: シフト解析</strong><br>
                ポータルのテキストを貼り付けて解析を実行します。
            </div>
            <div class="step-box">
                <strong>Step 3: 同期完了</strong><br>
                解析されたポジション・給与を確認して同期。
            </div>
        </section>

        <section>
            <h2>アップデート機能</h2>
            <ul>
                <li><strong>ポジション解析:</strong> 担当業務（レジ、品出し、イベント等）を自動判別し、カレンダーのタイトルに反映。</li>
                <li><strong>給与シミュレーション:</strong> 
                    <div class="salary-info">
                        時給設定に基づき、深夜手当(25%)や残業代を自動計算。概算給与を同期前に確認可能。
                    </div>
                </li>
            </ul>
        </section>

        <section>
            <h2>アプリを起動する</h2>
            <a href="https://smart-shift-syncweb-mmahtfwspadpxywkmsxetf.streamlit.app/" class="app-link">Shift Sync Online (Web版)</a>
            <a href="https://github.com/chenhaichen1002/Smart-Shift-Sync_GUI" style="color:var(--primary-color); display:block; text-align:center;">Windows GUI版はこちら</a>
        </section>

        <section>
            <h2>開発中の新機能</h2>
            <p><strong>Smart-Shift-change:</strong> <br>交代希望時の連絡ミスを防ぐ、スタッフ間確認ツールを開発検討中です。</p>
        </section>
    </main>
    <footer>
        <p>&copy; 2026 Chen - Smart Shift Sync<br>Developed for efficiency and accuracy.</p>
    </footer>
</body>
</html>
