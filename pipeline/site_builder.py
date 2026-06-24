"""
靜態網站資料產生器（沿用 ai-digest 的日曆封存式前端）

前端（docs/index.html + docs/css + docs/js）是固定的 SPA 殼層，
本模組只負責產生它要讀的 JSON 資料：
  docs/data/index.json                  — 月份清單（日曆用）
  docs/data/YYYY/MM/YYYY-MM-DD.json      — 當日職缺（{date,count,articles}）
  docs/data/YYYY/MM/articles.json        — 當月彙總（日曆掃描可用日期用）
  docs/data/ai_demand.json               — AI 需求溫度計（barometer 面板用）

職缺 → article 欄位對應：
  category = track（軌道）       source = 平台
  ai_summary = AI 評分理由        並夾帶 company/salary/AI 分數供卡片顯示
封存會累積（articles.json 每天合併、且檔案 commit 進 repo），日曆才有歷史。
"""

import os
import re
import json
import glob
from datetime import datetime
from typing import List, Dict


DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")


def build_site(display_jobs: List[Dict], stats: Dict = None,
               docs_dir: str = DOCS_DIR, date_str: str = None) -> str:
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    year, month = date_str[:4], date_str[5:7]
    data_dir = os.path.join(docs_dir, "data")
    month_dir = os.path.join(data_dir, year, month)
    os.makedirs(month_dir, exist_ok=True)

    articles = [_job_to_article(j, date_str, i) for i, j in enumerate(display_jobs)]

    # 1. 當日檔
    with open(os.path.join(month_dir, f"{date_str}.json"), "w", encoding="utf-8") as f:
        json.dump({"date": date_str, "count": len(articles), "articles": articles},
                  f, ensure_ascii=False, indent=1)

    # 2. 當月彙總（合併：先移除今天舊資料再加入）
    month_path = os.path.join(month_dir, "articles.json")
    existing = []
    if os.path.exists(month_path):
        try:
            existing = json.load(open(month_path, encoding="utf-8")).get("articles", [])
        except Exception:
            existing = []
    existing = [a for a in existing if not a.get("id", "").startswith(date_str)]
    merged = existing + articles
    with open(month_path, "w", encoding="utf-8") as f:
        json.dump({"articles": merged}, f, ensure_ascii=False, indent=1)

    # 3. index.json（掃描所有月份彙總檔重建）
    _rebuild_index(data_dir)

    # 4. AI 需求溫度計
    with open(os.path.join(data_dir, "ai_demand.json"), "w", encoding="utf-8") as f:
        json.dump(stats or {}, f, ensure_ascii=False, indent=1)

    print(f"[SITE] docs/data 更新完成（{date_str}：{len(articles)} 筆）")
    return month_dir


def _job_to_article(job: Dict, date_str: str, idx: int) -> Dict:
    jid = re.sub(r"\s+", "", f"{date_str}-{job.get('source', '')}-{job.get('job_id', '') or idx}")
    return {
        "id": jid,
        "title": job.get("title", ""),
        "url": job.get("url", ""),
        "source": job.get("source", ""),
        "category": job.get("track") or "其他",
        "published": f"{date_str}T00:00:00Z",
        # 卡片簡介：優先 Claude 評分時產生的「這份工作在做什麼」，否則退回原始 JD 摘要
        "summary": job.get("summary", "") or "",
        "description": (job.get("description", "") or "").strip()[:240],
        "company": job.get("company", ""),
        "location": job.get("location", ""),
        "salary": job.get("salary", ""),
        "work_hours": job.get("work_hours", "") or "",
        "benefits": job.get("benefits", "") or "",
        "scope": job.get("scope", ""),
        "ai_relevance": job.get("ai_relevance"),
        "ai_tool_importance": job.get("ai_tool_importance"),
        "humanities_accessible": bool(job.get("humanities_accessible", False)),
        "ai_explicitly_required": bool(job.get("ai_explicitly_required", False)),
        "ai_reason": job.get("ai_reason", "") or "",
        "tags": [],
    }


def _rebuild_index(data_dir: str):
    months = []
    for month_path in sorted(glob.glob(os.path.join(data_dir, "*", "*", "articles.json"))):
        parts = month_path.replace("\\", "/").split("/")
        year, month = parts[-3], parts[-2]
        try:
            arts = json.load(open(month_path, encoding="utf-8")).get("articles", [])
        except Exception:
            continue
        days = {a.get("id", "")[:10] for a in arts if a.get("id")}
        months.append({"year": year, "month": month,
                       "articles": len(arts), "days": len(days)})
    months.sort(key=lambda m: (m["year"], m["month"]))
    with open(os.path.join(data_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "months": months}, f, ensure_ascii=False, indent=1)
