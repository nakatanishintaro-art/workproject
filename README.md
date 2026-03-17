# 案件自動収集・AIマッチングシステム

SHINONOME Co.,Ltd. 向け業務委託案件自動収集ツール

**CrowdWorks** と **Lancers** から毎日自動で業務委託案件を収集し、OpenAI GPT-4.1-mini で自社スキルとのマッチングスコアを算出、Slack に通知します。

> **注意**: Indeed.com は Cloudflare Bot 対策により自動収集が不可のため、CrowdWorks・Lancers を使用しています。

---

## 機能一覧

| 機能 | 説明 |
|------|------|
| 案件収集 | CrowdWorks・Lancers から最新の業務委託案件を自動収集 |
| AIスコアリング | GPT-4.1-mini が自社スキルとの適合度を0〜100点で評価 |
| 重複排除 | SQLite DB で既存案件をスキップ、新規案件のみ処理 |
| Slack通知 | 推奨案件をSlackに自動通知（提案ヒント付き） |
| 日次自動実行 | GitHub Actions で毎朝9時（JST）に自動実行 |
| ログ管理 | 実行ログを30日間保存、古いログは自動削除 |

---

## ディレクトリ構成

```
indeed_matcher/
├── main.py                         # メインエントリーポイント
├── run_daily.sh                    # ローカル日次実行スクリプト（cron用）
├── requirements.txt                # Python依存パッケージ
├── .env.example                    # 環境変数テンプレート
├── .github/
│   └── workflows/
│       └── daily_run.yml           # GitHub Actions 設定（毎朝9時 JST）
├── src/
│   ├── __init__.py
│   ├── scraper.py                  # CrowdWorks・Lancers スクレイパー
│   ├── ai_scorer.py                # OpenAI AIスコアリング
│   ├── database.py                 # SQLite DB管理
│   ├── notifier.py                 # Slack通知・レポート出力
│   └── company_profile.py          # 自社プロフィール・検索キーワード設定
├── data/
│   └── jobs.db                     # SQLite データベース（自動生成）
└── logs/                           # 実行ログ（自動生成）
```

---

## セットアップ手順

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を編集して以下を設定：

```env
# 必須
OPENAI_API_KEY=sk-...

# 任意（設定するとSlack通知が有効になる）
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# 調整可能なパラメータ
MIN_SCORE_TO_NOTIFY=60      # 通知するスコアの閾値（0〜100）
TOP_N_JOBS=10               # Slackに表示する上位件数
MAX_JOBS_PER_RUN=100        # 1回の実行で収集する最大件数
SCRAPE_DELAY_SECONDS=2      # スクレイピング間隔（秒）
```

### 3. 実行

```bash
# 通常実行（案件収集 → AIスコアリング → Slack通知）
python3 main.py

# テストモード（サンプルデータでAIとSlack通知をテスト）
python3 main.py --test

# 通知のみ（既存のスコア済みデータを再通知）
python3 main.py --notify-only
```

---

## GitHub Actions による日次自動実行

### 設定手順

1. GitHubにリポジトリを作成してコードをプッシュ
2. **Settings → Secrets and variables → Actions** で以下を設定：

| 種別 | キー | 値 |
|------|------|----|
| Secret | `OPENAI_API_KEY` | OpenAI APIキー |
| Secret | `SLACK_WEBHOOK_URL` | Slack Webhook URL |

3. 設定完了後、毎日 **09:00 JST** に自動実行されます
4. **Actions タブ → Run workflow** で手動実行も可能

---

## ローカル環境での日次自動実行（cron）

サーバーやPC上で直接実行する場合は `crontab` を使用します：

```bash
# crontab を編集
crontab -e

# 毎朝9時に実行（以下を追加）
0 9 * * * /home/ubuntu/indeed_matcher/run_daily.sh
```

---

## Slack Webhook URLの取得方法

1. [Slack API](https://api.slack.com/apps) にアクセス
2. **Create New App** → **From scratch**
3. **Incoming Webhooks** を有効化
4. **Add New Webhook to Workspace** で通知先チャンネルを選択
5. 生成された Webhook URL をコピーして `.env` に設定

---

## カスタマイズ

### 検索キーワードの変更

`src/company_profile.py` の `SEARCH_QUERIES` を編集：

```python
SEARCH_QUERIES = [
    {"keyword": "SNS運用 業務委託", "location": ""},
    {"keyword": "広告運用 業務委託 リモート", "location": ""},
    # ... 追加・変更可能
]
```

### スコアリング基準の変更

`src/company_profile.py` の `COMPANY_PROFILE` を編集してスキルや強みを更新すると、AIスコアリングの基準が変わります。

### 通知スコア閾値の変更

`.env` の `MIN_SCORE_TO_NOTIFY` を変更（デフォルト: 60点）

---

## 動作確認済み環境

- Python 3.11
- Ubuntu 22.04 / macOS / Windows (WSL2)
- GitHub Actions (ubuntu-latest)
