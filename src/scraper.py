"""
案件スクレイピングエンジン
クラウドワークス・ランサーズから業務委託案件を収集する

対応プラットフォーム:
1. クラウドワークス (crowdworks.jp) - HTMLにJSONデータ埋め込み形式
2. ランサーズ (lancers.jp) - HTML解析

注意: Indeed.comはCloudflare Bot対策により直接アクセス不可のため、
      上記の代替プラットフォームを使用する。
"""
import os
import re
import time
import random
import logging
import hashlib
import json
import html
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DELAY = float(os.getenv("SCRAPE_DELAY_SECONDS", "2"))
MAX_JOBS = int(os.getenv("MAX_JOBS_PER_RUN", "100"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def _make_job_id(platform: str, job_id: str) -> str:
    return f"{platform}_{job_id}"


def _extract_salary(text: str) -> tuple[Optional[float], Optional[float]]:
    """給与テキストから時給の最小・最大値を抽出する"""
    if not text:
        return None, None

    hourly_patterns = [
        r'時給\s*([0-9,，]+)\s*(?:〜|～|-|–|~)\s*([0-9,，]+)\s*円?',
        r'時給\s*([0-9,，]+)\s*円',
        r'([0-9,，]+)\s*円\s*/\s*時',
    ]
    for pat in hourly_patterns:
        match = re.search(pat, text)
        if match:
            min_val = float(match.group(1).replace(",", "").replace("，", ""))
            max_str = match.group(2).replace(",", "").replace("，", "") if len(match.groups()) > 1 and match.group(2) else ""
            max_val = float(max_str) if max_str else min_val
            return min_val, max_val

    monthly_pattern = r'月(?:給|収|額)\s*([0-9,，]+)\s*(?:〜|～|-|–|~)?\s*([0-9,，]*)\s*万?円?'
    match = re.search(monthly_pattern, text)
    if match:
        min_val = float(match.group(1).replace(",", "").replace("，", ""))
        if min_val < 1000:
            min_val *= 10000
        return round(min_val / 160, 0), None

    return None, None


def _is_remote(text: str) -> bool:
    remote_keywords = ["リモート", "テレワーク", "在宅", "フルリモート", "完全在宅", "remote", "在宅OK", "在宅可"]
    return any(kw.lower() in text.lower() for kw in remote_keywords)


def _is_freelance(text: str) -> bool:
    freelance_keywords = ["業務委託", "フリーランス", "freelance", "業務請負", "外注", "委託", "完全歩合"]
    return any(kw.lower() in text.lower() for kw in freelance_keywords)


# ============================================================
# クラウドワークス スクレイパー
# ============================================================

def scrape_crowdworks(keyword: str, max_pages: int = 3) -> list[dict]:
    """
    クラウドワークスから案件を収集する
    HTMLにJSONデータが埋め込まれているため、それを解析する
    """
    jobs = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for page in range(1, max_pages + 1):
        url = (
            f"https://crowdworks.jp/public/jobs/search"
            f"?keep_search_condition=1&order=new"
            f"&search[job_type]=2"  # 2=プロジェクト（業務委託）
            f"&search[keywords]={quote_plus(keyword)}"
            f"&page={page}"
        )

        try:
            r = session.get(url, timeout=15)
            if r.status_code != 200:
                logger.warning(f"[CW] HTTP {r.status_code} for page {page}")
                break

            # HTMLからJSONデータを抽出
            json_match = re.search(
                r'<div[^>]+id="vue-container"[^>]+data="([^"]+)"',
                r.text
            )
            if not json_match:
                json_match = re.search(
                    r'id="vue-container"\s+data="([^"]+)"',
                    r.text
                )
            if not json_match:
                logger.warning(f"[CW] No JSON data found on page {page}")
                break

            json_str = html.unescape(json_match.group(1))
            data = json.loads(json_str)

            # 案件リストを取得
            job_list = []
            search_result = data.get("searchResult", {})
            if isinstance(search_result, dict):
                job_list = search_result.get("job_offers", [])
            if not job_list:
                for key in ["jobSearch", "search", "jobOffers", "job_offers", "jobs", "results"]:
                    candidate = data.get(key, {})
                    if isinstance(candidate, list):
                        job_list = candidate
                        break
                    elif isinstance(candidate, dict):
                        job_list = candidate.get("job_offers", [])
                        if job_list:
                            break

            if not job_list:
                logger.warning(f"[CW] No jobs in JSON data on page {page}")
                break

            logger.info(f"[CW] Page {page}: {len(job_list)} jobs found")

            for item in job_list:
                job_offer = item.get("job_offer", item)
                payment = item.get("payment", {})

                job_id = str(job_offer.get("id", ""))
                title = job_offer.get("title", "")
                description = job_offer.get("description_digest", "")

                # 予算情報
                salary_text = ""
                salary_min = None
                salary_max = None

                fixed = payment.get("fixed_price_payment", {})
                hourly = payment.get("hourly_payment", {})

                if hourly:
                    min_h = hourly.get("min_hourly_pay") or 0
                    max_h = hourly.get("max_hourly_pay") or 0
                    if min_h:
                        salary_text = f"時給 {int(min_h):,}円〜{int(max_h):,}円" if max_h and max_h != min_h else f"時給 {int(min_h):,}円"
                        salary_min = float(min_h)
                        salary_max = float(max_h) if max_h else float(min_h)
                elif fixed:
                    min_b = fixed.get("min_budget") or 0
                    max_b = fixed.get("max_budget") or 0
                    if max_b and max_b > 0:
                        if min_b and min_b > 0:
                            salary_text = f"固定 {int(min_b):,}円〜{int(max_b):,}円"
                        else:
                            salary_text = f"固定 {int(max_b):,}円"

                job_url = f"https://crowdworks.jp/public/jobs/{job_id}"

                jobs.append({
                    "job_id": _make_job_id("cw", job_id),
                    "title": title,
                    "company": item.get("client", {}).get("username", ""),
                    "location": "リモート可",
                    "salary_text": salary_text,
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "job_type": "業務委託",
                    "description": description[:2000],
                    "url": job_url,
                    "is_remote": True,
                    "is_freelance": True,
                    "can_propose_freelance": False,
                    "search_keyword": keyword,
                    "platform": "crowdworks",
                })

            time.sleep(random.uniform(DELAY, DELAY + 1))

        except json.JSONDecodeError as e:
            logger.error(f"[CW] JSON parse error on page {page}: {e}")
            break
        except requests.RequestException as e:
            logger.error(f"[CW] Request error on page {page}: {e}")
            break
        except Exception as e:
            logger.error(f"[CW] Unexpected error on page {page}: {e}", exc_info=True)
            break

    return jobs


# ============================================================
# ランサーズ スクレイパー
# ============================================================

def scrape_lancers(keyword: str, max_pages: int = 2) -> list[dict]:
    """
    ランサーズから案件を収集する
    """
    jobs = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for page in range(1, max_pages + 1):
        url = (
            f"https://www.lancers.jp/work/search"
            f"?keyword={quote_plus(keyword)}"
            f"&work_type[]=1"  # 1=プロジェクト
            f"&open=1"
            f"&page={page}"
        )

        try:
            r = session.get(url, timeout=15)
            if r.status_code != 200:
                logger.warning(f"[Lancers] HTTP {r.status_code}")
                break

            soup = BeautifulSoup(r.text, "html.parser")

            # 案件カードを取得（複数セレクタを試す）
            job_cards = soup.select(".p-search-result__item")
            if not job_cards:
                job_cards = soup.select(".work-list-item")
            if not job_cards:
                job_cards = soup.select("article.c-work-card")
            if not job_cards:
                job_cards = soup.select("li[class*='work']")

            logger.info(f"[Lancers] Page {page}: {len(job_cards)} cards found")

            if not job_cards:
                # JSON-LD形式のデータを試す
                scripts = soup.select("script[type='application/ld+json']")
                for script in scripts:
                    try:
                        ld_data = json.loads(script.string)
                        if isinstance(ld_data, list):
                            for item in ld_data:
                                if item.get("@type") == "JobPosting":
                                    title = item.get("title", "")
                                    href = item.get("url", "")
                                    salary_text = ""
                                    salary_info = item.get("baseSalary", {})
                                    if salary_info:
                                        val = salary_info.get("value", {})
                                        if val:
                                            salary_text = f"{val.get('minValue', '')}〜{val.get('maxValue', '')}円"
                                    job_id_match = re.search(r'/work/detail/(\d+)', href)
                                    job_id = job_id_match.group(1) if job_id_match else hashlib.md5(href.encode()).hexdigest()[:10]
                                    jobs.append({
                                        "job_id": _make_job_id("lancers", job_id),
                                        "title": title,
                                        "company": "",
                                        "location": "リモート可",
                                        "salary_text": salary_text,
                                        "salary_min": None,
                                        "salary_max": None,
                                        "job_type": "業務委託",
                                        "description": item.get("description", "")[:500],
                                        "url": href,
                                        "is_remote": True,
                                        "is_freelance": True,
                                        "can_propose_freelance": False,
                                        "search_keyword": keyword,
                                        "platform": "lancers",
                                    })
                    except Exception:
                        pass
                break

            for card in job_cards:
                title_el = card.select_one("h3 a, h2 a, .work-title a, a[class*='title']")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                if href and not href.startswith("http"):
                    href = "https://www.lancers.jp" + href

                # 予算
                budget_el = card.select_one(".work-budget, .budget, [class*='budget'], [class*='price']")
                salary_text = budget_el.get_text(strip=True) if budget_el else ""

                # 説明
                desc_el = card.select_one(".work-description, .description, p")
                description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                job_id_match = re.search(r'/work/detail/(\d+)', href)
                job_id = job_id_match.group(1) if job_id_match else hashlib.md5(href.encode()).hexdigest()[:10]

                salary_min, salary_max = _extract_salary(salary_text)

                jobs.append({
                    "job_id": _make_job_id("lancers", job_id),
                    "title": title,
                    "company": "",
                    "location": "リモート可",
                    "salary_text": salary_text,
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "job_type": "業務委託",
                    "description": description,
                    "url": href,
                    "is_remote": True,
                    "is_freelance": True,
                    "can_propose_freelance": False,
                    "search_keyword": keyword,
                    "platform": "lancers",
                })

            time.sleep(random.uniform(DELAY, DELAY + 1))

        except requests.RequestException as e:
            logger.error(f"[Lancers] Request error on page {page}: {e}")
            break
        except Exception as e:
            logger.error(f"[Lancers] Unexpected error on page {page}: {e}", exc_info=True)
            break

    return jobs


# ============================================================
# メイン収集関数
# ============================================================

def scrape_indeed(queries: list[dict]) -> list[dict]:
    """
    クラウドワークス・ランサーズから案件情報を収集する
    （関数名はシステム互換性のためscrape_indeedのまま維持）

    Args:
        queries: [{"keyword": "SNS運用 業務委託", "location": ""}, ...]

    Returns:
        案件情報のリスト
    """
    all_jobs = []
    seen_ids = set()

    for query in queries:
        if len(all_jobs) >= MAX_JOBS:
            break

        keyword = query["keyword"]
        logger.info(f"[Scraper] Searching: '{keyword}'")

        # クラウドワークス
        try:
            cw_jobs = scrape_crowdworks(keyword, max_pages=2)
            for job in cw_jobs:
                if job["job_id"] not in seen_ids and len(all_jobs) < MAX_JOBS:
                    seen_ids.add(job["job_id"])
                    all_jobs.append(job)
            logger.info(f"[Scraper] CrowdWorks: {len(cw_jobs)} jobs for '{keyword}'")
        except Exception as e:
            logger.error(f"[Scraper] CrowdWorks error: {e}")

        time.sleep(random.uniform(1, 2))

        # ランサーズ（業務委託・フリーランス・リモート系キーワードのみ）
        if any(kw in keyword for kw in ["業務委託", "フリーランス", "リモート", "SNS", "広告", "動画", "マーケティング"]):
            try:
                lancers_keyword = keyword.replace("業務委託", "").replace("フリーランス", "").strip()
                lancers_jobs = scrape_lancers(lancers_keyword, max_pages=1)
                for job in lancers_jobs:
                    if job["job_id"] not in seen_ids and len(all_jobs) < MAX_JOBS:
                        seen_ids.add(job["job_id"])
                        all_jobs.append(job)
                logger.info(f"[Scraper] Lancers: {len(lancers_jobs)} jobs for '{lancers_keyword}'")
            except Exception as e:
                logger.error(f"[Scraper] Lancers error: {e}")

            time.sleep(random.uniform(1, 2))

    logger.info(f"[Scraper] Total jobs collected: {len(all_jobs)}")
    return all_jobs
