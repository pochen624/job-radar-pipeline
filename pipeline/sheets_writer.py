"""
Google Sheets 寫入模組

將所有新職缺完整記錄至 Google Sheets。
每次執行都往 Sheet 最後新增資料（不覆蓋歷史紀錄）。
"""

import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime
from typing import List, Dict


SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

SHEET_HEADERS = [
    "爬取日期", "平台", "職稱", "公司", "地點", "薪資",
    "AI評分", "推薦等級", "符合點", "疑慮", "刊登日期", "連結"
]


def write_to_sheets(jobs: List[Dict], min_score: int = 40) -> bool:
    """
    將職缺資料寫入 Google Sheets

    Args:
        jobs: 已評分的職缺列表
        min_score: 只記錄幾分以上的職缺

    Returns:
        True = 成功，False = 失敗
    """
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")

    if not creds_path or not sheet_id:
        print("[Sheets] 環境變數未設定，跳過 Google Sheets 寫入")
        return False

    try:
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1

        # 如果是空表，寫入表頭
        if sheet.row_count == 0 or sheet.cell(1, 1).value != "爬取日期":
            sheet.insert_row(SHEET_HEADERS, index=1)

        # 篩選並整理資料列
        today = datetime.now().strftime("%Y-%m-%d")
        rows = []
        for job in jobs:
            if job.get("ai_score", 0) < min_score:
                continue

            rows.append([
                today,
                job.get("source", ""),
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("salary", ""),
                job.get("ai_score", 0),
                job.get("ai_recommendation", ""),
                ", ".join(job.get("ai_key_matches", [])),
                job.get("ai_concern", ""),
                job.get("date_posted", ""),
                job.get("url", "")
            ])

        if rows:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"[Sheets] 成功寫入 {len(rows)} 筆職缺")
        else:
            print("[Sheets] 沒有符合門檻的職缺可寫入")

        return True

    except Exception as e:
        print(f"[Sheets] 寫入失敗：{e}")
        return False
