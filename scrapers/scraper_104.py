"""
104人力銀行職缺爬蟲

透過直打 XHR API 取得結構化資料。
API Endpoint: https://www.104.com.tw/jobs/search/list
"""

import requests
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict


def scrape_104(
    keywords: List[str],
    area: str = "6001001000",
    max_pages: int = 3,
    hours_threshold: int = 24
) -> List[Dict]:
    """
    爬取 104 人力銀行職缺

    Args:
        keywords: 搜尋關鍵字列表
        area: 地區代碼
        max_pages: 最多爬幾頁
        hours_threshold: 只保留幾小時內的職缺

    Returns:
        職缺列表，每筆包含標準化欄位
    """
    all_jobs = []
    cutoff_time = datetime.now() - timedelta(hours=hours_threshold)

    for keyword in keywords:
        jobs = _fetch_keyword_104(keyword, area, max_pages, cutoff_time)
        all_jobs.extend(jobs)
        time.sleep(random.uniform(2, 4))

    return all_jobs


def _fetch_keyword_104(
    keyword: str,
    area: str,
    max_pages: int,
    cutoff_time: datetime
) -> List[Dict]:
    """單一關鍵字的實際爬取邏輯"""
    base_url = "https://www.104.com.tw/jobs/search/list"
    headers = {
        "Referer": "https://www.104.com.tw/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    jobs = []

    for page in range(1, max_pages + 1):
        params = {
            "ro": "0",
            "kwop": "7",
            "keyword": keyword,
            "order": "14",
            "asc": "0",
            "s9": "1",
            "jobsource": "2018indexpoc",
            "area": area,
            "page": page,
            "mode": "s",
            "jobtype": "1"
        }

        try:
            resp = requests.get(base_url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            job_list = data.get("data", {}).get("list", [])

            if not job_list:
                break

            for job in job_list:
                appear_date_str = job.get("appearDate", "")
                try:
                    appear_date = datetime.strptime(appear_date_str, "%Y/%m/%d")
                except ValueError:
                    appear_date = datetime.now()

                if appear_date < cutoff_time:
                    return jobs

                jobs.append({
                    "source": "104",
                    "job_id": job.get("jobNo", ""),
                    "title": job.get("jobName", ""),
                    "company": job.get("custName", ""),
                    "location": job.get("jobAddrNoDesc", ""),
                    "salary": job.get("salaryDesc", "面議"),
                    "url": f"https://www.104.com.tw/job/{job.get('jobNo', '')}",
                    "date_posted": appear_date_str,
                    "description": "",
                    "keyword_matched": keyword
                })

        except Exception as e:
            print(f"[104] 爬取失敗（第 {page} 頁，關鍵字：{keyword}）：{e}")
            break

        time.sleep(random.uniform(1, 3))

    return jobs
