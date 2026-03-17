"""
AIマッチングスコアリングモジュール
OpenAI API (GPT-4.1-mini) を使用して案件と自社プロフィールのマッチ度を評価する
"""
import os
import json
import logging
import time
from typing import Optional
from openai import OpenAI

from .company_profile import COMPANY_PROFILE

logger = logging.getLogger(__name__)

client = OpenAI()  # OPENAI_API_KEY は環境変数から自動取得

MIN_SCORE = int(os.getenv("MIN_SCORE_TO_NOTIFY", "60"))


SYSTEM_PROMPT = f"""
あなたは優秀な営業アシスタントです。
以下の会社プロフィールを持つ会社の代わりに、Indeed上の求人案件を評価してください。

## 会社プロフィール
会社名: {COMPANY_PROFILE['name']}
事業内容: {COMPANY_PROFILE['description']}
スキル・専門領域:
{chr(10).join([f'- {s}' for s in COMPANY_PROFILE['skills']])}

強み:
{chr(10).join([f'- {s}' for s in COMPANY_PROFILE['strengths']])}

## 評価の観点
1. この会社が受注・対応できる案件かどうか
2. 業務委託案件として直接受注できるか、またはアルバイト求人に対して業務委託を提案できるか
3. 時給換算で{COMPANY_PROFILE['preferred_budget_hourly_min']}円以上の収益性があるか
4. フルリモートで対応できるか

## 重要なルール
- 正社員・契約社員の採用案件は低スコアにする
- 会社のスキルと全く関係ない業種（製造業、医療、建設など）は低スコアにする
- アルバイト求人でも、業務委託として提案できる可能性があれば高く評価する
- 自治体・官公庁案件は特に高く評価する
"""


def score_job(job: dict) -> dict:
    """
    1件の案件をAIでスコアリングする

    Args:
        job: 案件情報の辞書

    Returns:
        スコアリング結果を追加した辞書
    """
    job_text = f"""
タイトル: {job.get('title', '')}
企業名: {job.get('company', '')}
勤務地: {job.get('location', '')}
給与: {job.get('salary_text', '記載なし')}
雇用形態: {job.get('job_type', '')}
リモート: {'可' if job.get('is_remote') else '不明'}
業務委託: {'あり' if job.get('is_freelance') else 'なし'}
業務内容:
{job.get('description', '詳細なし')}
"""

    user_prompt = f"""
以下の求人案件を評価してください。

{job_text}

以下のJSON形式で回答してください（他のテキストは不要）:
{{
  "score": 0〜100の整数,
  "category": "案件カテゴリ（SNS運用/動画制作/広告運用/コンテンツ制作/マーケティング/その他）",
  "reason": "スコアの理由（100文字以内）",
  "proposal_hint": "業務委託提案のポイント（アルバイト求人の場合のみ、50文字以内。業務委託案件の場合は空文字）",
  "is_recommended": true or false
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        job["ai_score"] = float(result.get("score", 0))
        job["ai_reason"] = result.get("reason", "")
        job["ai_proposal_hint"] = result.get("proposal_hint", "")
        job["ai_category"] = result.get("category", "その他")

        logger.info(
            f"[AI] '{job['title'][:40]}' -> Score: {job['ai_score']} / {job['ai_category']}"
        )

    except json.JSONDecodeError as e:
        logger.error(f"[AI] JSON parse error: {e}")
        job["ai_score"] = 0
        job["ai_reason"] = "スコアリングエラー"
        job["ai_proposal_hint"] = ""
        job["ai_category"] = "エラー"

    except Exception as e:
        logger.error(f"[AI] Scoring error for '{job.get('title', '')}': {e}")
        job["ai_score"] = 0
        job["ai_reason"] = f"エラー: {str(e)[:50]}"
        job["ai_proposal_hint"] = ""
        job["ai_category"] = "エラー"

    return job


def score_jobs_batch(jobs: list[dict], delay: float = 0.5) -> list[dict]:
    """
    複数の案件をバッチでスコアリングする

    Args:
        jobs: 案件情報のリスト
        delay: APIコール間の待機秒数

    Returns:
        スコアリング済み案件のリスト
    """
    scored = []
    total = len(jobs)

    for i, job in enumerate(jobs):
        logger.info(f"[AI] Scoring {i+1}/{total}: {job.get('title', '')[:50]}")
        scored_job = score_job(job)
        scored.append(scored_job)

        # APIレート制限対策
        if i < total - 1:
            time.sleep(delay)

    # スコア降順でソート
    scored.sort(key=lambda x: x.get("ai_score", 0), reverse=True)
    return scored


def filter_recommended(jobs: list[dict], min_score: int = None) -> list[dict]:
    """
    推奨案件のみをフィルタリングする

    Args:
        jobs: スコアリング済み案件のリスト
        min_score: 最低スコア（Noneの場合は環境変数から取得）

    Returns:
        フィルタリングされた案件のリスト
    """
    threshold = min_score if min_score is not None else MIN_SCORE
    return [j for j in jobs if j.get("ai_score", 0) >= threshold]
