"""
把 Claude 產生的評分套用到當日職缺，產出網站資料 + AI 需求溫度計。

由 Claude 雲端 routine（score-jobs skill）呼叫：
  1. main.py（GitHub Action）爬完寫出 data/pending.json（未評分的 jobs + baseline）
  2. Claude 讀 pending、依評分準則產出 data/scores.json
  3. python apply_scores.py  ← 本檔：合併分數 → record_daily_stats + build_site

只用標準函式庫 + pipeline.stats / pipeline.site_builder（皆無外部相依），
雲端 sandbox 不需 pip install 任何套件。
"""

import json
import os
import sys

from pipeline.stats import record_daily_stats
from pipeline.site_builder import build_site

PENDING = "data/pending.json"
SCORES = "data/scores.json"
VALID_TRACKS = {"工程/技術", "跨域-產品營運", "跨域-行銷內容", "跨域-資料分析", "其他"}


def _clamp(v, default=0):
    try:
        return max(0, min(100, int(round(float(v)))))
    except (TypeError, ValueError):
        return default


def _norm(score):
    """正規化單筆 Claude 評分（補齊缺漏、夾住範圍、軌道正規化）"""
    if not isinstance(score, dict):
        score = {}
    track = score.get("track", "其他")
    if track not in VALID_TRACKS:
        track = "其他"
    rel = _clamp(score.get("ai_relevance"))
    return {
        "ai_relevance": rel,
        "ai_score": rel,
        "is_ai_related": bool(score.get("is_ai_related", False)),
        "track": track,
        "humanities_accessible": bool(score.get("humanities_accessible", False)),
        "ai_tool_importance": _clamp(score.get("ai_tool_importance")),
        "ai_explicitly_required": bool(score.get("ai_explicitly_required", False)),
        "ai_reason": score.get("reason", "") or "",
        "summary": score.get("summary", "") or "",   # 這份工作在做什麼（一句話，卡片簡介用）
    }


def _merge(items, scores):
    """把 scores 依序套到 items 上（長度不符就補中性值）"""
    scores = scores or []
    for i, item in enumerate(items):
        item.update(_norm(scores[i] if i < len(scores) else {}))
    return items


def main():
    if not os.path.exists(PENDING):
        sys.exit(f"找不到 {PENDING}；請先讓 main.py（爬蟲）產生它")
    pending = json.load(open(PENDING, encoding="utf-8"))
    date_str = pending.get("date")
    jobs = pending.get("jobs", [])
    baseline = pending.get("baseline", [])

    scores = {}
    if os.path.exists(SCORES):
        try:
            scores = json.load(open(SCORES, encoding="utf-8"))
        except Exception as e:
            print(f"[警告] {SCORES} 解析失敗（{e}）；改以中性值套用（請檢查 Claude 輸出是否截斷）")
            scores = {}
    else:
        print(f"[警告] 找不到 {SCORES}，將以中性值套用（請確認 Claude 已產生評分）")

    _merge(jobs, scores.get("jobs"))
    _merge(baseline, scores.get("baseline"))

    display = sorted([j for j in jobs if j.get("is_ai_related")],
                     key=lambda x: x.get("ai_relevance", 0), reverse=True)

    stats = record_daily_stats(jobs, baseline, date_str=date_str)
    build_site(display, stats=stats, date_str=date_str)

    seg = stats["today"]["segment"]
    print(f"[APPLY] {date_str}：列出 {len(display)} 筆 ｜ AI 工具重要度 "
          f"{seg['avg_importance']}/100 ｜明文要求 AI {seg['pct_required']}% "
          f"｜歷史平均 {stats['cumulative']['seg_avg_importance']}")


if __name__ == "__main__":
    main()
