"""
Yourator 職缺爬蟲（改用官方 JSON API）

Yourator 前端呼叫的公開 API：
  GET https://www.yourator.co/api/v4/jobs?term[search]=<關鍵字>&page=<頁碼>
回傳 JSON：payload.jobs[]，payload.hasMore / payload.nextPage 供分頁。
無反爬蟲、無需登入，適合在 GitHub Actions 上執行。
"""

import requests
import time
import random
from typing import List, Dict


API_URL = "https://www.yourator.co/api/v4/jobs"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.yourator.co/jobs",
}


def scrape_yourator(keywords: List[str], max_pages: int = 3) -> List[Dict]:
    """
    爬取 Yourator 職缺（新創／科技為主，含大量跨領域職位）

    Args:
        keywords: 搜尋關鍵字列表
        max_pages: 每個關鍵字最多抓幾頁（每頁約 20 筆）

    Returns:
        標準化職缺列表
    """
    all_jobs = []
    for keyword in keywords:
        jobs = _fetch_keyword_yourator(keyword, max_pages)
        all_jobs.extend(jobs)
        time.sleep(random.uniform(1, 2))
    return all_jobs


def _fetch_keyword_yourator(keyword: str, max_pages: int) -> List[Dict]:
    """單一關鍵字的 Yourator API 抓取"""
    jobs = []
    page = 1

    while page <= max_pages:
        params = {"term[search]": keyword, "page": page}
        try:
            resp = requests.get(API_URL, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[Yourator] 抓取失敗（關鍵字：{keyword}，第 {page} 頁）：{e}")
            break

        payload = data.get("payload", {})
        job_list = payload.get("jobs", [])
        if not job_list:
            break

        for job in job_list:
            jobs.append(_normalize_yourator_job(job, keyword))

        if not payload.get("hasMore"):
            break
        page = payload.get("nextPage") or (page + 1)
        time.sleep(random.uniform(0.6, 1.2))

    return jobs


def _normalize_yourator_job(job: Dict, keyword: str) -> Dict:
    """將 Yourator API 物件轉成標準化欄位"""
    path = job.get("path", "")
    url = f"https://www.yourator.co{path}" if path.startswith("/") else (path or "")
    company = job.get("company", {}) or {}

    return {
        "source": "Yourator",
        "job_id": str(job.get("id", "")),
        "title": job.get("name", ""),
        "company": company.get("brand", "") or company.get("enName", ""),
        "location": job.get("location", ""),
        "salary": job.get("salary", "面議") or "面議",
        "url": url,
        "date_posted": job.get("lastActiveAt", ""),
        "description": "",
        "keyword_matched": keyword,
    }
