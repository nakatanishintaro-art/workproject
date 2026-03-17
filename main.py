"""
Indeed案件自動収集・AIマッチングシステム
メインエントリーポイント

使い方:
    # 通常実行（全工程）
    python3.11 main.py

    # テストモード（スクレイピングをスキップ、サンプルデータで動作確認）
    python3.11 main.py --test

    # スコアのみ再計算（既存データを再スコアリング）
    python3.11 main.py --rescore

    # 通知のみ（既存のスコア済みデータを通知）
    python3.11 main.py --notify-only
"""
import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .env ファイルを読み込む
load_dotenv()

# ログ設定
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f"logs/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger(__name__)

from src.database import init_db, get_session, Job, RunLog
from src.scraper import scrape_indeed
from src.ai_scorer import score_jobs_batch, filter_recommended
from src.notifier import send_slack_notification, print_report
from src.company_profile import SEARCH_QUERIES


def save_jobs_to_db(jobs: list[dict], session) -> tuple[int, int]:
    """
    案件をDBに保存する（重複スキップ）

    Returns:
        (保存件数, 新規件数)
    """
    saved = 0
    new_count = 0

    for job_data in jobs:
        # 既存チェック
        existing = session.query(Job).filter_by(job_id=job_data["job_id"]).first()
        if existing:
            # 既存案件はスコアのみ更新
            if job_data.get("ai_score") and not existing.ai_score:
                existing.ai_score = job_data.get("ai_score")
                existing.ai_reason = job_data.get("ai_reason")
                existing.ai_proposal_hint = job_data.get("ai_proposal_hint")
                existing.ai_category = job_data.get("ai_category")
                session.commit()
            continue

        # 新規保存
        job = Job(
            job_id=job_data["job_id"],
            title=job_data.get("title", ""),
            company=job_data.get("company", ""),
            location=job_data.get("location", ""),
            salary_text=job_data.get("salary_text", ""),
            salary_min=job_data.get("salary_min"),
            salary_max=job_data.get("salary_max"),
            job_type=job_data.get("job_type", ""),
            description=job_data.get("description", ""),
            url=job_data.get("url", ""),
            is_remote=job_data.get("is_remote", False),
            is_freelance=job_data.get("is_freelance", False),
            can_propose_freelance=job_data.get("can_propose_freelance", False),
            ai_score=job_data.get("ai_score"),
            ai_reason=job_data.get("ai_reason"),
            ai_proposal_hint=job_data.get("ai_proposal_hint"),
            ai_category=job_data.get("ai_category"),
        )
        session.add(job)
        saved += 1
        new_count += 1

    session.commit()
    return saved, new_count


def get_unnotified_jobs(session, min_score: float = 60) -> list[dict]:
    """未通知の推奨案件を取得する"""
    jobs = (
        session.query(Job)
        .filter(
            Job.ai_score >= min_score,
            Job.notified == False,
            Job.is_active == True,
        )
        .order_by(Job.ai_score.desc())
        .all()
    )
    return [
        {
            "job_id": j.job_id,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "salary_text": j.salary_text,
            "job_type": j.job_type,
            "url": j.url,
            "is_remote": j.is_remote,
            "is_freelance": j.is_freelance,
            "can_propose_freelance": j.can_propose_freelance,
            "ai_score": j.ai_score,
            "ai_reason": j.ai_reason,
            "ai_proposal_hint": j.ai_proposal_hint,
            "ai_category": j.ai_category,
        }
        for j in jobs
    ]


def mark_as_notified(session, job_ids: list[str]):
    """案件を通知済みにマークする"""
    session.query(Job).filter(Job.job_id.in_(job_ids)).update(
        {"notified": True}, synchronize_session=False
    )
    session.commit()


