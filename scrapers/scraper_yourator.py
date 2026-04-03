"""
Yourator 職缺爬蟲

爬取 https://www.yourator.co/jobs
使用 requests + BeautifulSoup 解析搜尋結果頁面。
"""

import requests
from bs4 import BeautifulSoup
import time
import random
from typing import List, Dict


def scrape_yourator(
    keywords: List[str],
    max_pages: int = 2
) -> List[Dict]:
    """
    爬取 Yourator 職缺

    Args:
        keywords: 搜尋關鍵字列表
        max_pages: 每個關鍵字最多爬幾頁

    Returns:
        標準化職缺列表
    """
    all_jobs = []

    for keyword in keywords:
        jobs = _fetch_keyword_yourator(keyword, max_pages)
        all_jobs.extend(jobs)
        time.sleep(random.uniform(2, 4))

    return all_jobs


def _fetch_keyword_yourator(keyword: str, max_pages: int) -> List[Dict]:
    """單一關鍵字的 Yourator 爬取（HTML 頁面解析）"""
    base_url = "https://www.yourator.co/jobs"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"
    }

    jobs = []

    for page in range(1, max_pages + 1):
        params = {
            "q": keyword,
            "page": page
        }

        try:
            resp = requests.get(base_url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Yourator 職缺卡片 — 嘗試多種選擇器
            job_cards = (
                soup.select("div.y-new-jobcard") or
                soup.select("a[href*='/companies/'][href*='/jobs/']") or
                soup.select("div[class*='job']")
            )

            if not job_cards:
                break

            for card in job_cards:
                try:
                    # 標題
                    title_el = card.select_one("h3, h2, [class*='title'], [class*='name']")
                    title = title_el.get_text(strip=True) if title_el else ""

                    # 公司
                    company_el = card.select_one("[class*='company'], [class*='brand'], span.company-name")
                    company = company_el.get_text(strip=True) if company_el else ""

                    # 連結
                    link_el = card if card.name == "a" else card.select_one("a[href]")
                    link = link_el.get("href", "") if link_el else ""
                    if link and not link.startswith("http"):
                        link = f"https://www.yourator.co{link}"

                    if title:
                        jobs.append({
                            "source": "Yourator",
                            "job_id": link.split("/")[-1] if link else "",
                            "title": title,
                            "company": company,
                            "location": "",
                            "salary": "面議",
                            "url": link,
                            "date_posted": "",
                            "description": "",
                            "keyword_matched": keyword
                        })

                except Exception:
                    continue

        except Exception as e:
            print(f"[Yourator] 爬取失敗（第 {page} 頁，關鍵字：{keyword}）：{e}")
            break

        time.sleep(random.uniform(1, 3))

    return jobs
