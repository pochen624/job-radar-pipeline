"""
LINE Notify 推播通知模組

每日執行後，推播 ai_score >= min_score_to_notify 的職缺。
推播格式：每日精選 Top 5，包含職稱、公司、薪資、評分、連結。
"""

import requests
import os
from typing import List, Dict
from datetime import datetime


LINE_NOTIFY_API = "https://notify-api.line.me/api/notify"


def send_daily_digest(
    new_jobs: List[Dict],
    min_score: int = 70,
    top_n: int = 5
) -> bool:
    """
    發送每日職缺摘要

    Args:
        new_jobs: 已評分的新職缺列表
        min_score: 最低分數門檻
        top_n: 最多推播幾筆

    Returns:
        True = 推播成功，False = 失敗
    """
    token = os.getenv("LINE_NOTIFY_TOKEN")
    if not token:
        print("[LINE] LINE_NOTIFY_TOKEN 未設定，跳過推播")
        return False

    # 篩選並排序
    qualified = [j for j in new_jobs if j.get("ai_score", 0) >= min_score]
    top_jobs = sorted(qualified, key=lambda x: x["ai_score"], reverse=True)[:top_n]

    if not top_jobs:
        message = _build_empty_message(len(new_jobs))
    else:
        message = _build_digest_message(top_jobs, len(new_jobs), min_score)

    return _send_line(token, message)


def _build_digest_message(
    top_jobs: List[Dict],
    total_new: int,
    min_score: int
) -> str:
    """建立推播訊息內容"""
    today = datetime.now().strftime("%m/%d")
    lines = [
        f"\nJob Radar [{today}]",
        f"新職缺：{total_new} 筆｜AI 高分（{min_score}+）：{len(top_jobs)} 筆",
        "-" * 20
    ]

    for i, job in enumerate(top_jobs, 1):
        score = job.get("ai_score", 0)
        tag = "[HOT]" if score >= 85 else ("[REC]" if score >= 70 else "[OK]")

        lines.append(f"\n{tag} [{i}] {job['title']}")
        lines.append(f"Company: {job['company']}")
        lines.append(f"Location: {job['location']}  Salary: {job['salary']}")
        lines.append(f"AI Score: {score}/100")

        if job.get("ai_reason"):
            lines.append(f"Reason: {job['ai_reason']}")

        lines.append(f"Link: {job['url']}")

    lines.append(f"\nFull log: Google Sheets")

    return "\n".join(lines)


def _build_empty_message(total_new: int) -> str:
    """沒有高分職缺時的訊息"""
    today = datetime.now().strftime("%m/%d")
    return (
        f"\nJob Radar [{today}]\n"
        f"今日新增 {total_new} 筆職缺，"
        f"暫無達標職缺，詳見 Google Sheets。"
    )


def _send_line(token: str, message: str) -> bool:
    """實際發送 LINE Notify"""
    headers = {"Authorization": f"Bearer {token}"}
    data = {"message": message}

    try:
        resp = requests.post(LINE_NOTIFY_API, headers=headers, data=data, timeout=10)
        if resp.status_code == 200:
            print("[LINE] 推播成功")
            return True
        else:
            print(f"[LINE] 推播失敗：{resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"[LINE] 推播錯誤：{e}")
        return False
