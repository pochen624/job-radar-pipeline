"""
Cake（原 CakeResume）職缺爬蟲

Cake 已從 cakeresume.com 改名為 cake.me，搜尋頁改為「路徑帶關鍵字」：
  https://www.cake.me/jobs/<關鍵字>?page=<頁碼>
職缺卡片由伺服器端（SSR）直接渲染在 HTML 中，雖然搜尋結果由 Algolia 提供，
但首屏 HTML 已含完整職缺清單，故用 requests + BeautifulSoup 解析即可，無需 Algolia 金鑰。

（舊版爬蟲失敗原因：打到舊網域 cakeresume.com 並用 ?q= 參數，會被導向而抓不到卡片。）
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import re
import time
import random
from typing import List, Dict


BASE = "https://www.cake.me/jobs"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

# /companies/<公司>/jobs/<id...> 的職缺連結
JOB_HREF_RE = re.compile(r"^/companies/([^/]+)/jobs/")


def scrape_cakeresume(keywords: List[str], max_pages: int = 2) -> List[Dict]:
    """
    爬取 Cake 職缺（台灣最大的新創／科技求職平台，跨領域職位多）

    Args:
        keywords: 搜尋關鍵字列表
        max_pages: 每個關鍵字最多抓幾頁

    Returns:
        標準化職缺列表
    """
    all_jobs = []
    for keyword in keywords:
        jobs = _fetch_keyword_cake(keyword, max_pages)
        all_jobs.extend(jobs)
        time.sleep(random.uniform(1.5, 3))
    return all_jobs


def _fetch_keyword_cake(keyword: str, max_pages: int) -> List[Dict]:
    """單一關鍵字的 Cake 抓取（解析 SSR HTML 卡片）"""
    jobs = []
    seen = set()

    for page in range(1, max_pages + 1):
        url = f"{BASE}/{quote(keyword)}"
        params = {"page": page} if page > 1 else None
        try:
            resp = requests.get(url, headers=HEADERS, params=params,
                                timeout=20, allow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            print(f"[Cake] 抓取失敗（關鍵字：{keyword}，第 {page} 頁）：{e}")
            break

        # 優先抓職缺卡片容器，取不到再退回全頁的職缺連結
        cards = soup.select("[class*='JobSearchItem']")
        page_jobs = _parse_cards(cards, keyword, seen) if cards else \
            _parse_anchors(soup, keyword, seen)

        if not page_jobs:
            break
        jobs.extend(page_jobs)
        time.sleep(random.uniform(0.8, 1.6))

    return jobs


def _parse_cards(cards, keyword: str, seen: set) -> List[Dict]:
    """從職缺卡片容器解析（較精準，可取得公司/地點）"""
    out = []
    for card in cards:
        job_link = None
        for a in card.select("a[href]"):
            if JOB_HREF_RE.match(a.get("href", "")):
                job_link = a
                break
        if not job_link:
            continue

        href = job_link.get("href", "")
        if href in seen:
            continue
        title = job_link.get_text(strip=True)
        if not title:
            continue
        seen.add(href)

        # 公司：卡片內 /companies/<slug> 但非 /jobs/ 的連結，取不到則用 slug
        company = ""
        for a in card.select("a[href^='/companies/']"):
            if "/jobs/" not in a.get("href", ""):
                txt = a.get_text(strip=True)
                if txt:
                    company = txt
                    break
        m = JOB_HREF_RE.match(href)
        if not company and m:
            company = m.group(1)

        out.append(_build_job(href, title, company, keyword))
    return out


def _parse_anchors(soup, keyword: str, seen: set) -> List[Dict]:
    """退回方案：直接掃全頁的職缺連結"""
    out = []
    for a in soup.select("a[href*='/jobs/']"):
        href = a.get("href", "")
        if not JOB_HREF_RE.match(href) or href in seen:
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 2:
            continue
        seen.add(href)
        company = JOB_HREF_RE.match(href).group(1)
        out.append(_build_job(href, title, company, keyword))
    return out


def _build_job(href: str, title: str, company: str, keyword: str) -> Dict:
    url = f"https://www.cake.me{href}"
    job_id = href.rstrip("/").split("/")[-1]
    return {
        "source": "CakeResume",
        "job_id": job_id,
        "title": title,
        "company": company,
        "location": "",
        "salary": "面議",
        "url": url,
        "date_posted": "",
        "description": "",
        "keyword_matched": keyword,
    }
