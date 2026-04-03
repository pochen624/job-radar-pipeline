"""
AI 職缺評分模組（使用 Google Gemini API）

對每筆職缺呼叫 Gemini Flash，回傳：
  - relevance_score: 0-100 相關度分數
  - key_matches: 符合的關鍵點列表
  - concern: 潛在疑慮
  - recommendation: highly_recommend / recommend / neutral / skip
"""

import google.generativeai as genai
import json
import time
import os
from typing import List, Dict


def setup_gemini():
    """初始化 Gemini API"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 環境變數未設定")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.0-flash")


def score_jobs(
    jobs: List[Dict],
    candidate_profile: str
) -> List[Dict]:
    """
    對職缺列表進行 AI 評分

    Args:
        jobs: 職缺列表
        candidate_profile: 應徵者背景描述

    Returns:
        附有 ai_score、ai_analysis 欄位的職缺列表
    """
    model = setup_gemini()
    scored_jobs = []

    for i, job in enumerate(jobs):
        print(f"[AI] 評分中 {i+1}/{len(jobs)}: {job['title']} @ {job['company']}")

        score_result = _score_single_job(model, job, candidate_profile)
        job.update(score_result)
        scored_jobs.append(job)

        time.sleep(1)

    return scored_jobs


def _score_single_job(
    model,
    job: Dict,
    candidate_profile: str
) -> Dict:
    """對單一職缺進行評分"""
    description_snippet = job.get("description", "")[:800]

    prompt = f"""你是一位專業的求職顧問，請評估以下職缺與應徵者的匹配程度。

【應徵者背景】
{candidate_profile}

【職缺資訊】
職稱：{job.get('title', '未知')}
公司：{job.get('company', '未知')}
地點：{job.get('location', '未知')}
薪資：{job.get('salary', '未提供')}
職缺描述摘要：{description_snippet}

【請以 JSON 格式回覆，不要有任何其他文字或 markdown】
{{
  "relevance_score": <0到100的整數，100=完美符合，0=完全不相關>,
  "key_matches": ["符合點1", "符合點2", "符合點3"],
  "concern": "潛在疑慮或不符合點，沒有則填 null",
  "recommendation": "<highly_recommend|recommend|neutral|skip>",
  "one_line_reason": "用一句話說明評分理由"
}}"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        # 移除可能的 markdown code block
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        result = json.loads(text)

        return {
            "ai_score": result.get("relevance_score", 50),
            "ai_key_matches": result.get("key_matches", []),
            "ai_concern": result.get("concern", ""),
            "ai_recommendation": result.get("recommendation", "neutral"),
            "ai_reason": result.get("one_line_reason", "")
        }

    except Exception as e:
        print(f"[AI] 評分失敗：{e}")
        return {
            "ai_score": 50,
            "ai_key_matches": [],
            "ai_concern": "評分失敗",
            "ai_recommendation": "neutral",
            "ai_reason": ""
        }
