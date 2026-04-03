"""
HTML 報表產生模組

將爬取到的職缺資料輸出為靜態 HTML 頁面，
部署至 GitHub Pages 供瀏覽。

支援雙語顯示：國外職缺同時顯示中文翻譯（第一行）與英文原文（第二行）。
"""

import os
import json
import html as html_module
from datetime import datetime
from typing import List, Dict


# 國際平台來源名稱
INTERNATIONAL_SOURCES = {"linkedin", "indeed", "glassdoor", "international"}

# 常見職稱關鍵字中英對照（用於簡易翻譯，無需 API）
TITLE_TRANSLATIONS = {
    "Software Engineer": "軟體工程師",
    "Senior Software Engineer": "資深軟體工程師",
    "Staff Software Engineer": "主任軟體工程師",
    "Principal Software Engineer": "首席軟體工程師",
    "Junior Software Engineer": "初階軟體工程師",
    "Frontend Engineer": "前端工程師",
    "Frontend Developer": "前端開發者",
    "Backend Engineer": "後端工程師",
    "Backend Developer": "後端開發者",
    "Full Stack Engineer": "全端工程師",
    "Full Stack Developer": "全端開發者",
    "Fullstack Engineer": "全端工程師",
    "Fullstack Developer": "全端開發者",
    "DevOps Engineer": "DevOps 工程師",
    "Site Reliability Engineer": "網站可靠性工程師",
    "SRE": "網站可靠性工程師",
    "Data Scientist": "資料科學家",
    "Data Engineer": "資料工程師",
    "Data Analyst": "資料分析師",
    "Machine Learning Engineer": "機器學習工程師",
    "ML Engineer": "機器學習工程師",
    "AI Engineer": "AI 工程師",
    "AI Researcher": "AI 研究員",
    "Research Scientist": "研究科學家",
    "Research Engineer": "研究工程師",
    "Deep Learning Engineer": "深度學習工程師",
    "NLP Engineer": "自然語言處理工程師",
    "Computer Vision Engineer": "電腦視覺工程師",
    "Cloud Engineer": "雲端工程師",
    "Cloud Architect": "雲端架構師",
    "Solutions Architect": "解決方案架構師",
    "System Administrator": "系統管理員",
    "Systems Engineer": "系統工程師",
    "Network Engineer": "網路工程師",
    "Security Engineer": "資安工程師",
    "Cybersecurity Engineer": "資安工程師",
    "QA Engineer": "品質保證工程師",
    "Test Engineer": "測試工程師",
    "Quality Assurance": "品質保證",
    "Product Manager": "產品經理",
    "Project Manager": "專案經理",
    "Program Manager": "計畫經理",
    "Engineering Manager": "工程經理",
    "Technical Lead": "技術主管",
    "Tech Lead": "技術主管",
    "CTO": "技術長",
    "VP of Engineering": "工程副總",
    "Director of Engineering": "工程總監",
    "Python Developer": "Python 開發者",
    "Java Developer": "Java 開發者",
    "Go Developer": "Go 開發者",
    "Golang Developer": "Go 開發者",
    "Rust Developer": "Rust 開發者",
    "iOS Developer": "iOS 開發者",
    "Android Developer": "Android 開發者",
    "Mobile Developer": "行動應用開發者",
    "React Developer": "React 開發者",
    "Web Developer": "網頁開發者",
    "UX Designer": "使用者體驗設計師",
    "UI Designer": "介面設計師",
    "UX/UI Designer": "UX/UI 設計師",
    "Product Designer": "產品設計師",
    "Graphic Designer": "平面設計師",
    "Database Administrator": "資料庫管理員",
    "DBA": "資料庫管理員",
    "Blockchain Developer": "區塊鏈開發者",
    "Blockchain Engineer": "區塊鏈工程師",
    "Embedded Engineer": "嵌入式工程師",
    "Firmware Engineer": "韌體工程師",
    "Hardware Engineer": "硬體工程師",
    "Technical Writer": "技術文件撰寫",
    "Scrum Master": "Scrum Master",
    "Business Analyst": "商業分析師",
    "Consultant": "顧問",
    "Intern": "實習生",
    "Internship": "實習",
    "Associate": "助理",
    "Assistant": "助理",
    "Manager": "經理",
    "Director": "總監",
    "Senior": "資深",
    "Junior": "初階",
    "Lead": "主管",
    "Head of": "負責人",
    "Chief": "首席",
    "Vice President": "副總裁",
    "Scientist": "科學家",
    "Analyst": "分析師",
    "Specialist": "專員",
    "Coordinator": "協調員",
    "Administrator": "管理員",
    "Architect": "架構師",
    "Developer": "開發者",
    "Engineer": "工程師",
    "Researcher": "研究員",
    "Designer": "設計師",
}

