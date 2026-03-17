"""
データベース設定・モデル定義
SQLAlchemy + SQLite を使用
"""
import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text,
    Float, DateTime, Boolean, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_PATH = os.getenv("DB_PATH", "./data/jobs.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Job(Base):
    """Indeed案件テーブル"""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(100), nullable=False, comment="Indeed固有のジョブID")
    title = Column(String(500), nullable=False, comment="求人タイトル")
    company = Column(String(300), comment="企業名")
    location = Column(String(200), comment="勤務地")
    salary_text = Column(String(300), comment="給与テキスト（生テキスト）")
    salary_min = Column(Float, comment="最低時給（円）")
    salary_max = Column(Float, comment="最高時給（円）")
    job_type = Column(String(100), comment="雇用形態（アルバイト/業務委託など）")
    description = Column(Text, comment="求人詳細テキスト")
    url = Column(String(1000), comment="求人URL")
    is_remote = Column(Boolean, default=False, comment="リモート可フラグ")
    is_freelance = Column(Boolean, default=False, comment="業務委託フラグ")
    can_propose_freelance = Column(Boolean, default=False, comment="業務委託提案可能フラグ（アルバイト求人への提案候補）")

    # AIスコアリング結果
    ai_score = Column(Float, comment="AIマッチングスコア (0-100)")
    ai_reason = Column(Text, comment="AIによるスコアリング理由")
    ai_proposal_hint = Column(Text, comment="AIによる提案文ヒント")
    ai_category = Column(String(100), comment="案件カテゴリ（SNS運用/動画制作/広告運用など）")

    # メタデータ
    scraped_at = Column(DateTime, default=datetime.utcnow, comment="収集日時")
    notified = Column(Boolean, default=False, comment="通知済みフラグ")
    is_active = Column(Boolean, default=True, comment="有効フラグ")

    __table_args__ = (
        UniqueConstraint("job_id", name="uq_job_id"),
    )

    def __repr__(self):
        return f"<Job id={self.id} title='{self.title[:30]}' score={self.ai_score}>"


class RunLog(Base):
    """実行ログテーブル"""
    __tablename__ = "run_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_at = Column(DateTime, default=datetime.utcnow)
    jobs_scraped = Column(Integer, default=0, comment="収集件数")
    jobs_new = Column(Integer, default=0, comment="新規件数")
    jobs_notified = Column(Integer, default=0, comment="通知件数")
    status = Column(String(50), default="success", comment="実行ステータス")
    error_message = Column(Text, comment="エラーメッセージ")


def init_db():
    """データベースとテーブルを初期化する"""
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    Base.metadata.create_all(engine)
    print(f"[DB] Database initialized at {DB_PATH}")


def get_session():
    """DBセッションを取得する"""
    return SessionLocal()
