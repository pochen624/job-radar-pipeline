"""
Job Radar Pipeline — 主程式

執行流程：
  1. 讀取設定 (config/job_config.yaml)
  2. 爬取各平台職缺（台灣 + 國際）
  3. 去重過濾（只保留今日新職缺）
  4. AI 評分（Gemini Flash）— 如有設定 API Key
  5. 產生 HTML 報表（部署至 GitHub Pages）
  6. 寫入 Google Sheets — 如有設定
  7. 發送 LINE Notify — 如有設定
"""

import os
import sys
import yaml
from datetime import datetime
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

from scrapers.scraper_104 import scrape_104
from scrapers.scraper_cakeresume import scrape_cakeresume
from scrapers.scraper_yourator import scrape_yourator
from scrapers.scraper_international import scrape_international
from pipeline.deduplicator import filter_new_jobs
from pipeline.html_report import generate_html_report


def load_config(config_path: str = "config/job_config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    start_time = datetime.now()
    dry_run = "--dry-run" in sys.argv

    print(f"\n{'='*50}")
    print(f"Job Radar Pipeline [{start_time.strftime('%Y-%m-%d %H:%M')}]")
    if dry_run:
        print("(DRY RUN)")
    print(f"{'='*50}\n")

    config = load_config()
    keywords = config["keywords"]
    platforms = config["platforms"]
    filters = config["filters"]

    # ── Step 1: 爬取職缺 ──────────────────────────
    all_raw_jobs = []

    if platforms.get("taiwan_104"):
        print("[104] Scraping...")
        try:
            jobs = scrape_104(
                keywords=keywords,
                area=config["location"]["taiwan"],
                hours_threshold=filters["hours_old"]
            )
            print(f"   -> {len(jobs)} jobs")
            all_raw_jobs.extend(jobs)
        except Exception as e:
            print(f"   -> FAILED: {e}")

    if platforms.get("taiwan_cakeresume"):
        print("[CakeResume] Scraping...")
        try:
            jobs = scrape_cakeresume(keywords=keywords)
            print(f"   -> {len(jobs)} jobs")
            all_raw_jobs.extend(jobs)
        except Exception as e:
            print(f"   -> FAILED: {e}")

    if platforms.get("taiwan_yourator"):
        print("[Yourator] Scraping...")
        try:
            jobs = scrape_yourator(keywords=keywords)
            print(f"   -> {len(jobs)} jobs")
            all_raw_jobs.extend(jobs)
        except Exception as e:
            print(f"   -> FAILED: {e}")

    if platforms.get("international_linkedin") or platforms.get("international_indeed"):
        print("[LinkedIn/Indeed] Scraping...")
        try:
            jobs = scrape_international(
                keywords=keywords,
                location=config["location"]["international"],
                results_per_site=filters["results_per_site"],
                hours_old=filters["hours_old"]
            )
            print(f"   -> {len(jobs)} jobs")
            all_raw_jobs.extend(jobs)
        except Exception as e:
            print(f"   -> FAILED: {e}")

    print(f"\nTotal scraped: {len(all_raw_jobs)}")

    # ── Step 2: 去重過濾 ──────────────────────────
    print("\nDeduplicating...")
    new_jobs, dup_count = filter_new_jobs(all_raw_jobs)
    print(f"   -> New: {len(new_jobs)} | Duplicates: {dup_count}")

    # 即使沒有新職缺也產生報表（顯示空白狀態）
    has_ai_scores = False
    output_jobs = new_jobs

    # ── Step 3: AI 評分（選用） ───────────────────
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and new_jobs and not dry_run:
        print(f"\nAI scoring {len(new_jobs)} jobs...")
        try:
            from pipeline.ai_scorer import score_jobs
            candidate_profile = config["ai_scoring"]["candidate_profile"]
            output_jobs = score_jobs(new_jobs, candidate_profile)
            has_ai_scores = True
        except Exception as e:
            print(f"   -> AI scoring failed: {e}")
            output_jobs = new_jobs
    elif not gemini_key:
        print("\n[SKIP] No GEMINI_API_KEY — skipping AI scoring")

    # ── Step 4: 產生 HTML 報表 ────────────────────
    print("\nGenerating HTML report...")
    generate_html_report(output_jobs, output_dir="public", has_ai_scores=has_ai_scores)

    # ── Step 5: Google Sheets（選用） ─────────────
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if sheet_id and not dry_run and has_ai_scores:
        print("\nWriting to Google Sheets...")
        try:
            from pipeline.sheets_writer import write_to_sheets
            write_to_sheets(output_jobs, min_score=config["ai_scoring"]["min_score_to_save"])
        except Exception as e:
            print(f"   -> Sheets failed: {e}")
    else:
        print("[SKIP] Google Sheets")

    # ── Step 6: LINE Notify（選用） ───────────────
    line_token = os.getenv("LINE_NOTIFY_TOKEN")
    if line_token and not dry_run and has_ai_scores:
        print("\nSending LINE Notify...")
        try:
            from pipeline.notifier import send_daily_digest
            send_daily_digest(output_jobs, min_score=config["ai_scoring"]["min_score_to_notify"])
        except Exception as e:
            print(f"   -> LINE failed: {e}")
    else:
        print("[SKIP] LINE Notify")

    # ── 執行摘要 ──────────────────────────────────
    elapsed = (datetime.now() - start_time).seconds
    print(f"\n{'='*50}")
    print(f"Done in {elapsed}s")
    print(f"   Scraped: {len(all_raw_jobs)}")
    print(f"   New: {len(new_jobs)}")
    if has_ai_scores:
        high = sum(1 for j in output_jobs if j.get("ai_score", 0) >= 70)
        print(f"   High score (70+): {high}")
    print(f"   Report: public/index.html")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
