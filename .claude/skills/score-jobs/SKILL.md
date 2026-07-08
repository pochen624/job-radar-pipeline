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

## Step 2：分批評分 → 漸進寫出 `data/scores.json`

### 2a. 分批策略（避免 output limit）

將 `jobs` 以 **每批 45 筆**為單位分批評分（`baseline` 單獨一批）。
**每完成一批就立刻用 Write 工具將目前已累積的結果寫入 `data/scores.json`**，
讓下一批萬一觸及 output limit 時，已完成的部分已安全落地。

```
第 1 批：jobs[0:45]   → Write scores.json（jobs 45筆 + baseline []）
第 2 批：jobs[45:90]  → Write scores.json（jobs 90筆 + baseline []）
第 3 批：jobs[90:135] → Write scores.json（jobs 135筆 + baseline []）
第 4 批：jobs[135:N]  → Write scores.json（jobs 全部 + baseline []）
baseline 批次         → Write scores.json（jobs 全部 + baseline 全部）
```

> `apply_scores.py` 的 `_merge` 已有容錯設計：`scores.json` 筆數少於 `pending` 時，
> 超出範圍的職缺自動補中性值（`ai_relevance=0`、`is_ai_related=false`，不進清單）。
> **即使部分完成也能 commit，網站仍會正常部署。**

### 2b. output limit 中途停止時的處理

若在某批次途中感知到 context 緊縮（連續兩批描述量大、或已處理超過 3 批），
應立即：
1. 將已完成的批次結果寫出 `data/scores.json`（不完整也沒關係）
2. 繼續 Step 3（`apply_scores.py`）與 Step 4（commit/push）——讓已完成的部分先上線
3. 在 Step 5「公佈欄」中誠實標示哪些職缺未完成評分

**不要為了完整性而跳過 commit**；部分評分上線遠勝過什麼都沒輸出。

### 2c. 評分欄位規格

`data/scores.json` 格式：

```json
{
  "jobs":     [ {評分}, ... ],
  "baseline": [ {評分}, ... ]
}
```

| 欄位 | 型別 | 說明 |
|---|---|---|
| `ai_relevance` | 0–100 整數 | 這份工作屬於「AI／科技新創／跨域」受眾的程度（用於篩選清單） |
| `is_ai_related` | bool | 是否納入 AI 職缺清單 |
| `track` | 字串 | 必為其一：`工程/技術`、`跨域-產品營運`、`跨域-行銷內容`、`跨域-資料分析`、`其他` |
| `humanities_accessible` | bool | 文科／社科背景能否勝任 |
| `ai_tool_importance` | 0–100 整數 | **在這份工作的日常實作中「使用 AI 工具」有多重要**（ChatGPT/Copilot/生成式 AI/AI 輔助流程）。**與是不是 AI 職無關**：行銷/行政若期待用 AI 提升產出就高、完全用不到就低。錨點：0=用不到｜50=明顯有幫助/被期待｜100=熟練使用 AI 工具是核心要求 |
| `ai_explicitly_required` | bool | JD 是否**明文**要求 AI 工具能力 |
| `reason` | 字串 | 一句話評分理由 |
| `summary` | 字串 | **這份工作在做什麼**——一句話中文簡介，讓求職者一眼看懂；卡片會直接顯示。資訊不足就依職稱/公司合理推斷、別硬掰細節 |
| `work_hours` | 字串 | **工作時數／班別**——只從 JD 描述裡**明確寫到**的工時抽出（例「日班 09:00-18:00」「排班制」「彈性工時」「週休二日」），≤20 字；JD 沒提到就給空字串 `""`，**不要臆測** |
| `skills` | 字串陣列 | **所需技能與能力**——從 JD／職稱抽出的關鍵技能（硬技能＋軟實力），例 `["Python","SQL","內容企劃","跨部門溝通"]`；取 **3–8 個**、每個 ≤20 字、只留真正相關的；JD 沒明列時可依職稱／公司推斷該職常見技能，但別硬湊不相關的。完全無從判斷就給空陣列 `[]` |

**目標受眾**：對 AI／科技新創有興趣、想投入跨領域職位者，含文科／社科背景；除工程職，也涵蓋產品、營運、行銷、內容、商業開發、客戶成功、資料分析、UX 等「文科也能切入」的 AI 相關職位。

`baseline` 樣本同樣要給 `ai_tool_importance` / `ai_explicitly_required`（它代表全市場，多數可能偏低，但仍照實評）；其餘欄位照填即可。

## Step 3：套用分數 → 產生網站資料 + 溫度計

```bash
python apply_scores.py
```

這會合併分數、`record_daily_stats`（更新 `data/ai_demand_history.csv` + SQLite）、`build_site`
（更新 `docs/data/<日期>.json`、當月彙總、`index.json`、`ai_demand.json`）。確認印出 `[APPLY] ...` 摘要。

## Step 4：commit + push

依完成程度選擇 commit 訊息：

```bash
git add docs/data data/ai_demand_history.csv
git rm --cached data/scores.json data/pending.json 2>/dev/null || true   # 不追蹤暫存檔

# 完整完成時：
git commit -m "data: Claude job scoring + AI demand ($(date -u +%F))"

# 部分完成時（已評 X 筆，剩 Y 未評）：
git commit -m "data: Claude job scoring (partial X/N) + AI demand ($(date -u +%F))"

git push origin HEAD:main
```

> ★ 絕對不要加 `[skip ci]`——需要這個 push 觸發 `pages.yml` 重新部署網站。

## Step 5：公佈欄（完成報告）

無論完整或部分完成，都要回報以下資訊：

**完整完成時：**
- 今日列出幾筆 AI 職缺
- AI 工具重要度（今日 / 歷史）
- 明文要求 AI 比例
- commit hash

**部分完成時，額外列出公佈欄：**

```
⚠️ 評分公佈欄（output limit 觸發，部分未完成）
─────────────────────────────────────────────
已評分：jobs[0:X]（X 筆）+ baseline（Y 筆）
未評分：jobs[X:N]（剩 Z 筆）→ 自動補中性值，不進職缺清單
原因：本次 context 使用量達上限，提前停止以保留已完成成果
建議：下次手動執行 /score-jobs 可重新評分當日完整資料
─────────────────────────────────────────────
```

> 部分完成仍要 commit + push，讓已評分的職缺先上線；
> 未評分的職缺因 `ai_relevance=0` 不會出現在清單頁，不影響網站展示品質。