def run_test_mode():
    """テストモード: サンプルデータでAIスコアリングと通知をテストする"""
    logger.info("[Main] テストモードで実行中...")

    sample_jobs = [
        {
            "job_id": "test_001",
            "title": "SNS運用代行（Instagram/TikTok）業務委託",
            "company": "株式会社テスト",
            "location": "東京都",
            "salary_text": "時給 3,500円〜5,000円",
            "salary_min": 3500,
            "salary_max": 5000,
            "job_type": "業務委託",
            "description": "InstagramとTikTokのアカウント運用をお任せします。コンテンツ企画から投稿まで一括でお願いします。週10〜20時間程度。完全リモート。",
            "url": "https://jp.indeed.com/test001",
            "is_remote": True,
            "is_freelance": True,
            "can_propose_freelance": False,
        },
        {
            "job_id": "test_002",
            "title": "Web広告運用アシスタント（アルバイト・在宅可）",
            "company": "デジタルマーケ株式会社",
            "location": "在宅勤務",
            "salary_text": "時給 1,500円〜2,000円",
            "salary_min": 1500,
            "salary_max": 2000,
            "job_type": "アルバイト・パート",
            "description": "Google広告・Meta広告の運用補助。レポート作成、入稿作業など。在宅勤務可。週20時間程度。",
            "url": "https://jp.indeed.com/test002",
            "is_remote": True,
            "is_freelance": False,
            "can_propose_freelance": True,
        },
        {
            "job_id": "test_003",
            "title": "動画編集者募集（YouTube/リール）業務委託",
            "company": "クリエイティブ合同会社",
            "location": "フルリモート",
            "salary_text": "月額 150,000円〜300,000円",
            "salary_min": None,
            "salary_max": None,
            "job_type": "業務委託",
            "description": "YouTubeチャンネルとInstagramリールの動画編集をお願いします。月10〜20本程度。Adobe Premiere Pro使用。完全在宅。",
            "url": "https://jp.indeed.com/test003",
            "is_remote": True,
            "is_freelance": True,
            "can_propose_freelance": False,
        },
        {
            "job_id": "test_004",
            "title": "工場スタッフ（製造ライン）",
            "company": "製造株式会社",
            "location": "愛知県",
            "salary_text": "時給 1,200円",
            "salary_min": 1200,
            "salary_max": 1200,
            "job_type": "アルバイト・パート",
            "description": "自動車部品の製造ラインでの作業。立ち仕事あり。",
            "url": "https://jp.indeed.com/test004",
            "is_remote": False,
            "is_freelance": False,
            "can_propose_freelance": False,
        },
        {
            "job_id": "test_005",
            "title": "自治体向けプロモーション企画・SNS運用（業務委託）",
            "company": "地域活性化コンサル",
            "location": "リモート可",
            "salary_text": "時給 4,000円〜6,000円",
            "salary_min": 4000,
            "salary_max": 6000,
            "job_type": "業務委託",
            "description": "地方自治体のシティプロモーション支援。SNS運用、コンテンツ制作、広報戦略立案。移住促進・観光振興プロジェクト。フルリモート対応可。",
            "url": "https://jp.indeed.com/test005",
            "is_remote": True,
            "is_freelance": True,
            "can_propose_freelance": False,
        },
    ]

    logger.info(f"[Main] サンプル案件 {len(sample_jobs)}件 をAIスコアリング中...")
    scored_jobs = score_jobs_batch(sample_jobs)

    min_score = int(os.getenv("MIN_SCORE_TO_NOTIFY", "60"))
    recommended = filter_recommended(scored_jobs, min_score)

    logger.info(f"[Main] 推奨案件: {len(recommended)}件 (スコア{min_score}点以上)")

    # コンソールレポート
    print_report(recommended, len(sample_jobs), len(sample_jobs))

    # Slack通知（設定されている場合）
    if os.getenv("SLACK_WEBHOOK_URL"):
        send_slack_notification(recommended, len(sample_jobs), len(sample_jobs))

    return recommended


def run_full_pipeline():
    """フルパイプライン実行: スクレイピング → スコアリング → DB保存 → 通知"""
    logger.info("[Main] フルパイプライン開始")
    session = get_session()
    run_log = RunLog(run_at=datetime.utcnow())

    try:
        # 1. スクレイピング
        logger.info("[Main] Step 1: Indeed スクレイピング開始")
        raw_jobs = scrape_indeed(SEARCH_QUERIES)
        run_log.jobs_scraped = len(raw_jobs)
        logger.info(f"[Main] 収集完了: {len(raw_jobs)}件")

        if not raw_jobs:
            logger.warning("[Main] 案件が収集できませんでした。")
            run_log.status = "no_jobs"
            session.add(run_log)
            session.commit()
            return

        # 2. AIスコアリング
        logger.info("[Main] Step 2: AIスコアリング開始")
        scored_jobs = score_jobs_batch(raw_jobs)

        # 3. DB保存
        logger.info("[Main] Step 3: DB保存")
        saved, new_count = save_jobs_to_db(scored_jobs, session)
        run_log.jobs_new = new_count
        logger.info(f"[Main] DB保存完了: {saved}件保存 (新規: {new_count}件)")

        # 4. 通知対象案件を取得
        min_score = int(os.getenv("MIN_SCORE_TO_NOTIFY", "60"))
        recommended = get_unnotified_jobs(session, min_score)
        logger.info(f"[Main] 通知対象: {len(recommended)}件")

        # 5. レポート出力・通知
        print_report(recommended, len(raw_jobs), new_count)

        if os.getenv("SLACK_WEBHOOK_URL"):
            success = send_slack_notification(recommended, len(raw_jobs), new_count)
            if success:
                # 通知済みマーク
                mark_as_notified(session, [j["job_id"] for j in recommended])
                run_log.jobs_notified = len(recommended)

        run_log.status = "success"

    except Exception as e:
        logger.error(f"[Main] パイプラインエラー: {e}", exc_info=True)
        run_log.status = "error"
        run_log.error_message = str(e)

    finally:
        session.add(run_log)
        session.commit()
        session.close()
        logger.info("[Main] フルパイプライン完了")


def run_notify_only():
    """通知のみモード: 既存のスコア済みデータを通知する"""
    logger.info("[Main] 通知のみモードで実行中...")
    session = get_session()

    min_score = int(os.getenv("MIN_SCORE_TO_NOTIFY", "60"))
    recommended = get_unnotified_jobs(session, min_score)

    print_report(recommended, 0, 0)

    if os.getenv("SLACK_WEBHOOK_URL") and recommended:
        success = send_slack_notification(recommended, 0, 0)
        if success:
            mark_as_notified(session, [j["job_id"] for j in recommended])

    session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indeed案件自動収集・AIマッチングシステム")
    parser.add_argument("--test", action="store_true", help="テストモード（サンプルデータ使用）")
    parser.add_argument("--notify-only", action="store_true", help="通知のみ（既存データ使用）")
    parser.add_argument("--rescore", action="store_true", help="既存データを再スコアリング")
    args = parser.parse_args()

    # DBを初期化
    init_db()

    if args.test:
        run_test_mode()
    elif args.notify_only:
        run_notify_only()
    else:
        run_full_pipeline()