# 常見地點翻譯
LOCATION_TRANSLATIONS = {
    "United States": "美國",
    "US": "美國",
    "USA": "美國",
    "United Kingdom": "英國",
    "UK": "英國",
    "Canada": "加拿大",
    "Australia": "澳洲",
    "Japan": "日本",
    "Singapore": "新加坡",
    "Hong Kong": "香港",
    "Taiwan": "台灣",
    "China": "中國",
    "Germany": "德國",
    "France": "法國",
    "Netherlands": "荷蘭",
    "Sweden": "瑞典",
    "Remote": "遠端",
    "Hybrid": "混合",
    "On-site": "現場",
    "New York": "紐約",
    "San Francisco": "舊金山",
    "Los Angeles": "洛杉磯",
    "Seattle": "西雅圖",
    "Boston": "波士頓",
    "Chicago": "芝加哥",
    "London": "倫敦",
    "Berlin": "柏林",
    "Paris": "巴黎",
    "Tokyo": "東京",
    "Taipei": "台北",
    "CA": "加州",
    "NY": "紐約州",
    "WA": "華盛頓州",
    "TX": "德州",
    "MA": "麻州",
}


def _translate_title(title: str) -> str:
    """嘗試翻譯職稱，優先完全匹配，再嘗試部分替換"""
    # 先試完全匹配
    for en, zh in TITLE_TRANSLATIONS.items():
        if title.strip().lower() == en.lower():
            return zh

    # 部分替換：從最長的 key 開始替換
    translated = title
    sorted_keys = sorted(TITLE_TRANSLATIONS.keys(), key=len, reverse=True)
    for en in sorted_keys:
        if en.lower() in translated.lower():
            # 保持大小寫不敏感替換
            import re
            pattern = re.compile(re.escape(en), re.IGNORECASE)
            translated = pattern.sub(TITLE_TRANSLATIONS[en], translated, count=1)

    # 如果翻譯後跟原文一樣，回傳空字串表示無法翻譯
    if translated == title:
        return ""
    return translated


def _translate_location(location: str) -> str:
    """嘗試翻譯地點"""
    if not location:
        return ""

    translated = location
    # 從最長的 key 開始替換
    sorted_keys = sorted(LOCATION_TRANSLATIONS.keys(), key=len, reverse=True)
    for en in sorted_keys:
        if en.lower() in translated.lower():
            import re
            pattern = re.compile(re.escape(en), re.IGNORECASE)
            translated = pattern.sub(LOCATION_TRANSLATIONS[en], translated, count=1)

    if translated == location:
        return ""
    return translated


def _is_international(source: str) -> bool:
    """判斷是否為國際平台"""
    return source.lower() in INTERNATIONAL_SOURCES


