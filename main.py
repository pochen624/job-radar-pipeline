"""
AI 職缺雷達 — 主程式

執行流程：
  1. 讀取設定 (config/job_config.yaml)
  2. 爬取 AI／跨域職缺：Cake、Yourator、1111、LinkedIn/Indeed（台灣 + 遠端）
  3. 去重過濾（只保留今日新職缺）
  4. 另抓 1111 全市場無偏樣本（給 AI 需求溫度計做基準）
  5. AI 評分（Gemini Flash）— 每筆加上 AI 相關度、軌道、文科可投、AI 工具重要度…
  6. 記錄每日 AI 需求溫度計（SQLite + data/ai_demand_history.csv）
  7. 產生 HTML 報表（部署至 GitHub Pages）
  8. Google Sheets / LINE Notify — 如有設定
"""

import os
import sys
import yaml
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from scrapers.scraper_cakeresume import scrape_cakeresume
from scrapers.scraper_yourator import scrape_yourator
from scrapers.scraper_1111 import scrape_1111, scrape_1111_baseline
from scrapers.scraper_international import scrape_international
from pipeline.deduplicator import filter_new_jobs
from pipeline.site_builder import build_site


def load_config(config_path: str = "config/job_config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _scrape(label, fn):
    """統一的爬取包裝：印出筆數、吞掉例外（單站失敗不影響整體）"""
    print(f"[{label}] Scraping...")
    try:
        jobs = fn()
        print(f"   -> {len(jobs)} jobs")
        return jobs
    except Exception as e:
        print(f"   -> FAILED: {e}")
        return []


def main():
    start_time = datetime.now()
    dry_run = "--dry-run" in sys.argv

    print(f"\n{'=' * 50}")
    print(f"AI 職缺雷達 [{start_time.strftime('%Y-%m-%d %H:%M')}]")
    if dry_run:
        print("(DRY RUN)")
    print(f"{'=' * 50}\n")

    config = load_config()
    keywords = config["keywords"]
    platforms = config["platforms"]
    filters = config["filters"]
    loc = config["location"]
    max_pages = filters.get("max_pages", 2)

    # ── Step 1: 爬取職缺 ──────────────────────────
    all_raw_jobs = []

    if platforms.get("taiwan_cakeresume"):
        all_raw_jobs += _scrape("Cake", lambda: scrape_cakeresume(keywords, max_pages=max_pages))
    if platforms.get("taiwan_yourator"):
        all_raw_jobs += _scrape("Yourator", lambda: scrape_yourator(keywords, max_pages=max_pages))
    if platforms.get("taiwan_1111"):
        all_raw_jobs += _scrape("1111", lambda: scrape_1111(keywords, max_pages=max_pages))
    if platforms.get("taiwan_104"):
        from scrapers.scraper_104 import scrape_104
        all_raw_jobs += _scrape("104", lambda: scrape_104(
            keywords=keywords, hours_threshold=filters["hours_old"]))
    if platforms.get("international_linkedin") or platforms.get("international_indeed"):
        all_raw_jobs += _scrape("LinkedIn/Indeed", lambda: scrape_international(
            keywords=keywords,
            location=loc.get("taiwan", "Taipei, Taiwan"),
            country_indeed=loc.get("country_indeed", "Taiwan"),
            results_per_site=filters["results_per_site"],
            hours_old=filters["hours_old"],
            include_remote=loc.get("include_remote", True),
        ))

    print(f"\nTotal scraped: {len(all_raw_jobs)}")

    # ── Step 2: 去重過濾 ──────────────────────────
    print("\nDeduplicating...")
    new_jobs, dup_count = filter_new_jobs(all_raw_jobs)
    print(f"   -> New: {len(new_jobs)} | Duplicates: {dup_count}")

    # ── Step 3: 全市場無偏樣本（溫度計基準，不去重、不進清單） ──
    baseline_jobs = []
    if platforms.get("taiwan_1111"):
        n = config.get("barometer", {}).get("market_baseline_sample", 80)
        baseline_jobs = _scrape("1111-baseline", lambda: scrape_1111_baseline(n))

    # ── Step 4: AI 評分（選用） ───────────────────
    has_ai_scores = False
    stats = None
    display_jobs = new_jobs
    gemini_key = os.getenv("GEMINI_API_KEY")

    if gemini_key and (new_jobs or baseline_jobs) and not dry_run:
        try:
            from pipeline.ai_scorer import score_jobs
            from pipeline.stats import record_daily_stats
            sc = config["ai_scoring"]
            cap = sc.get("max_jobs_to_score", 500)

            scored_segment = new_jobs[:cap]
            if len(new_jobs) > cap:
                print(f"[AI] 注意：今日 {len(new_jobs)} 筆超過上限 {cap}，僅評分前 {cap} 筆")

            to_score = scored_segment + baseline_jobs
            print(f"\nAI scoring {len(to_score)} jobs（含 {len(baseline_jobs)} 基準樣本）...")
            score_jobs(to_score, sc["candidate_profile"],
                       model_name=sc.get("model", "gemini-2.5-flash"),
                       batch_size=sc.get("batch_size", 15))
            has_ai_scores = True

            # 清單只顯示 AI 相關職缺，依相關度排序
            display_jobs = [j for j in scored_segment if j.get("is_ai_related")]
            display_jobs.sort(key=lambda x: x.get("ai_relevance", 0), reverse=True)

            # Step 5: 記錄 AI 需求溫度計
            print("Recording AI demand barometer...")
            stats = record_daily_stats(scored_segment, baseline_jobs)
            seg = stats["today"]["segment"]
            print(f"   -> 今日 AI 工具重要度: {seg['avg_importance']}/100 "
                  f"｜明文要求 AI: {seg['pct_required']}% ｜歷史平均: "
                  f"{stats['cumulative']['seg_avg_importance']}")
        except Exception as e:
            print(f"   -> AI scoring failed: {e}")
            has_ai_scores = False
            display_jobs = new_jobs
    elif not gemini_key:
        print("\n[SKIP] No GEMINI_API_KEY — skipping AI scoring & barometer")

    # ── Step 6: 產生網站資料（日曆封存式前端讀 docs/data/） ──
    print("\nBuilding site data (docs/data)...")
    build_site(display_jobs, stats=stats)

    # ── Step 7: Google Sheets（選用） ─────────────
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if sheet_id and not dry_run and has_ai_scores:
        print("\nWriting to Google Sheets...")
        try:
            from pipeline.sheets_writer import write_to_sheets
            write_to_sheets(display_jobs, min_score=config["ai_scoring"]["min_score_to_save"])
        except Exception as e:
            print(f"   -> Sheets failed: {e}")
    else:
        print("[SKIP] Google Sheets")

    # ── Step 8: LINE Notify（選用） ───────────────
    line_token = os.getenv("LINE_NOTIFY_TOKEN")
    if line_token and not dry_run and has_ai_scores:
        print("\nSending LINE Notify...")
        try:
            from pipeline.notifier import send_daily_digest
            send_daily_digest(display_jobs, min_score=config["ai_scoring"]["min_score_to_notify"])
        except Exception as e:
            print(f"   -> LINE failed: {e}")
    else:
        print("[SKIP] LINE Notify")

    # ── 執行摘要 ──────────────────────────────────
    elapsed = (datetime.now() - start_time).seconds
    print(f"\n{'=' * 50}")
    print(f"Done in {elapsed}s")
    print(f"   Scraped: {len(all_raw_jobs)} | New: {len(new_jobs)} | Listed: {len(display_jobs)}")
    if has_ai_scores and stats:
        print(f"   AI 工具重要度（今日/歷史）: "
              f"{stats['today']['segment']['avg_importance']} / "
              f"{stats['cumulative']['seg_avg_importance']}")
    print(f"   Site: docs/ (GitHub Pages)")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()
