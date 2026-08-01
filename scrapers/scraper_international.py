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


BOTH_SITES = ["linkedin", "indeed"]


def scrape_international(
    keywords: List[str],
    location: str = "Taipei, Taiwan",
    country_indeed: str = "Taiwan",
    results_per_site: int = 20,
    hours_old: int = 72,
    include_remote: bool = True,
    extra_locations: List = None,
) -> List[Dict]:
    """
    爬取 LinkedIn、Indeed 的台灣 + 遠端職缺（可加抓其他縣市，例如南部）

    Args:
        keywords: 搜尋關鍵字列表
        location: 主要搜尋地點（台灣）
        country_indeed: Indeed 的國家（必填，否則預設美國）
        results_per_site: 每平台每關鍵字每地點抓幾筆
        hours_old: 只保留幾小時內的職缺
        include_remote: 是否額外加抓一輪遠端／國際職缺
        extra_locations: 額外搜尋地點，每項可為字串或 dict
            {name, location, sites, keywords, results_per_site}；預設只走 Indeed。

    Returns:
        標準化職缺列表
    """
    all_jobs = []

    # (label, location, country_indeed, sites, keywords, results_wanted) 各搜尋情境
    passes = [("台灣", location, country_indeed, BOTH_SITES, keywords, results_per_site)]
    for spec in (extra_locations or []):
        passes.append(_make_pass(spec, keywords, country_indeed, results_per_site))
    if include_remote:
        passes.append(("遠端", "Remote", "worldwide", BOTH_SITES, keywords, results_per_site))

    # pass-major：不同 pass 的關鍵字清單可不同，故以 pass 為外層
    for label, loc, country, sites, kws, n_want in passes:
        for keyword in kws:
            for site in sites:
                try:
                    df = scrape_jobs(
                        site_name=[site],
                        search_term=keyword,
                        location=loc,
                        country_indeed=country,
                        results_wanted=n_want,
                        hours_old=hours_old,
                        description_format="markdown",
                    )
                    n = 0 if df is None or df.empty else len(df)
                    if n:
                        all_jobs.extend(_normalize_jobspy_df(df, keyword, label))
                    # 0 筆也要印：地點字串若不被平台接受會靜默回 0，不印就完全看不出來
                    print(f"   [{site}/{label}] {keyword}: {n} jobs")
                except Exception as e:
                    print(f"   [{site}/{label}] {keyword}: {e}")
            # LinkedIn 需要較長間隔（其內部另有 3–7 秒 sleep）；純 Indeed 的 pass 可縮短
            time.sleep(2 if "linkedin" in sites else 1)

    return all_jobs


def _make_pass(spec, default_keywords, default_country, default_results):
    """把 config 的 extra location 正規化成 pass tuple。

    接受純字串或 dict。預設**只走 Indeed**：實測 LinkedIn 對台灣南部縣市會大量
    回傳新竹等不相干職缺，且每次呼叫多 3–7 秒。
    """
    if isinstance(spec, str):
        spec = {"location": spec}
    loc = spec.get("location") or spec.get("name") or ""
    return (
        spec.get("name") or loc,
        loc,
        spec.get("country_indeed", default_country),
        list(spec.get("sites") or ["indeed"]),
        list(spec.get("keywords") or default_keywords),
        int(spec.get("results_per_site") or default_results),
    )


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
