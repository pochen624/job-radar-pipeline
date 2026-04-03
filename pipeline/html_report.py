"""
HTML 報表產生模組

將爬取到的職缺資料輸出為靜態 HTML 頁面，
部署至 GitHub Pages 供瀏覽。
"""

import os
import json
from datetime import datetime
from typing import List, Dict


def generate_html_report(
    jobs: List[Dict],
    output_dir: str = "public",
    has_ai_scores: bool = False
) -> str:
    """
    產生靜態 HTML 報表

    Args:
        jobs: 職缺列表（可能有或沒有 AI 評分）
        output_dir: 輸出目錄
        has_ai_scores: 是否包含 AI 評分欄位

    Returns:
        輸出的 HTML 檔案路徑
    """
    os.makedirs(output_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    today_short = datetime.now().strftime("%Y-%m-%d")

    # 按來源分組統計
    source_counts = {}
    for job in jobs:
        src = job.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    # 如果有 AI 評分，按分數排序；否則按來源排序
    if has_ai_scores:
        sorted_jobs = sorted(jobs, key=lambda x: x.get("ai_score", 0), reverse=True)
    else:
        sorted_jobs = sorted(jobs, key=lambda x: (x.get("source", ""), x.get("title", "")))

    # 產生職缺表格列
    table_rows = _build_table_rows(sorted_jobs, has_ai_scores)
    stats_html = _build_stats(source_counts, len(jobs), has_ai_scores, sorted_jobs)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Radar - {today_short}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f172a; color: #e2e8f0; line-height: 1.6;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
  header {{
    background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
    border-radius: 12px; padding: 30px; margin-bottom: 24px;
    border: 1px solid #475569;
  }}
  header h1 {{ font-size: 28px; color: #38bdf8; margin-bottom: 8px; }}
  header p {{ color: #94a3b8; font-size: 14px; }}
  .stats {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
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
  }}
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
  table {{
    width: 100%; border-collapse: collapse; background: #1e293b;
    border-radius: 8px; overflow: hidden;
  }}
  th {{
    background: #334155; padding: 12px 16px; text-align: left;
    font-size: 12px; text-transform: uppercase; color: #94a3b8;
    letter-spacing: 0.5px; cursor: pointer;
  }}
  th:hover {{ color: #38bdf8; }}
  td {{ padding: 12px 16px; border-bottom: 1px solid #1e293b; font-size: 14px; }}
  tr {{ background: #1e293b; transition: background 0.15s; }}
  tr:hover {{ background: #263348; }}
  .source-badge {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; font-weight: 600;
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
  .score-high {{ color: #4ade80; font-weight: 700; }}
  .score-mid {{ color: #fbbf24; font-weight: 600; }}
  .score-low {{ color: #94a3b8; }}
  .empty-state {{
    text-align: center; padding: 60px 20px; color: #64748b;
  }}
  footer {{
    text-align: center; padding: 24px; color: #475569; font-size: 12px;
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Job Radar</h1>
    <p>Updated: {today} | Auto-scraped from 104, CakeResume, Yourator, LinkedIn, Indeed</p>
  </header>

  {stats_html}

  <input type="text" class="search-box" placeholder="Search jobs by title, company, location..."
         onkeyup="filterTable(this.value)" />

  <div class="filters">
    <button class="filter-btn active" onclick="filterSource('all', this)">All</button>
    {"".join(f'<button class="filter-btn" onclick="filterSource({chr(39)}{src}{chr(39)}, this)">{src} ({cnt})</button>' for src, cnt in sorted(source_counts.items()))}
  </div>

  <table id="jobTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">Source</th>
        <th onclick="sortTable(1)">Title</th>
        <th onclick="sortTable(2)">Company</th>
        <th onclick="sortTable(3)">Location</th>
        <th onclick="sortTable(4)">Salary</th>
        {"<th onclick='sortTable(5)'>AI Score</th>" if has_ai_scores else ""}
        <th>Link</th>
      </tr>
    </thead>
    <tbody>
      {table_rows if table_rows else '<tr><td colspan="7" class="empty-state">No jobs found today</td></tr>'}
    </tbody>
  </table>

  <footer>
    Job Radar Pipeline &mdash; auto-generated by GitHub Actions
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
    return sortDir[col] ? va.localeCompare(vb) : vb.localeCompare(va);
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
</script>
</body>
</html>"""

    output_path = os.path.join(output_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 同時輸出 JSON 資料（方便後續擴充）
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


def _build_table_rows(jobs: List[Dict], has_ai_scores: bool) -> str:
    """建立 HTML 表格列"""
    rows = []
    for job in jobs:
        source = job.get("source", "")
        css_class = _get_source_class(source)

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

        url = job.get("url", "")
        link_cell = f'<a href="{url}" target="_blank" rel="noopener">View</a>' if url else "-"

        rows.append(f"""      <tr data-source="{source}">
        <td><span class="source-badge {css_class}">{source}</span></td>
        <td>{job.get("title", "")}</td>
        <td>{job.get("company", "")}</td>
        <td>{job.get("location", "")}</td>
        <td>{job.get("salary", "")}</td>
        {score_cell}
        <td>{link_cell}</td>
      </tr>""")

    return "\n".join(rows)


def _build_stats(
    source_counts: Dict,
    total: int,
    has_ai_scores: bool,
    jobs: List[Dict]
) -> str:
    """建立統計卡片 HTML"""
    cards = [f"""    <div class="stat-card">
      <div class="number">{total}</div>
      <div class="label">Total Jobs</div>
    </div>"""]

    cards.append(f"""    <div class="stat-card">
      <div class="number">{len(source_counts)}</div>
      <div class="label">Platforms</div>
    </div>""")

    if has_ai_scores:
        high = sum(1 for j in jobs if j.get("ai_score", 0) >= 70)
        cards.append(f"""    <div class="stat-card">
      <div class="number">{high}</div>
      <div class="label">High Score (70+)</div>
    </div>""")

    return f'  <div class="stats">\n' + "\n".join(cards) + '\n  </div>'
