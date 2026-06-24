---
name: score-jobs
description: |
  用 Claude（訂閱配額、不需 API key）把當天爬到的職缺評分／分軌道／標文科可投／算 AI 工具重要度，
  更新 docs/data 與 AI 需求溫度計，commit + push 到 main。完全在 Anthropic Cloud sandbox 跑，
  使用者的 Mac 不用開機、不需要 GEMINI_API_KEY。
  Use when the user says「幫今天的職缺評分」「score jobs」「/score-jobs」，或被排程 routine 自動觸發。
command: score-jobs
---

# Score Jobs（Claude 訂閱版每日評分）

GitHub Action 每天爬完職缺後，會把**未評分**的原始資料寫進 `data/pending.json` 並 commit。
這個 skill 由 Claude 讀那個檔、依準則評分、產生網站資料，**用月費配額跑、不需 API key**。

可選 argument：日期 `YYYY-MM-DD`（僅作紀錄；實際以 `data/pending.json` 內的 date 為準）。

---

## Step 0：強制同步到 origin/main

排程在雲端 sandbox 跑，checkout 可能是舊的、或跟爬蟲 commit 撞車。直接 hard-reset 最安全：

```bash
git fetch origin main
git checkout main 2>/dev/null || git checkout -b main origin/main
git reset --hard origin/main
git status   # 確認 clean 且在 main
```

## Step 1：讀取待評分資料

```bash
cat data/pending.json | head -c 500   # 確認有 date / jobs / baseline
```

`data/pending.json` 結構：`{"date": "YYYY-MM-DD", "jobs": [ {職缺} ... ], "baseline": [ {職缺} ... ]}`。
每筆職缺有 `title / company / location / salary / source / description`。
- `jobs`＝我們鎖定的 AI／跨域職缺（會進清單）
- `baseline`＝1111 全市場無偏樣本（只供溫度計基準，不進清單）

若 `data/pending.json` 不存在或 jobs 為空 → 印出說明、**不要 commit**、直接結束。

## Step 2：逐筆評分，寫出 `data/scores.json`

對 `jobs` 與 `baseline` 的**每一筆**，依序產生一個評分物件。輸出檔：

```json
{
  "jobs":     [ {評分}, ... ],   // 長度與順序對齊 pending.jobs
  "baseline": [ {評分}, ... ]    // 長度與順序對齊 pending.baseline
}
```

每個「評分」物件欄位：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `ai_relevance` | 0–100 整數 | 這份工作屬於「AI／科技新創／跨域」受眾的程度（用於篩選清單） |
| `is_ai_related` | bool | 是否納入 AI 職缺清單 |
| `track` | 字串 | 必為其一：`工程/技術`、`跨域-產品營運`、`跨域-行銷內容`、`跨域-資料分析`、`其他` |
| `humanities_accessible` | bool | 文科／社科背景能否勝任 |
| `ai_tool_importance` | 0–100 整數 | **在這份工作的日常實作中「使用 AI 工具」有多重要**（ChatGPT/Copilot/生成式 AI/AI 輔助流程）。**與是不是 AI 職無關**：行銷/行政若期待用 AI 提升產出就高、完全用不到就低。錨點：0=用不到｜50=明顯有幫助/被期待｜100=熟練使用 AI 工具是核心要求 |
| `ai_explicitly_required` | bool | JD 是否**明文**要求 AI 工具能力 |
| `reason` | 字串 | 一句話理由 |

**目標受眾**：對 AI／科技新創有興趣、想投入跨領域職位者，含文科／社科背景；除工程職，也涵蓋產品、營運、行銷、內容、商業開發、客戶成功、資料分析、UX 等「文科也能切入」的 AI 相關職位。

`baseline` 樣本同樣要給 `ai_tool_importance` / `ai_explicitly_required`（它代表全市場，多數可能偏低，但仍照實評）；其餘欄位照填即可。

> 量大時可分批在思考中處理，但**最終 `data/scores.json` 必須包含所有筆數、順序對齊**。用 Write 工具一次寫出完整檔案。

## Step 3：套用分數 → 產生網站資料 + 溫度計

```bash
python apply_scores.py
```

這會合併分數、`record_daily_stats`（更新 `data/ai_demand_history.csv` + SQLite）、`build_site`
（更新 `docs/data/<日期>.json`、當月彙總、`index.json`、`ai_demand.json`）。確認印出 `[APPLY] ...` 摘要。

## Step 4：commit + push

```bash
git add docs/data data/ai_demand_history.csv
git rm --cached data/scores.json data/pending.json 2>/dev/null || true   # 不追蹤暫存檔
# 注意：commit 訊息「不要」加 [skip ci] —— 我們需要這個 push 觸發 pages.yml 把評分後的網站重新部署。
git commit -m "data: Claude job scoring + AI demand ($(date -u +%F))"
git push origin HEAD:main
```

push 後 `pages.yml` 會自動把更新後的 `docs/` 重新部署到 GitHub Pages。
完成後簡述：今日列出幾筆、AI 工具重要度今日/歷史、明文要求 AI 比例、commit hash。
