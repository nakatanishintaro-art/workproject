"""
自社プロフィール設定
AIマッチングスコアリングのベースとなる自社の強み・スキルセットを定義する
ポートフォリオ（SHINONOME Co.,Ltd.）の内容に基づいて設定
"""

COMPANY_PROFILE = {
    "name": "SHINONOME Co.,Ltd.",
    "description": """
    SNS・Web広告運用、動画・コンテンツ制作、写真撮影、
    自治体向けプロモーション、補助金申請支援の5領域でワンストップ対応できる
    クリエイティブ＆マーケティング会社。
    """,
    "skills": [
        "SNS運用（Instagram, X(Twitter), TikTok, Facebook, YouTube）",
        "Meta広告（Facebook/Instagram広告）運用・クリエイティブ制作",
        "Google広告（検索/ディスプレイ/YouTube）運用",
        "動画制作・編集（リール、ショート動画、プロモーション動画）",
        "写真撮影・フォトディレクション",
        "コンテンツマーケティング・ライティング",
        "自治体向けシティプロモーション",
        "インバウンド向けプロモーション",
        "補助金申請支援・コンサルティング",
        "ブランディング・クリエイティブディレクション",
        "Webサイト制作・LP制作",
        "インフルエンサーマーケティング",
        "PR・広報支援",
    ],
    "strengths": [
        "自治体・官公庁との取引実績あり",
        "SNS運用から広告運用まで一気通貫で対応可能",
        "動画制作とSNS運用を組み合わせたトータルプロデュース",
        "フルリモートでの業務対応が可能",
        "補助金活用による顧客の初期コスト削減提案が可能",
    ],
    "preferred_budget_hourly_min": 3000,  # 希望最低時給（円）
    "preferred_work_style": "フルリモート",
    "ng_keywords": [
        "正社員", "新卒", "転職", "社員", "入社", "出社必須",
        "工場", "製造", "建設", "介護", "医療", "看護",
        "ドライバー", "配送", "警備",
    ],
}

# Indeed検索キーワード設定
SEARCH_QUERIES = [
    # 業務委託・フリーランス直接検索
    {"keyword": "SNS運用 業務委託", "location": ""},
    {"keyword": "広告運用 業務委託 リモート", "location": ""},
    {"keyword": "動画制作 業務委託 リモート", "location": ""},
    {"keyword": "コンテンツ制作 業務委託", "location": ""},
    {"keyword": "マーケティング 業務委託 フルリモート", "location": ""},
    {"keyword": "SNSマーケティング フリーランス", "location": ""},
    {"keyword": "Instagram運用 業務委託", "location": ""},
    {"keyword": "Web広告 業務委託 リモート", "location": ""},
    # アルバイト求人（業務委託提案候補）
    {"keyword": "SNS運用 アルバイト リモート", "location": ""},
    {"keyword": "動画編集 アルバイト リモート", "location": ""},
    {"keyword": "広告運用 アルバイト", "location": ""},
    {"keyword": "コンテンツ制作 パート リモート", "location": ""},
    {"keyword": "Webマーケティング アルバイト", "location": ""},
]
