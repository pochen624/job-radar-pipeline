"""
CakeResume 職缺爬蟲

爬取 https://www.cakeresume.com/jobs
使用 requests + BeautifulSoup 解析搜尋結果頁面。
"""

import requests
from bs4 import BeautifulSoup
import time
import random
from typing import List, Dict


def scrape_cakeresume(
    keywords: List[str],
    max_pages: int = 2
) -> List[Dict]:
    """
    爬取 CakeResume 職缺

    Args:
        keywords: 搜尋關鍵字列表
        max_pages: 每個關鍵字最多爬幾頁

    Returns:
        標準化職缺列表
    """
    all_jobs = []

    for keyword in keywords:
        jobs = _fetch_keyword_cake(keyword, max_pages)
        all_jobs.extend(jobs)
        time.sleep(random.uniform(2, 4))

    return all_jobs


def _fetch_keyword_cake(keyword: str, max_pages: int) -> List[Dict]:
    """單一關鍵字的 CakeResume 爬取"""
    base_url = "https://www.cakeresume.com/jobs"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"
    }

    jobs = []

    for page in range(1, max_pages + 1):
        params = {
            "q": keyword,
            "page": page
        }

        try:
            resp = requests.get(base_url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # CakeResume 職缺卡片
            job_cards = soup.select("a[class*='JobSearchItem']")

            if not job_cards:
                # 嘗試其他可能的選擇器
                job_cards = soup.select("div[class*='job-item'], div[class*='JobItem']")

            if not job_cards:
                break

            for card in job_cards:
                try:
                    # 職缺標題
                    title_el = card.select_one("h2, h3, [class*='title'], [class*='Title']")
                    title = title_el.get_text(strip=True) if title_el else ""

                    # 公司名
                    company_el = card.select_one("[class*='company'], [class*='Company']")
                    company = company_el.get_text(strip=True) if company_el else ""

                    # 連結
                    link = card.get("href", "")
                    if link and not link.startswith("http"):
                        link = f"https://www.cakeresume.com{link}"

                    # 地點
                    location_el = card.select_one("[class*='location'], [class*='Location']")
                    location = location_el.get_text(strip=True) if location_el else ""

                    # 薪資
                    salary_el = card.select_one("[class*='salary'], [class*='Salary']")
                    salary = salary_el.get_text(strip=True) if salary_el else "面議"

                    if title and company:
                        jobs.append({
                            "source": "CakeResume",
                            "job_id": link.split("/")[-1] if link else "",
                            "title": title,
                            "company": company,
                            "location": location,
                            "salary": salary,
                            "url": link,
                            "date_posted": "",
                            "description": "",
                            "keyword_matched": keyword
                        })

                except Exception:
                    continue

        except Exception as e:
            print(f"[CakeResume] 爬取失敗（第 {page} 頁，關鍵字：{keyword}）：{e}")
            break

        time.sleep(random.uniform(1, 3))

    return jobs
