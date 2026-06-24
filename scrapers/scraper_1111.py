"""
1111 人力銀行職缺爬蟲（JSON API）

公開 API（前端使用，無反爬蟲）：
  GET https://www.1111.com.tw/api/v1/search/jobs?keyword=<關鍵字>&page=<頁碼>
回傳 result.hits[]、result.pagination.{page,totalPage,totalCount}。

兩種用法：
  scrape_1111(keywords)         — 以關鍵字鎖定 AI／跨域職缺（次要來源）
  scrape_1111_baseline(n)       — 不帶關鍵字抓「全市場最新職缺」樣本，
                                  作為 AI 需求溫度計的「無偏市場基準」（不會顯示在職缺清單）
"""

import ssl
import requests
import time
import random
from typing import List, Dict
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context


API_URL = "https://www.1111.com.tw/api/v1/search/jobs"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.1111.com.tw/search/job",
}


class _RelaxedTLSAdapter(HTTPAdapter):
    """1111 憑證缺少 Subject Key Identifier，新版 OpenSSL 嚴格模式會拒絕。
    這裡關閉「嚴格 X509」旗標但仍驗證 CA 鏈，兼顧相容與安全。"""

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.mount("https://", _RelaxedTLSAdapter())
    return s


_SESSION = _session()


def scrape_1111(keywords: List[str], max_pages: int = 2) -> List[Dict]:
    """以關鍵字鎖定職缺（AI／跨域）。每頁約 40 筆。"""
    all_jobs = []
    for keyword in keywords:
        jobs = _fetch_1111(keyword=keyword, max_pages=max_pages)
        all_jobs.extend(jobs)
        time.sleep(random.uniform(0.8, 1.5))
    return all_jobs


def scrape_1111_baseline(max_records: int = 80) -> List[Dict]:
    """
    不帶關鍵字抓全市場最新職缺，作為「無偏市場基準」樣本。
    這些職缺只供 AI 需求溫度計計算用，會標記 is_baseline=True，不顯示於清單。
    """
    pages = max(1, (max_records + 39) // 40)
    jobs = _fetch_1111(keyword=None, max_pages=pages, is_baseline=True)
    return jobs[:max_records]


def _fetch_1111(keyword, max_pages: int, is_baseline: bool = False) -> List[Dict]:
    jobs = []
    for page in range(1, max_pages + 1):
        params = {"page": page}
        if keyword:
            params["keyword"] = keyword
        try:
            resp = _SESSION.get(API_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            tag = "baseline" if is_baseline else keyword
            print(f"[1111] 抓取失敗（{tag}，第 {page} 頁）：{e}")
            break

        result = data.get("result", {})
        hits = result.get("hits", [])
        if not hits:
            break

        for h in hits:
            jobs.append(_normalize_1111(h, keyword or "", is_baseline))

        pagination = result.get("pagination", {})
        if page >= pagination.get("totalPage", page):
            break
        time.sleep(random.uniform(0.5, 1.0))

    return jobs


def _normalize_1111(h: Dict, keyword: str, is_baseline: bool) -> Dict:
    job_id = h.get("jobId", "")
    work_city = h.get("workCity", {}) or {}
    industry = h.get("industry", {}) or {}
    return {
        "source": "1111",
        "job_id": str(job_id),
        "title": h.get("title", ""),
        "company": h.get("companyName", ""),
        "location": work_city.get("name", ""),
        "salary": h.get("salary", "面議") or "面議",
        "url": f"https://www.1111.com.tw/job/{job_id}",
        "date_posted": h.get("updateAt", ""),
        "description": (h.get("description", "") or "")[:1500],
        "industry": industry.get("name", ""),
        "keyword_matched": keyword,
        "is_baseline": is_baseline,
    }
