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
    """單一關鍵字的 Yourator 爬取"""
    base_url = "https://www.yourator.co/api/v2/jobs"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"
    }

    jobs = []

    for page in range(1, max_pages + 1):
        params = {
            "term[]": keyword,
            "page": page
        }

        try:
            resp = requests.get(base_url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()

            # 嘗試 JSON API
            try:
                data = resp.json()
                job_list = data.get("jobs", data.get("data", []))

                if not job_list:
                    break

                for job in job_list:
                    title = job.get("name", job.get("title", ""))
                    company_data = job.get("company", {})
                    company = company_data.get("brand", company_data.get("name", "")) if isinstance(company_data, dict) else str(company_data)
                    job_path = job.get("path", job.get("url", ""))
                    url = f"https://www.yourator.co{job_path}" if job_path and not job_path.startswith("http") else job_path

                    if title:
                        jobs.append({
                            "source": "Yourator",
                            "job_id": str(job.get("id", "")),
                            "title": title,
                            "company": company,
                            "location": job.get("location", ""),
                            "salary": job.get("salary", "面議"),
                            "url": url,
                            "date_posted": job.get("created_at", ""),
                            "description": job.get("description", "")[:2000],
                            "keyword_matched": keyword
                        })

            except ValueError:
                # 如果不是 JSON，改用 HTML 解析
                jobs.extend(_parse_yourator_html(resp.text, keyword))

        except Exception as e:
            print(f"[Yourator] 爬取失敗（第 {page} 頁，關鍵字：{keyword}）：{e}")
            break

        time.sleep(random.uniform(1, 3))

    return jobs


def _parse_yourator_html(html: str, keyword: str) -> List[Dict]:
    """HTML 備用解析"""
    soup = BeautifulSoup(html, "lxml")
    jobs = []

    job_cards = soup.select("div.job-item, a.job-item, div[class*='JobItem']")

    for card in job_cards:
        try:
            title_el = card.select_one("h2, h3, [class*='title'], [class*='name']")
            title = title_el.get_text(strip=True) if title_el else ""

            company_el = card.select_one("[class*='company'], [class*='brand']")
            company = company_el.get_text(strip=True) if company_el else ""

            link = card.get("href", "")
            if not link:
                link_el = card.select_one("a[href]")
                link = link_el.get("href", "") if link_el else ""
            if link and not link.startswith("http"):
                link = f"https://www.yourator.co{link}"

            if title and company:
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

    return jobs