def generate_html_report(
    jobs: List[Dict],
    output_dir: str = "public",
    has_ai_scores: bool = False
) -> str:
    """
    產生靜態 HTML 報表（繁體中文介面，國外職缺雙語顯示）
    """
    os.makedirs(output_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    today_short = datetime.now().strftime("%Y-%m-%d")

    # 按來源分組統計
    source_counts = {}
    for job in jobs:
        src = job.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    # 台灣 vs 國際統計
    tw_count = sum(cnt for src, cnt in source_counts.items() if not _is_international(src))
    intl_count = sum(cnt for src, cnt in source_counts.items() if _is_international(src))

    # 排序
    if has_ai_scores:
        sorted_jobs = sorted(jobs, key=lambda x: x.get("ai_score", 0), reverse=True)
    else:
        sorted_jobs = sorted(jobs, key=lambda x: (x.get("source", ""), x.get("title", "")))

    table_rows = _build_table_rows(sorted_jobs, has_ai_scores)
    stats_html = _build_stats(source_counts, len(jobs), tw_count, intl_count, has_ai_scores, sorted_jobs)

    # 來源顯示名稱對照
    source_display = {
        "104": "104人力銀行",
        "CakeResume": "CakeResume",
        "Yourator": "Yourator",
        "linkedin": "LinkedIn",
        "indeed": "Indeed",
        "glassdoor": "Glassdoor",
    }

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Radar 職缺雷達 - {today_short}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft JhengHei", "Noto Sans TC", Roboto, sans-serif;
    background: #0f172a; color: #e2e8f0; line-height: 1.6;
  }}
  .container {{ max-width: 1280px; margin: 0 auto; padding: 20px; }}
  header {{
    background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
    border-radius: 12px; padding: 30px; margin-bottom: 24px;
    border: 1px solid #475569;
  }}
  header h1 {{ font-size: 28px; color: #38bdf8; margin-bottom: 4px; }}
  header .subtitle {{ color: #cbd5e1; font-size: 15px; margin-bottom: 8px; }}
  header .meta {{ color: #64748b; font-size: 12px; }}
  .stats {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px; margin-bottom: 24px;
  }}
  .stat-card {{
    background: #1e293b; border-radius: 8px; padding: 16px;
    border: 1px solid #334155; text-align: center;
  }}
  .stat-card .number {{ font-size: 32px; font-weight: 700; color: #38bdf8; }}
  .stat-card .label {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  .filters {{
    display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap;
    align-items: center;
  }}
  .filter-label {{ color: #64748b; font-size: 12px; margin-right: 4px; }}
  .filter-btn {{
    background: #1e293b; border: 1px solid #475569; color: #e2e8f0;
    padding: 6px 14px; border-radius: 20px; cursor: pointer; font-size: 13px;
    transition: all 0.2s;
  }}
  .filter-btn:hover, .filter-btn.active {{
    background: #38bdf8; color: #0f172a; border-color: #38bdf8;
  }}
  .search-box {{
    width: 100%; padding: 10px 16px; border-radius: 8px;
    background: #1e293b; border: 1px solid #475569; color: #e2e8f0;
    font-size: 14px; margin-bottom: 16px; outline: none;
  }}
  .search-box:focus {{ border-color: #38bdf8; }}
  .search-box::placeholder {{ color: #64748b; }}
  table {{
    width: 100%; border-collapse: collapse; background: #1e293b;
    border-radius: 8px; overflow: hidden;
  }}
  th {{
    background: #334155; padding: 12px 16px; text-align: left;
    font-size: 12px; color: #94a3b8; letter-spacing: 0.5px;
    cursor: pointer; user-select: none; white-space: nowrap;
  }}
  th:hover {{ color: #38bdf8; }}
  th::after {{ content: ' \\2195'; opacity: 0.3; }}
  td {{ padding: 12px 16px; border-bottom: 1px solid #0f172a; font-size: 14px; vertical-align: top; }}
  tr {{ background: #1e293b; transition: background 0.15s; }}
  tr:hover {{ background: #263348; }}
  .source-badge {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; font-weight: 600; white-space: nowrap;
  }}
  .source-104 {{ background: #7c3aed22; color: #a78bfa; border: 1px solid #7c3aed44; }}
  .source-cakeresume {{ background: #f59e0b22; color: #fbbf24; border: 1px solid #f59e0b44; }}
  .source-yourator {{ background: #10b98122; color: #34d399; border: 1px solid #10b98144; }}
  .source-linkedin {{ background: #0ea5e922; color: #38bdf8; border: 1px solid #0ea5e944; }}
  .source-indeed {{ background: #ef444422; color: #f87171; border: 1px solid #ef444444; }}
  .source-glassdoor {{ background: #22c55e22; color: #4ade80; border: 1px solid #22c55e44; }}
  .source-default {{ background: #64748b22; color: #94a3b8; border: 1px solid #64748b44; }}
  a {{ color: #38bdf8; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .bilingual .zh {{ display: block; font-size: 14px; }}
  .bilingual .en {{ display: block; font-size: 12px; color: #64748b; margin-top: 2px; }}
  .score-high {{ color: #4ade80; font-weight: 700; }}
  .score-mid {{ color: #fbbf24; font-weight: 600; }}
  .score-low {{ color: #94a3b8; }}
  .empty-state {{ text-align: center; padding: 60px 20px; color: #64748b; }}
  .intl-tag {{
    display: inline-block; font-size: 10px; padding: 1px 5px; border-radius: 3px;
    background: #475569; color: #cbd5e1; margin-left: 6px; vertical-align: middle;
  }}
  footer {{
    text-align: center; padding: 24px; color: #475569; font-size: 12px;
  }}
  @media (max-width: 768px) {{
    .container {{ padding: 12px; }}
    td, th {{ padding: 8px 10px; font-size: 13px; }}
    header h1 {{ font-size: 22px; }}
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Job Radar 職缺雷達</h1>
    <div class="subtitle">每日自動爬取・多平台整合・即時更新</div>
    <div class="meta">更新時間：{today} ｜ 資料來源：104人力銀行、CakeResume、Yourator、LinkedIn、Indeed</div>
  </header>

  {stats_html}

  <input type="text" class="search-box" placeholder="搜尋職缺（職稱、公司、地點）..."
         onkeyup="filterTable(this.value)" />

  <div class="filters">
    <span class="filter-label">篩選平台：</span>
    <button class="filter-btn active" onclick="filterSource('all', this)">全部</button>
    {"".join(f'<button class="filter-btn" onclick="filterSource({chr(39)}{src}{chr(39)}, this)">{source_display.get(src, src)} ({cnt})</button>' for src, cnt in sorted(source_counts.items()))}
  </div>

  <table id="jobTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">來源</th>
        <th onclick="sortTable(1)">職稱</th>
        <th onclick="sortTable(2)">公司</th>
        <th onclick="sortTable(3)">地點</th>
        <th onclick="sortTable(4)">薪資</th>
        {"<th onclick='sortTable(5)'>AI 評分</th>" if has_ai_scores else ""}
        <th>連結</th>
      </tr>
    </thead>
    <tbody>
      {table_rows if table_rows else '<tr><td colspan="7" class="empty-state">今日暫無新職缺</td></tr>'}
    </tbody>
  </table>

  <footer>
    Job Radar 職缺雷達 &mdash; 由 GitHub Actions 自動產生 ｜ 資料僅供參考
  </footer>
</div>

<script>
function filterTable(query) {{
  const rows = document.querySelectorAll('#jobTable tbody tr');
  query = query.toLowerCase();
  rows.forEach(row => {{
    const text = row.textContent.toLowerCase();
    row.style.display = text.includes(query) ? '' : 'none';
  }});
}}

function filterSource(source, btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const rows = document.querySelectorAll('#jobTable tbody tr');
  rows.forEach(row => {{
    if (source === 'all') {{ row.style.display = ''; return; }}
    const src = row.getAttribute('data-source') || '';
    row.style.display = src === source ? '' : 'none';
  }});
}}

let sortDir = {{}};
function sortTable(col) {{
  const table = document.getElementById('jobTable');
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  sortDir[col] = !sortDir[col];
  rows.sort((a, b) => {{
    let va = a.cells[col]?.textContent?.trim() || '';
    let vb = b.cells[col]?.textContent?.trim() || '';
    const na = parseFloat(va), nb = parseFloat(vb);
    if (!isNaN(na) && !isNaN(nb)) return sortDir[col] ? na - nb : nb - na;
    return sortDir[col] ? va.localeCompare(vb, 'zh-TW') : vb.localeCompare(va, 'zh-TW');
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
</script>
</body>
</html>"""

    output_path = os.path.join(output_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 同時輸出 JSON 資料
    json_path = os.path.join(output_dir, "jobs.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "updated": today,
            "total": len(jobs),
            "jobs": sorted_jobs
        }, f, ensure_ascii=False, indent=2)

    print(f"[HTML] 報表已產生：{output_path}（{len(jobs)} 筆職缺）")
    return output_path


def _get_source_class(source: str) -> str:
    """取得來源對應的 CSS class"""
    mapping = {
        "104": "source-104",
        "CakeResume": "source-cakeresume",
        "Yourator": "source-yourator",
        "linkedin": "source-linkedin",
        "indeed": "source-indeed",
        "glassdoor": "source-glassdoor",
    }
    return mapping.get(source, "source-default")


def _get_source_display(source: str) -> str:
    """取得來源的中文顯示名稱"""
    mapping = {
        "104": "104",
        "CakeResume": "Cake",
        "Yourator": "Yourator",
        "linkedin": "LinkedIn",
        "indeed": "Indeed",
        "glassdoor": "Glassdoor",
    }
    return mapping.get(source, source)


def _build_bilingual_cell(zh_text: str, en_text: str) -> str:
    """建立雙語顯示欄位（中文第一行、英文第二行）"""
    zh_safe = html_module.escape(zh_text)
    en_safe = html_module.escape(en_text)

    if zh_text and zh_text != en_text:
        return f'<div class="bilingual"><span class="zh">{zh_safe}</span><span class="en">{en_safe}</span></div>'
    else:
        return html_module.escape(en_text)


def _build_table_rows(jobs: List[Dict], has_ai_scores: bool) -> str:
    """建立 HTML 表格列（支援雙語）"""
    rows = []
    for job in jobs:
        source = job.get("source", "")
        css_class = _get_source_class(source)
        source_label = _get_source_display(source)
        is_intl = _is_international(source)

        # 職稱欄位
        title_raw = job.get("title", "")
        if is_intl and title_raw:
            title_zh = _translate_title(title_raw)
            title_cell = _build_bilingual_cell(title_zh, title_raw)
        else:
            title_cell = html_module.escape(title_raw)

        # 公司欄位（國際的保留原文）
        company_raw = job.get("company", "")
        company_cell = html_module.escape(company_raw)

        # 地點欄位
        location_raw = job.get("location", "")
        if is_intl and location_raw:
            location_zh = _translate_location(location_raw)
            location_cell = _build_bilingual_cell(location_zh, location_raw)
        else:
            location_cell = html_module.escape(location_raw)

        # 薪資欄位
        salary_raw = job.get("salary", "")
        salary_cell = html_module.escape(salary_raw)

        # AI 評分
        score_cell = ""
        if has_ai_scores:
            score = job.get("ai_score", 0)
            if score >= 80:
                score_class = "score-high"
            elif score >= 60:
                score_class = "score-mid"
            else:
                score_class = "score-low"
            score_cell = f'<td class="{score_class}">{score}</td>'

        # 連結
        url = job.get("url", "")
        link_cell = f'<a href="{html_module.escape(url)}" target="_blank" rel="noopener">查看</a>' if url else "-"

        # 國際標籤
        intl_tag = '<span class="intl-tag">海外</span>' if is_intl else ""

        rows.append(f"""      <tr data-source="{source}">
        <td><span class="source-badge {css_class}">{source_label}</span>{intl_tag}</td>
        <td>{title_cell}</td>
        <td>{company_cell}</td>
        <td>{location_cell}</td>
        <td>{salary_cell}</td>
        {score_cell}
        <td>{link_cell}</td>
      </tr>""")

    return "\n".join(rows)


def _build_stats(
    source_counts: Dict,
    total: int,
    tw_count: int,
    intl_count: int,
    has_ai_scores: bool,
    jobs: List[Dict]
) -> str:
    """建立統計卡片 HTML"""
    cards = [f"""    <div class="stat-card">
      <div class="number">{total}</div>
      <div class="label">職缺總數</div>
    </div>"""]

    cards.append(f"""    <div class="stat-card">
      <div class="number">{tw_count}</div>
      <div class="label">台灣職缺</div>
    </div>""")

    cards.append(f"""    <div class="stat-card">
      <div class="number">{intl_count}</div>
      <div class="label">海外職缺</div>
    </div>""")

    cards.append(f"""    <div class="stat-card">
      <div class="number">{len(source_counts)}</div>
      <div class="label">爬取平台數</div>
    </div>""")

    if has_ai_scores:
        high = sum(1 for j in jobs if j.get("ai_score", 0) >= 70)
        cards.append(f"""    <div class="stat-card">
      <div class="number">{high}</div>
      <div class="label">高分職缺 (70+)</div>
    </div>""")

    return f'  <div class="stats">\n' + "\n".join(cards) + '\n  </div>'
