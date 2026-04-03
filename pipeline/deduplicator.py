"""
職缺去重模組

使用 SQLite 儲存已見過的職缺。
去重 key = MD5(職稱 + 公司名)
"""

import sqlite3
import hashlib
from datetime import datetime
from typing import List, Dict, Tuple
import os


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "jobs.db")


def setup_database():
    """初始化資料庫（如不存在則建立）"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_jobs (
            job_hash    TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            company     TEXT NOT NULL,
            source      TEXT,
            first_seen  TEXT NOT NULL,
            last_seen   TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def filter_new_jobs(jobs: List[Dict]) -> Tuple[List[Dict], int]:
    """
    過濾出「今天新出現」的職缺

    Args:
        jobs: 所有爬取到的職缺列表

    Returns:
        (new_jobs, duplicate_count): 新職缺列表, 重複數量
    """
    setup_database()
    conn = sqlite3.connect(DB_PATH)
    today = datetime.now().strftime("%Y-%m-%d")

    new_jobs = []
    duplicate_count = 0

    for job in jobs:
        job_hash = _compute_hash(job["title"], job["company"])

        existing = conn.execute(
            "SELECT 1 FROM seen_jobs WHERE job_hash = ?", (job_hash,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE seen_jobs SET last_seen = ? WHERE job_hash = ?",
                (today, job_hash)
            )
            duplicate_count += 1
        else:
            conn.execute(
                "INSERT INTO seen_jobs VALUES (?, ?, ?, ?, ?, ?)",
                (job_hash, job["title"], job["company"],
                 job.get("source", ""), today, today)
            )
            new_jobs.append(job)

    conn.commit()
    conn.close()

    return new_jobs, duplicate_count


def _compute_hash(title: str, company: str) -> str:
    """計算職缺的唯一 hash"""
    raw = f"{title.strip().lower()}{company.strip().lower()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
