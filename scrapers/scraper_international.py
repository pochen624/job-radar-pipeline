"""
國際求職平台爬蟲（使用 python-jobspy 套件）

JobSpy 統一爬取 LinkedIn / Indeed 等平台，回傳標準化 DataFrame。

兩個重點修正：
  1. Indeed 需要 country_indeed 參數才會抓對應國家；空 location 會預設成美國。
     → 預設 country_indeed="Taiwan" + location="Taipei, Taiwan"，才會抓到台灣職缺。
  2. 額外加一輪「遠端／國際」搜尋（location="Remote"），讓有志者也能投遠端 AI 職缺。
"""

from jobspy import scrape_jobs
import pandas as pd
from typing import List, Dict
import time


def scrape_international(
    keywords: List[str],
    location: str = "Taipei, Taiwan",
    country_indeed: str = "Taiwan",
    results_per_site: int = 20,
    hours_old: int = 72,
    include_remote: bool = True,
) -> List[Dict]:
    """
    爬取 LinkedIn、Indeed 的台灣 + 遠端職缺

    Args:
        keywords: 搜尋關鍵字列表
        location: 主要搜尋地點（台灣）
        country_indeed: Indeed 的國家（必填，否則預設美國）
        results_per_site: 每平台每關鍵字每地點抓幾筆
        hours_old: 只保留幾小時內的職缺
        include_remote: 是否額外加抓一輪遠端／國際職缺

    Returns:
        標準化職缺列表
    """
    all_jobs = []

    # (label, location, country_indeed) 各搜尋情境
    passes = [("台灣", location, country_indeed)]
    if include_remote:
        passes.append(("遠端", "Remote", "worldwide"))

    for keyword in keywords:
        for label, loc, country in passes:
            for site in ["linkedin", "indeed"]:
                try:
                    df = scrape_jobs(
                        site_name=[site],
                        search_term=keyword,
                        location=loc,
                        country_indeed=country,
                        results_wanted=results_per_site,
                        hours_old=hours_old,
                        description_format="markdown",
                    )
                    if df is not None and not df.empty:
                        jobs = _normalize_jobspy_df(df, keyword, label)
                        all_jobs.extend(jobs)
                        print(f"   [{site}/{label}] {keyword}: {len(jobs)} jobs")
                except Exception as e:
                    print(f"   [{site}/{label}] {keyword}: {e}")
            time.sleep(2)

    return all_jobs


def _normalize_jobspy_df(df: pd.DataFrame, keyword: str, scope: str) -> List[Dict]:
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
            "scope": scope,  # 台灣 / 遠端
            "keyword_matched": keyword,
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
