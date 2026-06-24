"""
AI 需求溫度計 — 每日彙總與累積時間序列

目標：追蹤「市場對使用 AI 工具的需求」有多高、隨時間如何變化。

兩種樣本：
  segment  : 我們鎖定的 AI／科技新創／跨域職缺（非 baseline）
  baseline : 1111 不帶關鍵字抓來的「全市場最新職缺」無偏樣本

持久化兩處：
  - SQLite  database/jobs.db 的 daily_ai_stats（含 per-track JSON，較豐富）
  - CSV     data/ai_demand_history.csv（扁平、可被 git commit，是趨勢的真實來源，
            避免 GitHub Actions 快取被清掉就斷掉歷史）
"""

import os
import csv
import json
import sqlite3
from datetime import datetime
from typing import List, Dict


_ROOT = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(_ROOT, "database", "jobs.db")
CSV_PATH = os.path.join(_ROOT, "data", "ai_demand_history.csv")

CSV_FIELDS = [
    "date",
    "n_segment", "seg_avg_importance", "seg_pct_required", "seg_avg_relevance",
    "n_baseline", "base_avg_importance", "base_pct_required",
]


def record_daily_stats(
    scored_jobs: List[Dict],
    baseline_jobs: List[Dict],
    date_str: str = None,
) -> Dict:
    """計算今日彙總、寫入 SQLite + CSV，回傳給儀表板用的摘要（今日 / 累積 / 趨勢）。"""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")

    seg = _aggregate(scored_jobs)
    base = _aggregate(baseline_jobs)

    row = {
        "date": date_str,
        "n_segment": seg["n"],
        "seg_avg_importance": seg["avg_importance"],
        "seg_pct_required": seg["pct_required"],
        "seg_avg_relevance": seg["avg_relevance"],
        "n_baseline": base["n"],
        "base_avg_importance": base["avg_importance"],
        "base_pct_required": base["pct_required"],
    }

    _upsert_csv(row)
    _upsert_sqlite(row, by_track=seg["by_track"], by_source=seg["by_source"])

    history = _read_history()
    return {
        "today": {
            "date": date_str,
            "segment": seg,
            "baseline": base,
        },
        "cumulative": _cumulative(history),
        "trend": history,  # 已依日期排序
    }


def _aggregate(jobs: List[Dict]) -> Dict:
    """對一組已評分職缺計算彙總指標"""
    jobs = [j for j in jobs if "ai_tool_importance" in j]
    n = len(jobs)
    if n == 0:
        return {"n": 0, "avg_importance": 0.0, "pct_required": 0.0,
                "avg_relevance": 0.0, "by_track": {}, "by_source": {}}

    imp = sum(j.get("ai_tool_importance", 0) for j in jobs) / n
    req = 100.0 * sum(1 for j in jobs if j.get("ai_explicitly_required")) / n
    rel = sum(j.get("ai_relevance", 0) for j in jobs) / n

    by_track = {}
    for j in jobs:
        t = j.get("track", "其他")
        by_track.setdefault(t, []).append(j.get("ai_tool_importance", 0))
    by_track = {t: {"n": len(v), "avg_importance": round(sum(v) / len(v), 1)}
                for t, v in by_track.items()}

    by_source = {}
    for j in jobs:
        s = j.get("source", "unknown")
        by_source.setdefault(s, []).append(j.get("ai_tool_importance", 0))
    by_source = {s: {"n": len(v), "avg_importance": round(sum(v) / len(v), 1)}
                 for s, v in by_source.items()}

    return {
        "n": n,
        "avg_importance": round(imp, 1),
        "pct_required": round(req, 1),
        "avg_relevance": round(rel, 1),
        "by_track": by_track,
        "by_source": by_source,
    }


def _upsert_csv(row: Dict):
    """寫入 CSV（同日覆蓋）"""
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    rows = {}
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows[r["date"]] = r
    rows[row["date"]] = {k: row[k] for k in CSV_FIELDS}

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for d in sorted(rows.keys()):
            w.writerow(rows[d])


def _upsert_sqlite(row: Dict, by_track: Dict, by_source: Dict):
    """寫入 SQLite daily_ai_stats（同日覆蓋，含 per-track/source JSON）"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_ai_stats (
            date TEXT PRIMARY KEY,
            n_segment INTEGER, seg_avg_importance REAL, seg_pct_required REAL,
            seg_avg_relevance REAL,
            n_baseline INTEGER, base_avg_importance REAL, base_pct_required REAL,
            by_track TEXT, by_source TEXT
        )
    """)
    conn.execute("""
        INSERT INTO daily_ai_stats VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(date) DO UPDATE SET
            n_segment=excluded.n_segment, seg_avg_importance=excluded.seg_avg_importance,
            seg_pct_required=excluded.seg_pct_required, seg_avg_relevance=excluded.seg_avg_relevance,
            n_baseline=excluded.n_baseline, base_avg_importance=excluded.base_avg_importance,
            base_pct_required=excluded.base_pct_required,
            by_track=excluded.by_track, by_source=excluded.by_source
    """, (
        row["date"], row["n_segment"], row["seg_avg_importance"], row["seg_pct_required"],
        row["seg_avg_relevance"], row["n_baseline"], row["base_avg_importance"],
        row["base_pct_required"], json.dumps(by_track, ensure_ascii=False),
        json.dumps(by_source, ensure_ascii=False),
    ))
    conn.commit()
    conn.close()


def _read_history() -> List[Dict]:
    """讀回 CSV 全部歷史（轉成數值），依日期排序"""
    if not os.path.exists(CSV_PATH):
        return []
    out = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rec = {"date": r["date"]}
            for k in CSV_FIELDS[1:]:
                try:
                    rec[k] = float(r.get(k, 0) or 0)
                except ValueError:
                    rec[k] = 0.0
            out.append(rec)
    return sorted(out, key=lambda x: x["date"])


def _cumulative(history: List[Dict]) -> Dict:
    """以筆數加權計算「搜尋以來」的平均"""
    seg_w = sum(h["n_segment"] for h in history)
    base_w = sum(h["n_baseline"] for h in history)

    def wavg(key, weight_key, total):
        if total == 0:
            return 0.0
        return round(sum(h[key] * h[weight_key] for h in history) / total, 1)

    return {
        "days": len(history),
        "total_segment_jobs": int(seg_w),
        "total_baseline_jobs": int(base_w),
        "seg_avg_importance": wavg("seg_avg_importance", "n_segment", seg_w),
        "seg_pct_required": wavg("seg_pct_required", "n_segment", seg_w),
        "base_avg_importance": wavg("base_avg_importance", "n_baseline", base_w),
        "base_pct_required": wavg("base_pct_required", "n_baseline", base_w),
    }
