"""
通知モジュール
Slack Webhook を使用して日次レポートを送信する
"""
import os
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
TOP_N = int(os.getenv("TOP_N_JOBS", "10"))


def _get_score_emoji(score: float) -> str:
    """スコアに応じた絵文字を返す"""
    if score >= 85:
        return "🔥"
    elif score >= 70:
        return "⭐"
    elif score >= 60:
        return "✅"
    else:
        return "📋"


def _get_category_emoji(category: str) -> str:
    """カテゴリに応じた絵文字を返す"""
    mapping = {
        "SNS運用": "📱",
        "動画制作": "🎬",
        "広告運用": "📊",
        "コンテンツ制作": "✍️",
        "マーケティング": "📈",
        "その他": "💼",
    }
    for key, emoji in mapping.items():
        if key in category:
            return emoji
    return "💼"


def _get_platform_label(job: dict) -> str:
    """プラットフォームラベルを返す"""
    platform = job.get("platform", "")
    if platform == "crowdworks":
        return "CrowdWorks"
    elif platform == "lancers":
        return "Lancers"
    return "案件サイト"


def build_slack_message(jobs: list[dict], total_scraped: int, total_new: int) -> dict:
    """
    Slack通知メッセージを構築する

    Args:
        jobs: 通知対象の案件リスト（スコア降順）
        total_scraped: 今回収集した総件数
        total_new: 新規案件数

    Returns:
        Slack Blocks API 形式のメッセージ辞書
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    top_jobs = jobs[:TOP_N]

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📋 案件自動収集レポート - {today}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*収集件数:*\n{total_scraped}件"},
                {"type": "mrkdwn", "text": f"*新規案件:*\n{total_new}件"},
                {"type": "mrkdwn", "text": f"*推奨案件:*\n{len(jobs)}件"},
                {"type": "mrkdwn", "text": f"*TOP表示:*\n{len(top_jobs)}件"},
            ],
        },
        {"type": "divider"},
    ]

    if not top_jobs:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "本日は新規案件が見つかりませんでした。明日また自動収集します。",
            },
        })
    else:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🏆 本日のTOP{len(top_jobs)}推奨案件 (スコア順)*",
            },
        })

        for i, job in enumerate(top_jobs, 1):
            score = job.get("ai_score", 0)
            score_emoji = _get_score_emoji(score)
            cat_emoji = _get_category_emoji(job.get("ai_category", ""))
            job_type_label = "【業務委託】" if job.get("is_freelance") else "【提案候補】" if job.get("can_propose_freelance") else "【案件】"
            remote_label = "🏠 フルリモート可" if job.get("is_remote") else "📍 " + (job.get("location", "勤務地不明"))
            salary_text = job.get("salary_text", "給与記載なし")
            platform_label = _get_platform_label(job)

            proposal_hint = job.get("ai_proposal_hint", "")
            proposal_section = f"\n> 💡 *提案ヒント:* {proposal_hint}" if proposal_hint else ""

            url = job.get("url", "")
            url_text = f"\n🔗 <{url}|求人を見る>" if url else ""

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{score_emoji} *{i}. {job.get('title', 'タイトル不明')}*\n"
                        f"{cat_emoji} {job.get('ai_category', '')} | {job_type_label} | スコア: *{int(score)}点* | 📌 {platform_label}\n"
                        f"🏢 {job.get('company', '企業名不明')} | {remote_label}\n"
                        f"💴 {salary_text}\n"
                        f"📝 {job.get('ai_reason', '')}"
                        f"{proposal_section}"
                        f"{url_text}"
                    ),
                },
            })

            if i < len(top_jobs):
                blocks.append({"type": "divider"})

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"案件自動収集システム (CrowdWorks / Lancers) | {datetime.now().strftime('%H:%M')} 実行完了",
            }
        ],
    })

    return {"blocks": blocks}


def send_slack_notification(jobs: list[dict], total_scraped: int, total_new: int) -> bool:
    """
    Slack に通知を送信する

    Args:
        jobs: 通知対象の案件リスト
        total_scraped: 今回収集した総件数
        total_new: 新規案件数

    Returns:
        送信成功かどうか
    """
    if not SLACK_WEBHOOK_URL:
        logger.warning("[Notifier] SLACK_WEBHOOK_URL が設定されていません。通知をスキップします。")
        return False

    message = build_slack_message(jobs, total_scraped, total_new)
    payload = json.dumps(message).encode("utf-8")

    try:
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                logger.info(f"[Notifier] Slack通知を送信しました ({len(jobs)}件)")
                return True
            else:
                logger.error(f"[Notifier] Slack送信失敗: HTTP {response.status}")
                return False

    except urllib.error.URLError as e:
        logger.error(f"[Notifier] Slack送信エラー: {e}")
        return False


def print_report(jobs: list[dict], total_scraped: int, total_new: int):
    """
    コンソールにレポートを出力する（Slack未設定時のフォールバック）
    """
    today = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    print("\n" + "=" * 70)
    print(f"  📋 案件自動収集レポート - {today}")
    print(f"  対象プラットフォーム: CrowdWorks / Lancers")
    print("=" * 70)
    print(f"  収集件数: {total_scraped}件 | 新規: {total_new}件 | 推奨: {len(jobs)}件")
    print("=" * 70)

    if not jobs:
        print("  本日は新規案件が見つかりませんでした。明日また自動収集します。")
    else:
        top_jobs = jobs[:TOP_N]
        print(f"\n  🏆 TOP{len(top_jobs)} 推奨案件\n")
        for i, job in enumerate(top_jobs, 1):
            score = job.get("ai_score", 0)
            score_emoji = _get_score_emoji(score)
            job_type = "【業務委託】" if job.get("is_freelance") else "【提案候補】" if job.get("can_propose_freelance") else ""
            platform_label = _get_platform_label(job)
            print(f"  {score_emoji} {i}. {job.get('title', '')[:60]}")
            print(f"     スコア: {int(score)}点 | {job.get('ai_category', '')} {job_type} | {platform_label}")
            print(f"     企業: {job.get('company', '不明')} | {'リモート可' if job.get('is_remote') else job.get('location', '')}")
            print(f"     給与: {job.get('salary_text', '記載なし')}")
            print(f"     理由: {job.get('ai_reason', '')}")
            if job.get("ai_proposal_hint"):
                print(f"     提案: {job.get('ai_proposal_hint')}")
            if job.get("url"):
                print(f"     URL: {job.get('url')}")
            print()

    print("=" * 70 + "\n")
