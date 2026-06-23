"""
AI 職缺評分模組（Google Gemini Flash，免費層即可）

對每筆職缺回傳：
  - ai_relevance (0-100)        : 與「AI／科技新創／跨域」受眾的相關度
  - is_ai_related (bool)         : 是否納入 AI 職缺清單
  - track                        : 工程/技術 · 跨域-產品營運 · 跨域-行銷內容 · 跨域-資料分析 · 其他
  - humanities_accessible (bool) : 文科／社科背景是否也能勝任
  - ai_tool_importance (0-100)   : 「在這份工作中使用 AI 工具」的重要程度（市場溫度計訊號，
                                    與 ai_relevance 不同；即使非 AI 職也可能很高）
  - ai_explicitly_required (bool): JD 是否明文要求具備 AI 工具能力
  - reason                       : 一句話理由

為了省成本與符合免費層 RPM，採「一次評分多筆」批次處理。
"""

import google.generativeai as genai
import json
import time
import os
from typing import List, Dict


VALID_TRACKS = {"工程/技術", "跨域-產品營運", "跨域-行銷內容", "跨域-資料分析", "其他"}
DEFAULT_MODEL = "gemini-2.5-flash"


def setup_gemini(model_name: str = DEFAULT_MODEL):
    """初始化 Gemini（要求回傳 JSON）"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 環境變數未設定")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name,
        generation_config={"response_mime_type": "application/json"},
    )


def score_jobs(
    jobs: List[Dict],
    candidate_profile: str,
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 15,
    sleep_between: float = 4.0,
) -> List[Dict]:
    """
    對職缺列表批次評分。會原地補上分數欄位並回傳同一個列表。
    任何一批失敗都不會中斷整體（該批補上中性預設值）。
    """
    if not jobs:
        return jobs

    model = setup_gemini(model_name)
    total_batches = (len(jobs) + batch_size - 1) // batch_size

    for bi in range(total_batches):
        batch = jobs[bi * batch_size:(bi + 1) * batch_size]
        print(f"[AI] 評分批次 {bi + 1}/{total_batches}（{len(batch)} 筆）")
        results = _score_batch(model, batch, candidate_profile)

        for job, res in zip(batch, results):
            job.update(_clean_result(res))

        if bi < total_batches - 1:
            time.sleep(sleep_between)  # 尊重免費層 RPM（10-15 RPM）

    return jobs


def _score_batch(model, batch: List[Dict], candidate_profile: str) -> List[Dict]:
    """對一批職缺評分，回傳與 batch 等長的結果列表"""
    job_blocks = []
    for i, job in enumerate(batch):
        desc = (job.get("description", "") or "")[:600]
        job_blocks.append(
            f"[{i}] 職稱：{job.get('title', '')}\n"
            f"    公司：{job.get('company', '')}｜地點：{job.get('location', '')}\n"
            f"    描述：{desc}"
        )
    jobs_text = "\n".join(job_blocks)

    prompt = f"""你是台灣求職市場分析顧問。請逐一評估下列 {len(batch)} 筆職缺。

【目標受眾】
{candidate_profile}

【兩種「AI」要分清楚】
- ai_relevance：這份工作本身是否屬於「AI／科技新創／跨域」範疇（用於篩選受眾）。
- ai_tool_importance：在這份工作的「日常實作」中，使用 AI 工具（ChatGPT、Copilot、
  生成式 AI、AI 輔助流程等）有多重要。這跟是不是「AI 職」無關——一個行銷或行政職若
  期待用 AI 提升產出，分數就高；完全用不到 AI 的工作分數就低。
  錨點：0=用不到 AI 工具｜50=明顯有幫助/被期待｜100=能熟練使用 AI 工具是核心要求。

【職缺清單】
{jobs_text}

【請只回傳 JSON 陣列，長度必須等於 {len(batch)}，第 i 個對應 [i] 職缺】
[
  {{
    "ai_relevance": <0-100 整數>,
    "is_ai_related": <true|false，是否屬於 AI/科技新創/跨域受眾>,
    "track": "<工程/技術|跨域-產品營運|跨域-行銷內容|跨域-資料分析|其他>",
    "humanities_accessible": <true|false，文科/社科背景能否勝任>,
    "ai_tool_importance": <0-100 整數，見上方錨點>,
    "ai_explicitly_required": <true|false，JD 是否明文要求 AI 工具能力>,
    "reason": "<一句話理由>"
  }}
]"""

    try:
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        data = json.loads(text)
        if isinstance(data, dict):  # 容錯：模型可能包一層
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
        if not isinstance(data, list):
            raise ValueError("回傳非陣列")
        # 對齊長度
        if len(data) < len(batch):
            data = data + [{} for _ in range(len(batch) - len(data))]
        return data[:len(batch)]
    except Exception as e:
        print(f"[AI] 批次評分失敗，改用中性預設值：{e}")
        return [{} for _ in batch]


def _clean_result(res: Dict) -> Dict:
    """正規化單筆結果，補齊缺漏並夾住範圍"""
    if not isinstance(res, dict):
        res = {}

    def _clamp(v, lo=0, hi=100, default=0):
        try:
            return max(lo, min(hi, int(round(float(v)))))
        except (TypeError, ValueError):
            return default

    track = res.get("track", "其他")
    if track not in VALID_TRACKS:
        track = "其他"

    relevance = _clamp(res.get("ai_relevance"), default=0)
    return {
        "ai_relevance": relevance,
        "ai_score": relevance,  # 與舊版報表欄位相容
        "is_ai_related": bool(res.get("is_ai_related", False)),
        "track": track,
        "humanities_accessible": bool(res.get("humanities_accessible", False)),
        "ai_tool_importance": _clamp(res.get("ai_tool_importance"), default=0),
        "ai_explicitly_required": bool(res.get("ai_explicitly_required", False)),
        "ai_reason": res.get("reason", "") or "",
    }
