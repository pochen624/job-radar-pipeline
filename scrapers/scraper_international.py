"""
國際求職平台爬蟲（使用 python-jobspy 套件）

JobSpy 統一爬取多個平台的職缺，回傳標準化 DataFrame。
"""

from jobspy import scrape_jobs
import pandas as pd
from typing import List, Dict
import time


def scrape_international(
    keywords: List[str],
    location: str = "Taiwan",
    results_per_site: int = 30,
    hours_old: int = 24
) -> List[Dict]:
    """
    爬取 LinkedIn、Indeed 等國際平台

    Args:
        keywords: 搜尋關鍵字列表
        location: 地點（英文）
        results_per_site: 每個平台每個關鍵字抓幾筆
        hours_old: 只保留幾小時內的職缺

    Returns:
        標準化職缺列表
    """
    all_jobs = []

    for keyword in keywords:
        try:
            df = scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor"],
                search_term=keyword,
                location=location,
                results_wanted=results_per_site,
                hours_old=hours_old,
                country_indeed="Taiwan",
                description_format="markdown"
            )

            if df is not None and not df.empty:
                jobs = _normalize_jobspy_df(df, keyword)
                all_jobs.extend(jobs)

        except Exception as e:
            print(f"[International] 爬取失敗（關鍵字：{keyword}）：{e}")

        time.sleep(3)

    return all_jobs


def _normalize_jobspy_df(df: pd.DataFrame, keyword: str) -> List[Dict]:
    """將 JobSpy DataFrame 轉換為標準化格式"""
    jobs = []
    for _, row in df.iterrows():
        jobs.append({
            "source": str(row.get("site", "international")),
            "job_id": str(row.get("id", "")),
            "title": str(row.get("title", "")),
            "company": str(row.get("company", "")),
            "location": str(row.get("location", "")),
            "salary": _parse_salary(row),
            "url": str(row.get("job_url", "")),
            "date_posted": str(row.get("date_posted", "")),
            "description": str(row.get("description", ""))[:2000],
            "keyword_matched": keyword
        })
    return jobs


def _parse_salary(row) -> str:
    """解析薪資欄位"""
    min_amt = row.get("min_amount")
    max_amt = row.get("max_amount")
    currency = row.get("currency", "")
    interval = row.get("interval", "")

    if pd.notna(min_amt) and pd.notna(max_amt):
        return f"{currency} {min_amt:,.0f}–{max_amt:,.0f} / {interval}"
    return "未提供"
