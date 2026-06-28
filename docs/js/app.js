/* ═══════════════════════════════════════════
   AI Digest Archive — v2.0
   Calendar + Hierarchical Tags + Drag-to-Tag
   ═══════════════════════════════════════════ */

const DATA_BASE = 'data';
const LS_FAVORITES = 'job-radar-favorites';
const LS_TAGS = 'job-radar-tags';

const CATEGORY_ICONS = {
  '\u5DE5\u7A0B/\u6280\u8853': '\u{1F6E0}\uFE0F',          // \u5DE5\u7A0B/\u6280\u8853
  '\u8DE8\u57DF-\u7522\u54C1\u71DF\u904B': '\u{1F4CA}',     // \u8DE8\u57DF-\u7522\u54C1\u71DF\u904B
  '\u8DE8\u57DF-\u884C\u92B7\u5167\u5BB9': '\u{1F4E3}',     // \u8DE8\u57DF-\u884C\u92B7\u5167\u5BB9
  '\u8DE8\u57DF-\u8CC7\u6599\u5206\u6790': '\u{1F4C8}',     // \u8DE8\u57DF-\u8CC7\u6599\u5206\u6790
  '\u5176\u4ED6': '\u{1F4CC}',                              // \u5176\u4ED6
};

const HIDDEN_TAGS = new Set(['curated', 'twitter', 'x', 'telegram']);
const LS_TAG_FOLDERS = 'job-radar-tag-folders';

// 分類組對應：X-AI* 七個分類合併為「X/Twitter」一組重點報告
const X_TWITTER_CATEGORIES = new Set([
  'X-AI公司', 'X-AI人物', 'X-AI工具', 'X-AI應用',
  'X-AI技術', 'X-AI新聞', 'X-AI開源', 'X-AI搜尋',
]);

/**
 * 給一個 article.category 字串，回傳對應 category_highlights 的 key。
 * X-AI* 7 個子分類都映射到 'X/Twitter'（合併重點）；其餘維持原 key。
 */
function categoryHighlightKeyFor(cat) {
  if (X_TWITTER_CATEGORIES.has(cat)) return 'X/Twitter';
  return cat;
}

// 分類底下若來源數在 2..MAX 之間，就把每個來源拆成可收合的 subtitle
//（台灣媒體、Lab、AI Media、Community、GitHub… 單日來源數最多 ~14）。
// 只有 1 個來源沒意義；上限 18 用來擋掉 X-AI工具/技術 這種一堆獨立帳號的分類
//（單日來源數常 20~23），避免炸出二十幾個各只有 1 篇的 subtitle。
const MAX_SOURCE_SUBGROUPS = 18;
function isManualTag(tag) { return state.manualTags.has(tag); }

// ── State ──
let state = {
  currentDate: new Date().toISOString().slice(0, 10),
  calMonth: new Date().getMonth(),
  calYear: new Date().getFullYear(),
  articles: [],
  filteredArticles: [],
  activeCategories: new Set(),
  activeSources: new Set(),
  activeTags: new Set(),
  manualTags: new Set(),
  // tagFolders: [{name: "AI工具", open: true, children: ["必讀","教學"], articles: {"id1":true}}, ...]
  tagFolders: JSON.parse(localStorage.getItem(LS_TAG_FOLDERS) || '[]'),
  availableDates: new Set(), // dates that have data
  taggedDates: new Set(),    // dates with tagged articles
  curatedDates: {},          // dates with AI curated content {date: [flags]}
  dateCounts: {},            // date -> article count
  viewMode: 'articles',
  history: [],       // [{type:'day',date:'2026-04-05'}, {type:'folder',name:'AI工具'}, ...]
  historyIndex: -1,
  historyNavigating: false,  // flag to prevent push while navigating
  favorites: new Set(JSON.parse(localStorage.getItem(LS_FAVORITES) || '[]')),
  tags: JSON.parse(localStorage.getItem(LS_TAGS) || '{}'),
  dataCache: {},
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ── Data Loading ──
async function fetchJSON(url) {
  if (state.dataCache[url]) return state.dataCache[url];
  try {
    const resp = await fetch(url);
    if (!resp.ok) return null;
    const data = await resp.json();
    state.dataCache[url] = data;
    return data;
  } catch { return null; }
}

async function loadDay(dateStr) {
  const [y, m] = dateStr.split('-');
  const url = `${DATA_BASE}/${y}/${m}/${dateStr}.json`;
  const data = await fetchJSON(url);
  state.dayData = data || null;
  return data ? data.articles || [] : [];
}

async function loadMonth(year, month) {
  const url = `${DATA_BASE}/${year}/${month}/articles.json`;
  const data = await fetchJSON(url);
  return data ? data.articles || [] : [];
}

async function buildDateIndex() {
  const index = await fetchJSON(`${DATA_BASE}/index.json`);
  if (!index) return;
  state.availableDates.clear();
  state.dateCounts = {};

  for (const m of index.months) {
    const arts = await loadMonth(m.year, m.month);
    const byDate = {};
    arts.forEach(a => {
      const d = a.id.slice(0, 10);
      byDate[d] = (byDate[d] || 0) + 1;
      state.availableDates.add(d);
      // Check if any article on this date has manual tags
      if ((a.tags || []).some(t => isManualTag(t))) {
        state.taggedDates.add(d);
      }
    });
    Object.assign(state.dateCounts, byDate);
  }

  // Also include curated dates (highlights/research/qa) — these may have 0 articles
  // (e.g. days where you wrote a Q&A before cron filled in articles for that day)
  try {
    const curated = await fetchJSON(`${DATA_BASE}/curated-dates.json`);
    if (curated && typeof curated === 'object') {
      for (const date of Object.keys(curated)) {
        state.availableDates.add(date);
      }
    }
  } catch {}
}

// ── Favorites & Tags ──
function toggleFavorite(id) {
  if (state.favorites.has(id)) state.favorites.delete(id);
  else state.favorites.add(id);
  localStorage.setItem(LS_FAVORITES, JSON.stringify([...state.favorites]));
}

function getArticleTags(id) { return state.tags[id] || []; }

function setArticleTags(id, tags) {
  if (tags.length === 0) delete state.tags[id];
  else state.tags[id] = tags;
  localStorage.setItem(LS_TAGS, JSON.stringify(state.tags));
}

// ═══════════════════════════════════════════
//  Calendar Widget
// ═══════════════════════════════════════════

const MONTH_NAMES = ['January','February','March','April','May','June','July','August','September','October','November','December'];

function renderCalendar() {
  const y = state.calYear, m = state.calMonth;
  $('#cal-title').textContent = `${MONTH_NAMES[m]} ${y}`;

  const firstDay = new Date(y, m, 1).getDay(); // 0=Sun
  const offset = (firstDay + 6) % 7; // Mon=0
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const today = new Date().toISOString().slice(0, 10);

  const container = $('#cal-days');
  container.innerHTML = '';

  // Empty cells for offset
  for (let i = 0; i < offset; i++) {
    const el = document.createElement('div');
    el.className = 'cal-day empty';
    container.appendChild(el);
  }

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const el = document.createElement('div');
    el.className = 'cal-day';
    el.textContent = d;

    if (state.curatedDates[dateStr]) {
      el.classList.add('has-curated');
      if (state.curatedDates[dateStr].includes('research')) {
        el.classList.add('has-research');
      }
    } else if (state.taggedDates.has(dateStr)) {
      el.classList.add('has-tags');
    } else if (state.availableDates.has(dateStr)) {
      el.classList.add('has-data');
    }

    if (dateStr === today) el.classList.add('today');
    if (dateStr === state.currentDate) el.classList.add('selected');

    if (state.availableDates.has(dateStr)) {
      el.style.cursor = 'pointer';
      el.addEventListener('click', () => showDay(dateStr));
      // Show article count
      const count = state.dateCounts[dateStr];
      if (count) {
        const countEl = document.createElement('span');
        countEl.className = 'cal-count';
        countEl.textContent = count;
        el.appendChild(countEl);
      }
    }

    container.appendChild(el);
  }
}

// ═══════════════════════════════════════════
//  Article Rendering
// ═══════════════════════════════════════════

function renderArticleCard(art, opts = {}) {
  const detail = !!opts.detail;  // detail：公司職缺面板用的「詳細卡片」（結構化 5 欄位 + JD 全文）
  const isFav = state.favorites.has(art.id);
  const tags = getArticleTags(art.id);
  const sharedTags = (art.tags || []).filter(t => isManualTag(t));
  const icon = CATEGORY_ICONS[art.category] || '\u{1F4CC}';
  const dateStr = art.published ? new Date(art.published).toLocaleDateString('zh-TW', {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'}) : '';

  const card = document.createElement('div');
  card.className = detail ? 'article-card article-card--detail' : 'article-card';
  card.dataset.cat = art.category;
  card.dataset.id = art.id;
  card.draggable = !detail;  // detail 卡片在面板裡，不需要拖曳貼標

  const perks = [];
  if (art.salary && !['面議', '未提供', ''].includes(art.salary)) perks.push(`<span class="perk perk-salary">💰 ${escHtml(art.salary)}</span>`);
  if (art.work_hours) perks.push(`<span class="perk">⏰ ${escHtml(art.work_hours)}</span>`);
  if (art.benefits) perks.push(`<span class="perk perk-benefit">🎁 ${escHtml(art.benefits)}</span>`);
  // summary 是 Claude 產生的「這份工作在做什麼」簡介；舊資料的 summary 是 company｜地點｜薪資 的字串，含「｜」就略過改用 description
  const blurb = (art.summary && !art.summary.includes('｜')) ? art.summary : (art.description || '');

  const headHtml = `
    <div class="card-header">
      <div class="card-title"><a href="${escHtml(art.url)}" target="_blank" rel="noopener">${escHtml(art.title)}</a></div>
      <div class="card-actions">
        <button class="btn-star ${isFav ? 'starred' : ''}" data-id="${art.id}" title="收藏">&#9733;</button>
        <button class="btn-tag" data-id="${art.id}" title="標籤">&#127991;</button>
      </div>
    </div>
    ${art.company ? `<div class="card-company">🏢 ${escHtml(art.company)}</div>` : ''}`;
  const aimetaHtml = art.ai_tool_importance != null ? `<div class="card-aimeta">🤖 AI工具重要度 <b>${art.ai_tool_importance}</b>/100 · 相關度 ${art.ai_relevance != null ? art.ai_relevance : '-'}${art.humanities_accessible ? ' · <span class="hum-pill">🎓 文科可投</span>' : ''}${art.ai_explicitly_required ? ' · <span class="req-pill">明文要求 AI</span>' : ''}</div>` : '';
  const tagsHtml = (sharedTags.length || tags.length) ? `<div class="card-tags">${sharedTags.map(t => `<span class="tag-badge tag-shared">${escHtml(t)}</span>`).join('')}${tags.map(t => `<span class="tag-badge tag-personal">${escHtml(t)}</span>`).join('')}</div>` : '';

  if (detail) {
    // detail 模式：精簡 meta（地點/薪資改由下方結構化 job-spec 呈現）＋ 5 欄位 job-spec
    card.innerHTML = headHtml
      + `<div class="card-meta">
          <span class="cat-badge">${icon} ${escHtml(art.category)}</span>
          <span>${escHtml(art.source)}</span>
          ${art.scope ? `<span>${escHtml(art.scope)}</span>` : ''}
          ${dateStr ? `<span>${dateStr}</span>` : ''}
        </div>`
      + renderJobSpec(art)
      + aimetaHtml
      + tagsHtml;
  } else {
    card.innerHTML = headHtml
      + `<div class="card-meta">
          <span class="cat-badge">${icon} ${escHtml(art.category)}</span>
          <span>${escHtml(art.source)}</span>
          ${art.location ? `<span>📍 ${escHtml(art.location)}</span>` : ''}
          ${art.scope ? `<span>${escHtml(art.scope)}</span>` : ''}
          ${dateStr ? `<span>${dateStr}</span>` : ''}
        </div>`
      + (perks.length ? `<div class="card-perks">${perks.join('')}</div>` : '')
      + (blurb ? `<div class="card-summary">${escHtml(blurb).slice(0, 240)}</div>` : '')
      + aimetaHtml
      + tagsHtml;
  }

  if (detail) {
    // 工作內容「看更多／收合」展開
    const moreBtn = card.querySelector('.spec-more');
    if (moreBtn) moreBtn.addEventListener('click', () => {
      const desc = card.querySelector('.spec-desc');
      const clamped = desc.classList.toggle('clamped');
      moreBtn.textContent = clamped ? '看更多 ▾' : '收合 ▴';
    });
  } else {
    // Drag events（列表模式才需要拖曳貼標）
    card.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', art.id);
      card.classList.add('dragging');
    });
    card.addEventListener('dragend', () => card.classList.remove('dragging'));
  }

  return card;
}

// 詳細卡片的結構化區塊：薪水 / 工作時數 / 工作地點 / 工作內容 / 所需技能與能力
function renderJobSpec(art) {
  const salary = (art.salary && art.salary.trim()) ? escHtml(art.salary) : '面議／未提供';
  const hours = (art.work_hours && art.work_hours.trim()) ? escHtml(art.work_hours) : '未提供';
  const loc = (art.location && art.location.trim()) ? escHtml(art.location) : '未提供';

  // 工作內容：Claude 一句話簡介（lead）＋ JD 全文（過長則可展開）
  const lead = (art.summary && !art.summary.includes('｜')) ? escHtml(art.summary) : '';
  const desc = (art.description && art.description.trim() && art.description.trim() !== 'None') ? art.description.trim() : '';
  let contentHtml = '';
  if (lead) contentHtml += `<div class="spec-lead">${lead}</div>`;
  if (desc) {
    const long = desc.length > 160;
    contentHtml += `<div class="spec-desc${long ? ' clamped' : ''}">${escHtml(desc)}</div>`;
    if (long) contentHtml += `<button class="spec-more" type="button">看更多 ▾</button>`;
  }
  if (!contentHtml) contentHtml = `<div class="spec-muted">（本筆未提供詳細描述，請點下方連結看原始職缺）</div>`;

  // 所需技能與能力：目前無獨立欄位 → 從 JD 呈現＋原始職缺連結；若日後有 art.skills（陣列/字串）則顯示
  let skillsHtml;
  const skills = art.skills;
  if (Array.isArray(skills) && skills.length) {
    skillsHtml = `<div class="spec-skills">${skills.map(s => `<span class="skill-chip">${escHtml(String(s))}</span>`).join('')}</div>`;
  } else if (typeof skills === 'string' && skills.trim()) {
    skillsHtml = `<div>${escHtml(skills)}</div>`;
  } else {
    skillsHtml = `<div class="spec-muted">詳見上方「工作內容」　<a href="${escHtml(art.url)}" target="_blank" rel="noopener">查看原始職缺 ↗</a></div>`;
  }

  return `
    <div class="job-spec">
      <div class="spec-row"><span class="spec-label">💰 薪水</span><span class="spec-val">${salary}</span></div>
      <div class="spec-row"><span class="spec-label">⏰ 工作時數</span><span class="spec-val">${hours}</span></div>
      <div class="spec-row"><span class="spec-label">📍 工作地點</span><span class="spec-val">${loc}</span></div>
      <div class="spec-row spec-row--block"><span class="spec-label">📋 工作內容</span><div class="spec-val">${contentHtml}</div></div>
      <div class="spec-row spec-row--block"><span class="spec-label">🛠 所需技能與能力</span><div class="spec-val">${skillsHtml}</div></div>
    </div>`;
}

// ── 今日招募公司分布（Top-N 水平長條 + 長尾摘要 + 可展開；點長條展開該公司職缺面板） ──
let companyExpanded = false;
let selectedCompany = null;  // 目前在面板展開的公司（null = 未展開）
function renderCompanyChart(articles) {
  const el = document.getElementById('company-chart');
  if (!el) return;
  window.__dayArticles = articles;
  const counts = {};
  (articles || []).forEach(a => {
    const c = (a.company || '').trim();
    if (c) counts[c] = (counts[c] || 0) + 1;
  });
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'zh-TW'));
  if (!entries.length) { el.style.display = 'none'; return; }
  el.style.display = '';

  const TOPN = 18;
  const totalCompanies = entries.length;
  const totalJobs = (articles || []).length;
  const shown = companyExpanded ? entries : entries.slice(0, TOPN);
  const max = entries[0][1];
  const bars = shown.map(([co, n]) =>
    `<div class="co-row co-row--click${co === selectedCompany ? ' active' : ''}" data-company="${escHtml(co)}">` +
    `<span class="co-name" title="${escHtml(co)}">${escHtml(co)}</span>` +
    `<span class="co-track"><span class="co-bar" style="width:${Math.max(4, (n / max) * 100)}%"></span></span>` +
    `<span class="co-n">${n}</span></div>`
  ).join('');
  const hidden = totalCompanies - shown.length;
  const hiddenJobs = entries.slice(shown.length).reduce((s, [, n]) => s + n, 0);
  let foot = '';
  if (hidden > 0) {
    foot = `<button class="co-toggle" onclick="companyExpanded=true; renderCompanyChart(window.__dayArticles)">展開全部 ${totalCompanies} 家（另 ${hidden} 家 / ${hiddenJobs} 筆）▾</button>`;
  } else if (companyExpanded && totalCompanies > TOPN) {
    foot = `<button class="co-toggle" onclick="companyExpanded=false; renderCompanyChart(window.__dayArticles)">收合 ▴</button>`;
  }
  el.innerHTML = `<div class="cc-head">🏢 今日招募公司 — 共 <b>${totalCompanies}</b> 家、<b>${totalJobs}</b> 筆`
    + `<span class="cc-sub">招最多：${escHtml(entries[0][0])}（${entries[0][1]}）</span></div>`
    + `<div class="co-list">${bars}</div>${foot}`;
}

// ── 公司職缺面板：點長條後在圖表下方展開該公司所有職缺的詳細卡片 ──
function toggleCompanyJobs(company) {
  if (selectedCompany === company) closeCompanyJobs();
  else renderCompanyJobs(company);
}

function renderCompanyJobs(company) {
  const panel = document.getElementById('company-jobs-panel');
  if (!panel) return;
  const jobs = (window.__dayArticles || []).filter(a => (a.company || '').trim() === company);
  if (!jobs.length) { closeCompanyJobs(); return; }
  selectedCompany = company;

  panel.innerHTML = `<div class="cj-head">`
    + `<span class="cj-title">🏢 ${escHtml(company)} — 共 <b>${jobs.length}</b> 個職缺</span>`
    + `<button class="cj-close" type="button" title="關閉">✕</button></div>`
    + `<div class="cj-list"></div>`;
  const listEl = panel.querySelector('.cj-list');
  jobs.forEach(art => listEl.appendChild(renderArticleCard(art, { detail: true })));
  panel.querySelector('.cj-close').addEventListener('click', closeCompanyJobs);
  panel.style.display = '';

  markActiveCompanyBar(company);
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function closeCompanyJobs() {
  selectedCompany = null;
  const panel = document.getElementById('company-jobs-panel');
  if (panel) { panel.style.display = 'none'; panel.innerHTML = ''; }
  markActiveCompanyBar(null);
}

// 高亮目前展開的公司長條（company 為 null 時全部取消高亮）
function markActiveCompanyBar(company) {
  document.querySelectorAll('#company-chart .co-row').forEach(row => {
    row.classList.toggle('active', !!company && row.dataset.company === company);
  });
}

function renderArticles(articles) {
  closeCompanyJobs();  // 換日／換篩選時先收掉舊的公司職缺面板
  renderCompanyChart(articles);
  const list = $('#article-list');
  list.innerHTML = '';

  // Whether to show the article-list "empty" placeholder is decided AFTER we
  // try to render top blocks (api_summary / daily_highlights / research_tools / qa),
  // so a day with no articles but with Q&A or Pro highlights still shows the top sections.
  const hasTopContent = !!(state.dayData && (
    state.dayData.api_summary ||
    state.dayData.daily_highlights ||
    state.dayData.research_tools ||
    (state.dayData.qa && (state.dayData.qa.items || []).length > 0)
  ));

  if (articles.length === 0 && !hasTopContent) {
    $('#empty-state').hidden = false;
    $('#article-stats').textContent = '';
    return;
  }
  $('#empty-state').hidden = true;

  // Render API auto-summary (topmost, purple theme)
  if (state.dayData && state.dayData.api_summary) {
    const api = state.dayData.api_summary;
    const body = api.line_report || api.daily_report || '';
    if (body) {
      const modelTag = api.model ? ` <span class="api-summary-model">${escHtml(api.model)}</span>` : '';
      const apiDiv = document.createElement('div');
      apiDiv.className = 'api-summary';
      apiDiv.innerHTML = `<details class="api-summary-details"><summary class="api-summary-toggle">${escHtml(api.title || '🤖 每日 AI 摘要')}${modelTag}</summary><div class="api-summary-body">${renderMarkdown(body)}</div></details>`;
      list.appendChild(apiDiv);
    }
  }

  // Render daily highlights if available (Gemini 3.1 Pro manual curation)
  if (state.dayData && state.dayData.daily_highlights) {
    const hl = state.dayData.daily_highlights;
    const modelTag = hl.model ? ` <span class="highlights-model">${escHtml(hl.model)}</span>` : '';
    const hlDiv = document.createElement('div');
    hlDiv.className = 'daily-highlights';
    hlDiv.innerHTML = `<details class="highlights-details"><summary class="highlights-toggle">✨ ${escHtml(hl.title)}${modelTag}</summary><div class="highlights-body">${renderMarkdown(hl.content)}</div></details>`;
    list.appendChild(hlDiv);
  }

  // Render research tools section if available
  if (state.dayData && state.dayData.research_tools) {
    const rt = state.dayData.research_tools;
    const rtDiv = document.createElement('div');
    rtDiv.className = 'research-tools';
    rtDiv.innerHTML = `<details class="research-tools-details"><summary class="research-tools-toggle">🔬 ${escHtml(rt.title)}</summary><div class="research-tools-body">${renderMarkdown(rt.content)}</div></details>`;
    list.appendChild(rtDiv);
    // Store article_ids for badge rendering
    state.researchToolIds = new Set(rt.article_ids || []);
  } else {
    state.researchToolIds = new Set();
  }

  // Render Q&A section if available (amber theme — personal research notebook)
  if (state.dayData && state.dayData.qa) {
    const qa = state.dayData.qa;
    const items = qa.items || [];
    if (items.length > 0) {
      const qaDiv = document.createElement('div');
      qaDiv.className = 'qa';
      const itemsHtml = items.map((it, idx) => {
        const tagsHtml = (it.tags || []).map(t => `<span class="qa-tag">${escHtml(t)}</span>`).join('');
        const askedAt = it.asked_at ? `<span class="qa-asked-at">${escHtml(it.asked_at.slice(0,10))}</span>` : '';
        return `<details class="qa-item${idx === 0 ? ' qa-first' : ''}">
          <summary class="qa-item-toggle">
            <span class="qa-q-marker">Q${idx + 1}</span>
            <span class="qa-question">${escHtml(it.question)}</span>
            ${askedAt}
          </summary>
          <div class="qa-item-body">
            ${tagsHtml ? `<div class="qa-tags">${tagsHtml}</div>` : ''}
            <div class="qa-answer">${renderMarkdown(it.answer_markdown || '')}</div>
          </div>
        </details>`;
      }).join('');
      qaDiv.innerHTML = `<details class="qa-details" open><summary class="qa-toggle">💡 ${escHtml(qa.title || 'Q&A')} <span class="qa-count">${items.length}</span></summary><div class="qa-body">${itemsHtml}</div></details>`;
      list.appendChild(qaDiv);
    }
  }

  const groups = {};
  articles.forEach(a => {
    const cat = a.category || 'General';
    (groups[cat] = groups[cat] || []).push(a);
  });

  const catOrder = Object.keys(CATEGORY_ICONS);
  const sortedCats = Object.keys(groups).sort((a, b) => {
    const ia = catOrder.indexOf(a), ib = catOrder.indexOf(b);
    return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
  });

  for (const cat of sortedCats) {
    const icon = CATEGORY_ICONS[cat] || '\u{1F4CC}';
    const header = document.createElement('div');
    header.className = 'category-group-header';

    const arrow = document.createElement('span');
    arrow.className = 'group-arrow collapsed';  // default collapsed
    arrow.innerHTML = '&#9660;';

    header.appendChild(arrow);
    header.appendChild(document.createTextNode(` ${icon} ${cat} (${groups[cat].length})`));
    list.appendChild(header);

    // Wrapper for all cards in this category (default collapsed)
    const groupDiv = document.createElement('div');
    groupDiv.className = 'category-group-articles collapsed';

    // Embed category highlights at the top of the group body (above article cards).
    // X-AI* 7 sub-categories all reference the merged "X/Twitter" highlights.
    const chKey = categoryHighlightKeyFor(cat);
    const chBlock = state.dayData?.category_highlights?.[chKey];
    if (chBlock && (chBlock.content || '').trim()) {
      const chInline = document.createElement('div');
      chInline.className = 'category-highlights-inline';
      const countTag = chBlock.article_count
        ? ` <span class="category-highlights-count">${chBlock.article_count} 篇</span>`
        : '';
      const mergedNote = chKey === 'X/Twitter'
        ? '<div class="category-highlights-merged-note">📌 本重點為 X-AI 公司／人物／工具／應用／技術／新聞／開源 7 個分類的合併分析</div>'
        : '';
      chInline.innerHTML = `
        <div class="category-highlights-inline-title">📂 ${escHtml(chBlock.title || `${chKey} 分類重點`)}${countTag}</div>
        ${mergedNote}
        <div class="category-highlights-inline-body">${renderMarkdown(chBlock.content)}</div>
      `;
      groupDiv.appendChild(chInline);
    }

    fillCategoryBody(groupDiv, groups[cat]);
    list.appendChild(groupDiv);

    // Click header to collapse/expand
    header.addEventListener('click', () => {
      groupDiv.classList.toggle('collapsed');
      arrow.classList.toggle('collapsed');
    });
  }

  const cats = new Set(articles.map(a => a.category));
  const sources = new Set(articles.map(a => a.source));
  $('#article-stats').textContent = `${articles.length} 筆職缺 ｜ ${cats.size} 軌道 ｜ ${sources.size} 平台`;
}

// Fill a category's body with cards. When the category has a sensible number of
// distinct sources (2..MAX_SOURCE_SUBGROUPS), split them into collapsible
// per-source subtitles (default collapsed) so readers can jump straight to a
// specific outlet (e.g. 數位時代, Inside). Otherwise render a flat card list.
function fillCategoryBody(groupDiv, catArticles) {
  const bySource = {};
  catArticles.forEach(a => {
    const s = a.source || '其他';  // 其他
    (bySource[s] = bySource[s] || []).push(a);
  });
  const sourceNames = Object.keys(bySource);

  if (sourceNames.length < 2 || sourceNames.length > MAX_SOURCE_SUBGROUPS) {
    catArticles.forEach(art => groupDiv.appendChild(renderArticleCard(art)));
    return;
  }

  // Sort sources by article count desc (matches the sidebar Sources ordering)
  sourceNames.sort((a, b) => bySource[b].length - bySource[a].length);

  for (const src of sourceNames) {
    const srcHeader = document.createElement('div');
    srcHeader.className = 'source-group-header';

    const srcArrow = document.createElement('span');
    srcArrow.className = 'group-arrow collapsed';  // default collapsed
    srcArrow.innerHTML = '&#9660;';

    srcHeader.appendChild(srcArrow);
    srcHeader.appendChild(document.createTextNode(` ${src} (${bySource[src].length})`));
    groupDiv.appendChild(srcHeader);

    const srcDiv = document.createElement('div');
    srcDiv.className = 'source-group-articles collapsed';
    bySource[src].forEach(art => srcDiv.appendChild(renderArticleCard(art)));
    groupDiv.appendChild(srcDiv);

    srcHeader.addEventListener('click', () => {
      srcDiv.classList.toggle('collapsed');
      srcArrow.classList.toggle('collapsed');
    });
  }
}

// ═══════════════════════════════════════════
//  Filters
// ═══════════════════════════════════════════

function renderFilters(articles) {
  // Categories
  const catCounts = {};
  articles.forEach(a => { catCounts[a.category] = (catCounts[a.category] || 0) + 1; });
  const catEl = $('#category-filters');
  catEl.innerHTML = '';
  const all = createChip('All', articles.length, state.activeCategories.size === 0);
  all.addEventListener('click', () => { state.activeCategories.clear(); applyFilters(); closeMobileSidebar(); });
  catEl.appendChild(all);
  Object.entries(catCounts).sort((a, b) => b[1] - a[1]).forEach(([cat, count]) => {
    const chip = createChip(cat, count, state.activeCategories.has(cat));
    chip.addEventListener('click', () => {
      state.activeCategories.has(cat) ? state.activeCategories.delete(cat) : state.activeCategories.add(cat);
      applyFilters();
      closeMobileSidebar();
    });
    catEl.appendChild(chip);
  });

  // Sources
  const srcCounts = {};
  articles.forEach(a => { srcCounts[a.source] = (srcCounts[a.source] || 0) + 1; });
  const srcEl = $('#source-filters');
  srcEl.innerHTML = '';
  Object.entries(srcCounts).sort((a, b) => b[1] - a[1]).slice(0, 15).forEach(([src, count]) => {
    const chip = createChip(src, count, state.activeSources.has(src));
    chip.addEventListener('click', () => {
      state.activeSources.has(src) ? state.activeSources.delete(src) : state.activeSources.add(src);
      applyFilters();
      closeMobileSidebar();
    });
    srcEl.appendChild(chip);
  });

  // Tag tree
  renderTagTree(articles);
}

function createChip(label, count, active, type) {
  const el = document.createElement('span');
  el.className = `filter-chip${active ? ' active' : ''}${type === 'tag' ? ' filter-tag' : ''}`;
  el.innerHTML = `${escHtml(label)} <span class="count">${count}</span>`;
  return el;
}

function applyFilters() {
  let filtered = state.articles;
  if (state.activeCategories.size > 0) {
    filtered = filtered.filter(a => state.activeCategories.has(a.category));
  }
  if (state.activeSources.size > 0) {
    filtered = filtered.filter(a => state.activeSources.has(a.source));
  }
  // Tag folder filtering is done via direct click, not chip-based
  state.filteredArticles = filtered;
  renderArticles(filtered);
  renderFilters(state.articles);
}

// ═══════════════════════════════════════════
//  Tag Folder System (hierarchical + drag)
// ═══════════════════════════════════════════

function saveTagFolders() {
  localStorage.setItem(LS_TAG_FOLDERS, JSON.stringify(state.tagFolders));
}

function getArticlesInFolder(folder) {
  return Object.keys(folder.articles || {});
}

function getArticlesInChild(folder, childName) {
  return Object.keys(folder.articles || {}).filter(id => {
    const tags = getArticleTags(id);
    return tags.includes(childName);
  });
}

function addArticleToFolder(folder, articleId) {
  if (!folder.articles) folder.articles = {};
  folder.articles[articleId] = true;
  saveTagFolders();
}

function addArticleToChild(folder, childName, articleId) {
  addArticleToFolder(folder, articleId);
  const tags = getArticleTags(articleId);
  if (!tags.includes(childName)) {
    tags.push(childName);
    setArticleTags(articleId, tags);
  }
}

function renderTagTree() {
  const tree = $('#tag-tree');
  tree.innerHTML = '';

  state.tagFolders.forEach((folder, fi) => {
    const folderEl = document.createElement('div');
    folderEl.className = 'tag-folder';

    const totalCount = getArticlesInFolder(folder).length;
    const isOpen = folder.open !== false;

    // Header
    const header = document.createElement('div');
    header.className = 'tag-folder-header';

    // Arrow button (expand/collapse ONLY)
    const arrowBtn = document.createElement('span');
    arrowBtn.className = `arrow ${isOpen ? 'open' : ''}`;
    arrowBtn.innerHTML = '&#9654;';
    arrowBtn.style.cursor = 'pointer';
    arrowBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      folder.open = !isOpen;
      saveTagFolders();
      renderTagTree();
    });

    // Folder name (click to VIEW articles)
    const nameSpan = document.createElement('span');
    nameSpan.className = 'folder-name';
    nameSpan.textContent = folder.name;
    nameSpan.style.cursor = 'pointer';
    nameSpan.addEventListener('click', (e) => {
      e.stopPropagation();
      showFolderArticles(folder);
    });

    const countSpan = document.createElement('span');
    countSpan.className = 'folder-count';
    countSpan.textContent = totalCount;

    // Action buttons
    const actionsSpan = document.createElement('span');
    actionsSpan.className = 'folder-actions';

    const addBtn = document.createElement('button');
    addBtn.className = 'folder-action-btn';
    addBtn.title = 'Add sub-tag';
    addBtn.textContent = '+';
    addBtn.addEventListener('click', (e) => { e.stopPropagation(); promptAddChild(fi); });

    const renameBtn = document.createElement('button');
    renameBtn.className = 'folder-action-btn';
    renameBtn.title = 'Rename';
    renameBtn.innerHTML = '&#9998;';
    renameBtn.addEventListener('click', (e) => { e.stopPropagation(); promptRenameFolder(fi); });

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'folder-action-btn';
    deleteBtn.title = 'Delete';
    deleteBtn.innerHTML = '&times;';
    deleteBtn.addEventListener('click', (e) => { e.stopPropagation(); deleteFolder(fi); });

    actionsSpan.appendChild(addBtn);
    actionsSpan.appendChild(renameBtn);
    actionsSpan.appendChild(deleteBtn);

    header.appendChild(arrowBtn);
    header.appendChild(nameSpan);
    header.appendChild(countSpan);
    header.appendChild(actionsSpan);

    // Drag-drop on folder header
    setupDropZone(header, (articleId) => {
      addArticleToFolder(folder, articleId);
      renderTagTree();
      applyFilters();
    });

    folderEl.appendChild(header);

    // Children container
    const children = document.createElement('div');
    children.className = `tag-children ${isOpen ? 'open' : ''}`;

    (folder.children || []).forEach((childName, ci) => {
      const childCount = getArticlesInChild(folder, childName).length;
      const childEl = document.createElement('div');
      childEl.className = 'tag-child-item';

      const childLabel = document.createElement('span');
      childLabel.textContent = `\u2022 ${childName}`;
      childLabel.style.cursor = 'pointer';
      childLabel.addEventListener('click', (e) => {
        e.stopPropagation();
        pushHistory({ type: 'child', folderName: folder.name, childName });
        const ids = getArticlesInChild(folder, childName);
        const allArts = getAllArticlesFromCache();
        const filtered = allArts.filter(a => ids.includes(a.id));
        $('#view-title').textContent = `${folder.name} / ${childName}`;
        renderArticles(filtered);
      });

      const childCountSpan = document.createElement('span');
      childCountSpan.className = 'child-count';
      childCountSpan.textContent = childCount;

      const removeBtn = document.createElement('button');
      removeBtn.className = 'child-remove';
      removeBtn.title = 'Remove';
      removeBtn.innerHTML = '&times;';
      removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!confirm(`確定要刪除子標籤「${childName}」嗎？`)) return;
        state.tagFolders[fi].children.splice(ci, 1);
        saveTagFolders();
        renderTagTree();
      });

      childEl.appendChild(childLabel);
      childEl.appendChild(childCountSpan);
      childEl.appendChild(removeBtn);

      // Drag-drop on child
      setupDropZone(childEl, (articleId) => {
        addArticleToChild(folder, childName, articleId);
        renderTagTree();
        applyFilters();
      });

      children.appendChild(childEl);
    });

    // "Add sub-tag" link at bottom
    const addLink = document.createElement('div');
    addLink.className = 'tag-add-sub';
    addLink.textContent = '+ add sub-tag';
    addLink.addEventListener('click', (e) => {
      e.stopPropagation();
      promptAddChild(fi);
    });
    children.appendChild(addLink);

    folderEl.appendChild(children);
    tree.appendChild(folderEl);
  });
}

// Show all articles in a folder across all loaded data
function showFolderArticles(folder) {
  pushHistory({ type: 'folder', folderName: folder.name });
  const ids = getArticlesInFolder(folder);
  if (ids.length === 0) {
    $('#view-title').textContent = `${folder.name} (empty)`;
    renderArticles([]);
    return;
  }
  const allArts = getAllArticlesFromCache();
  const filtered = allArts.filter(a => ids.includes(a.id));
  $('#view-title').textContent = `${folder.name} (${filtered.length})`;
  renderArticles(filtered);
}

// Get all articles from data cache (across all loaded dates/months)
function getAllArticlesFromCache() {
  let all = [];
  for (const [url, data] of Object.entries(state.dataCache)) {
    if (data && data.articles) {
      all = all.concat(data.articles);
    }
  }
  // Dedupe by id
  const seen = new Set();
  return all.filter(a => {
    if (seen.has(a.id)) return false;
    seen.add(a.id);
    return true;
  });
}

function setupDropZone(el, onDrop) {
  el.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    el.classList.add('drag-over');
  });
  el.addEventListener('dragleave', () => el.classList.remove('drag-over'));
  el.addEventListener('drop', (e) => {
    e.preventDefault();
    el.classList.remove('drag-over');
    const articleId = e.dataTransfer.getData('text/plain');
    if (articleId) onDrop(articleId);
  });
}

function promptAddFolder() {
  const name = prompt('New tag folder name:');
  if (!name || !name.trim()) return;
  state.tagFolders.push({ name: name.trim(), open: true, children: [], articles: {} });
  saveTagFolders();
  renderTagTree();
}

function promptAddChild(fi) {
  const name = prompt(`Add sub-tag to "${state.tagFolders[fi].name}":`);
  if (!name || !name.trim()) return;
  if (!state.tagFolders[fi].children) state.tagFolders[fi].children = [];
  if (!state.tagFolders[fi].children.includes(name.trim())) {
    state.tagFolders[fi].children.push(name.trim());
    saveTagFolders();
    renderTagTree();
  }
}

function promptRenameFolder(fi) {
  const name = prompt('Rename folder:', state.tagFolders[fi].name);
  if (!name || !name.trim()) return;
  state.tagFolders[fi].name = name.trim();
  saveTagFolders();
  renderTagTree();
}

function deleteFolder(fi) {
  if (!confirm(`確定要刪除標籤資料夾「${state.tagFolders[fi].name}」及其所有子標籤嗎？`)) return;
  state.tagFolders.splice(fi, 1);
  saveTagFolders();
  renderTagTree();
}

// ═══════════════════════════════════════════
//  Views
// ═══════════════════════════════════════════

async function showDay(dateStr) {
  pushHistory({ type: 'day', date: dateStr });
  state.currentDate = dateStr;
  state.viewMode = 'articles';
  // Update calendar month if needed
  const [y, m] = dateStr.split('-').map(Number);
  if (y !== state.calYear || (m - 1) !== state.calMonth) {
    state.calYear = y;
    state.calMonth = m - 1;
  }
  renderCalendar();

  $('#view-title').textContent = dateStr;
  $('#search-input').value = '';

  state.articles = await loadDay(dateStr);
  state.activeCategories.clear();
  state.activeSources.clear();
  state.activeTags.clear();
  state.filteredArticles = state.articles;

  renderArticles(state.articles);
  renderFilters(state.articles);
  updateMobileNav('articles');
  updateDayNavButtons();
  closeMobileSidebar();
}

async function showFavorites() {
  pushHistory({ type: 'favorites' });
  state.viewMode = 'favorites';
  $('#view-title').textContent = 'Favorites';
  $('#search-input').value = '';

  const index = await fetchJSON(`${DATA_BASE}/index.json`);
  if (!index) { renderArticles([]); return; }

  let allArticles = [];
  for (const m of index.months) {
    const arts = await loadMonth(m.year, m.month);
    allArticles = allArticles.concat(arts);
  }

  state.articles = allArticles.filter(a => state.favorites.has(a.id));
  state.activeCategories.clear();
  state.activeSources.clear();
  state.filteredArticles = state.articles;

  renderArticles(state.articles);
  renderFilters(state.articles);
  updateMobileNav('favorites');
  updateDayNavButtons();
  closeMobileSidebar();
}

// ── Mobile sidebar close helper ──
function closeMobileSidebar() {
  const sidebar = $('#sidebar');
  if (!sidebar) return;
  // Only close if we're actually in mobile-open state (avoid spurious updateMobileNav calls)
  if (sidebar.classList.contains('mobile-open')) {
    sidebar.classList.remove('mobile-open');
    // After filtering, the focus should be on the article list — show "Articles" tab as active
    if (state.viewMode === 'articles') {
      updateMobileNav('articles');
    } else if (state.viewMode === 'favorites') {
      updateMobileNav('favorites');
    }
  }
}

// ── Tag Modal ──
let currentTagArticleId = null;

function openTagModal(articleId) {
  currentTagArticleId = articleId;
  const tags = getArticleTags(articleId);
  $('#tag-list').innerHTML = tags.map(t =>
    `<span class="tag-badge tag-personal">${escHtml(t)} <span style="cursor:pointer" data-remove="${escHtml(t)}">&times;</span></span>`
  ).join('');
  $('#tag-input').value = '';
  $('#tag-modal').classList.add('is-open');
  $('#tag-input').focus();
}

function closeTagModal() {
  $('#tag-modal').classList.remove('is-open');
  currentTagArticleId = null;
  applyFilters();
}

// ═══════════════════════════════════════════
//  Event Handlers
// ═══════════════════════════════════════════

// ═══════════════════════════════════════════
//  History (Back / Forward)
// ═══════════════════════════════════════════

function pushHistory(entry) {
  if (state.historyNavigating) return; // don't push while navigating
  // If we're not at the end, truncate forward history
  if (state.historyIndex < state.history.length - 1) {
    state.history = state.history.slice(0, state.historyIndex + 1);
  }
  state.history.push(entry);
  state.historyIndex = state.history.length - 1;
  updateHistoryButtons();
}

function updateHistoryButtons() {
  const back = $('#btn-back');
  const fwd = $('#btn-forward');
  if (back) back.disabled = state.historyIndex <= 0;
  if (fwd) fwd.disabled = state.historyIndex >= state.history.length - 1;
}

// ── Day navigation (prev/next available date) ──
function adjacentDate(currentDate, direction) {
  const sorted = [...state.availableDates].sort();
  if (sorted.length === 0) return null;
  const idx = sorted.indexOf(currentDate);
  if (idx === -1) {
    // current date not in list — find nearest
    if (direction < 0) {
      // previous: largest date that's < current
      for (let i = sorted.length - 1; i >= 0; i--) {
        if (sorted[i] < currentDate) return sorted[i];
      }
    } else {
      // next: smallest date that's > current
      for (let i = 0; i < sorted.length; i++) {
        if (sorted[i] > currentDate) return sorted[i];
      }
    }
    return null;
  }
  const newIdx = idx + direction;
  if (newIdx < 0 || newIdx >= sorted.length) return null;
  return sorted[newIdx];
}

function updateDayNavButtons() {
  const prev = $('#btn-prev-day');
  const next = $('#btn-next-day');
  if (!prev || !next) return;
  if (state.viewMode === 'articles' && state.currentDate) {
    prev.disabled = !adjacentDate(state.currentDate, -1);
    next.disabled = !adjacentDate(state.currentDate, +1);
  } else {
    prev.disabled = true;
    next.disabled = true;
  }
}

async function navigateHistory(delta) {
  const newIndex = state.historyIndex + delta;
  if (newIndex < 0 || newIndex >= state.history.length) return;
  state.historyIndex = newIndex;
  state.historyNavigating = true;

  const entry = state.history[newIndex];
  try {
    if (entry.type === 'day') {
      await showDay(entry.date);
    } else if (entry.type === 'favorites') {
      await showFavorites();
    } else if (entry.type === 'folder') {
      const folder = state.tagFolders.find(f => f.name === entry.folderName);
      if (folder) showFolderArticles(folder);
    } else if (entry.type === 'child') {
      const folder = state.tagFolders.find(f => f.name === entry.folderName);
      if (folder) {
        const ids = getArticlesInChild(folder, entry.childName);
        const allArts = getAllArticlesFromCache();
        const filtered = allArts.filter(a => ids.includes(a.id));
        $('#view-title').textContent = `${entry.folderName} / ${entry.childName}`;
        renderArticles(filtered);
      }
    }
  } finally {
    state.historyNavigating = false;
    updateHistoryButtons();
    updateDayNavButtons();
  }
}

function setupEvents() {
  // Calendar nav
  $('#cal-prev').addEventListener('click', () => {
    state.calMonth--;
    if (state.calMonth < 0) { state.calMonth = 11; state.calYear--; }
    renderCalendar();
  });
  $('#cal-next').addEventListener('click', () => {
    state.calMonth++;
    if (state.calMonth > 11) { state.calMonth = 0; state.calYear++; }
    renderCalendar();
  });
  $('#btn-today').addEventListener('click', () => showDay(new Date().toISOString().slice(0, 10)));
  $('#btn-favorites').addEventListener('click', showFavorites);
  $('#btn-add-tag').addEventListener('click', promptAddFolder);

  // History back/forward
  $('#btn-back').addEventListener('click', () => navigateHistory(-1));
  $('#btn-forward').addEventListener('click', () => navigateHistory(1));

  // Day navigation (prev/next available date)
  $('#btn-prev-day').addEventListener('click', () => {
    const d = adjacentDate(state.currentDate, -1);
    if (d) showDay(d);
  });
  $('#btn-next-day').addEventListener('click', () => {
    const d = adjacentDate(state.currentDate, +1);
    if (d) showDay(d);
  });

  // Show drop hint when dragging articles
  document.addEventListener('dragstart', () => {
    const hint = $('#tag-drop-hint');
    if (hint) hint.hidden = false;
  });
  document.addEventListener('dragend', () => {
    const hint = $('#tag-drop-hint');
    if (hint) hint.hidden = true;
  });

  // Article list clicks
  $('#article-list').addEventListener('click', (e) => {
    const starBtn = e.target.closest('.btn-star');
    if (starBtn) { e.preventDefault(); toggleFavorite(starBtn.dataset.id); starBtn.classList.toggle('starred'); return; }
    const tagBtn = e.target.closest('.btn-tag');
    if (tagBtn) { e.preventDefault(); openTagModal(tagBtn.dataset.id); return; }
  });

  // 點長條圖某公司 → 展開/收合該公司職缺面板（委派；展開全部/收合按鈕不觸發）
  $('#company-chart').addEventListener('click', (e) => {
    if (e.target.closest('.co-toggle')) return;
    const row = e.target.closest('.co-row');
    if (row && row.dataset.company) toggleCompanyJobs(row.dataset.company);
  });

  // 公司職缺面板裡的收藏/標籤（與 #article-list 相同的委派）
  $('#company-jobs-panel').addEventListener('click', (e) => {
    const starBtn = e.target.closest('.btn-star');
    if (starBtn) { e.preventDefault(); toggleFavorite(starBtn.dataset.id); starBtn.classList.toggle('starred'); return; }
    const tagBtn = e.target.closest('.btn-tag');
    if (tagBtn) { e.preventDefault(); openTagModal(tagBtn.dataset.id); return; }
  });

  // Tag modal
  $('#tag-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && $('#tag-input').value.trim()) {
      const tag = $('#tag-input').value.trim();
      const tags = getArticleTags(currentTagArticleId);
      if (!tags.includes(tag)) { tags.push(tag); setArticleTags(currentTagArticleId, tags); }
      openTagModal(currentTagArticleId);
    }
  });
  $('#tag-list').addEventListener('click', (e) => {
    if (e.target.dataset.remove) {
      const tags = getArticleTags(currentTagArticleId).filter(t => t !== e.target.dataset.remove);
      setArticleTags(currentTagArticleId, tags);
      openTagModal(currentTagArticleId);
    }
  });
  $('#tag-close').addEventListener('click', () => closeTagModal());
  $('#modal-backdrop').addEventListener('click', () => closeTagModal());
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && $('#tag-modal').classList.contains('is-open')) closeTagModal();
  });

  // Export/Import
  $('#btn-export').addEventListener('click', () => {
    const data = { favorites: [...state.favorites], tags: state.tags };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = `job-radar-favorites-${new Date().toISOString().slice(0, 10)}.json`;
    a.click(); URL.revokeObjectURL(a.href);
  });
  $('#btn-import').addEventListener('change', (e) => {
    const file = e.target.files[0]; if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result);
        if (data.favorites) { state.favorites = new Set([...state.favorites, ...data.favorites]); localStorage.setItem(LS_FAVORITES, JSON.stringify([...state.favorites])); }
        if (data.tags) { Object.assign(state.tags, data.tags); localStorage.setItem(LS_TAGS, JSON.stringify(state.tags)); }
        applyFilters();
      } catch {}
    };
    reader.readAsText(file);
  });

  // Collapsible sections
  $$('.section-toggle').forEach(toggle => {
    toggle.addEventListener('click', () => {
      const target = document.getElementById(toggle.dataset.target);
      if (target) target.classList.toggle('collapsed');
      const icon = toggle.querySelector('.toggle-icon');
      if (icon) icon.style.transform = target.classList.contains('collapsed') ? 'rotate(-90deg)' : '';
    });
  });

  // Mobile nav
  $$('.mobile-nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;
      const sidebar = $('#sidebar');
      const isOpen = sidebar.classList.contains('mobile-open');

      if (view === 'articles') {
        sidebar.classList.remove('mobile-open');
        showDay(state.currentDate);
      } else if (view === 'favorites') {
        sidebar.classList.remove('mobile-open');
        showFavorites();
      } else if (view === 'categories' || view === 'menu') {
        // Toggle sidebar — if already open and clicking same button, close it
        if (isOpen) {
          sidebar.classList.remove('mobile-open');
        } else {
          sidebar.classList.add('mobile-open');
        }
      }
      // Update active state
      $$('.mobile-nav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });

  // Search
  let searchTimeout;
  $('#search-input').addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      const q = $('#search-input').value.trim();
      if (q.length >= 2 && window.searchArticles) {
        const results = window.searchArticles(state.articles, q);
        $('#view-title').textContent = `Search: "${q}"`;
        renderArticles(results);
      } else if (q.length === 0) {
        applyFilters();
        $('#view-title').textContent = state.currentDate;
      }
    }, 300);
  });
}

function updateMobileNav(active) {
  $$('.mobile-nav-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.view === active));
}

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function renderMarkdown(text) {
  if (!text) return '';
  // Escape HTML first so we can safely build tags below
  let html = escHtml(text);

  // Tables (pipe-separated) — process multiline blocks before \n→<br>
  // Pattern: header row | --- separator | body rows
  html = html.replace(
    /(^\|[^\n]+\|\n\|[\s\-:|]+\|\n(?:\|[^\n]+\|\n?)+)/gm,
    (block) => {
      const lines = block.trim().split('\n').filter(l => l.trim().startsWith('|'));
      if (lines.length < 2) return block;
      const headerCells = lines[0].split('|').slice(1, -1).map(c => c.trim());
      const bodyRows = lines.slice(2).map(row => row.split('|').slice(1, -1).map(c => c.trim()));
      const head = '<thead><tr>' + headerCells.map(c => `<th>${c}</th>`).join('') + '</tr></thead>';
      const body = '<tbody>' + bodyRows.map(r => '<tr>' + r.map(c => `<td>${c}</td>`).join('') + '</tr>').join('') + '</tbody>';
      return `<table>${head}${body}</table>`;
    }
  );

  // Headers (process in order: #### before ### before ## before #)
  html = html
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>');

  // Blockquotes
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr>');

  // Bold + italic + inline code
  html = html
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+?)`/g, '<code>$1</code>');

  // Links [text](url) — escHtml already escaped & < > but URLs survive
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // List items (- or numbered)
  html = html
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>');

  // Wrap consecutive <li> in <ul> (basic, no nesting)
  html = html.replace(/(<li>.*?<\/li>)(?:\s*(<li>.*?<\/li>))+/gs, (m) => `<ul>${m}</ul>`);
  html = html.replace(/(?<!<\/?ul>)(<li>[^<]*<\/li>)/g, (m) => `<ul>${m}</ul>`);

  // Newlines → <br>, but skip newlines that are already inside block tags
  // simpler: only convert newlines that aren't adjacent to a closing/opening block tag
  html = html.replace(/\n/g, '<br>');
  // Clean up <br> right before/after block elements (they cause extra spacing)
  html = html.replace(/<br>\s*(<\/?(h[1-6]|table|thead|tbody|tr|th|td|ul|li|blockquote|hr)\b[^>]*>)/g, '$1');
  html = html.replace(/(<\/?(h[1-6]|table|thead|tbody|tr|th|td|ul|li|blockquote|hr)\b[^>]*>)\s*<br>/g, '$1');

  return html;
}

// ═══════════════════════════════════════════
//  Init
// ═══════════════════════════════════════════

async function renderBarometer() {
  const el = document.getElementById('barometer');
  if (!el) return;
  let s = null;
  try { s = await fetchJSON(`${DATA_BASE}/ai_demand.json`); } catch {}
  if (!s || !s.today || !s.today.segment || !s.today.segment.n) { el.style.display = 'none'; return; }
  const seg = s.today.segment, base = s.today.baseline || {}, cum = s.cumulative || {};
  const fmt = (v) => (v == null ? '-' : v);
  const cards = [
    ['今日 AI 工具重要度', fmt(seg.avg_importance), '/100（鎖定職缺）', `共 ${seg.n} 筆`],
    ['歷史平均', fmt(cum.seg_avg_importance), '/100（搜尋以來）', `累積 ${cum.total_segment_jobs || 0} 筆 · ${cum.days || 0} 天`],
    ['今日明文要求 AI', `${fmt(seg.pct_required)}%`, '職缺明文要求 AI 能力', `歷史 ${fmt(cum.seg_pct_required)}%`],
    ['全市場基準', fmt(base.avg_importance), '/100（1111 全產業）', `今日 ${base.n || 0} 筆 · 歷史 ${fmt(cum.base_avg_importance)}`],
  ];
  const cardsHtml = cards.map(([t, v, u, c]) =>
    `<div class="baro-card"><div class="big">${v}</div><div class="sub">${t}${u}</div><div class="ctx">${c}</div></div>`).join('');

  const order = ['工程/技術', '跨域-產品營運', '跨域-行銷內容', '跨域-資料分析', '其他'];
  const bt = seg.by_track || {};
  const bars = order.filter(t => bt[t]).map(t => {
    const v = bt[t].avg_importance || 0;
    return `<div class="track-bar"><span class="tname">${t} (${bt[t].n})</span><span class="bar" style="width:${Math.max(2, v * 1.6)}px"></span><span class="tval">${v}</span></div>`;
  }).join('');
  const barsBlock = bars ? `<div class="track-bars"><div class="t-title">今日各軌道平均 AI 工具重要度</div>${bars}</div>` : '';

  const pts = (s.trend || []).filter(h => (h.n_segment || 0) > 0).map(h => [h.date, h.seg_avg_importance || 0]);
  let trendBlock = '<div class="trend-wrap"><div class="t-title">趨勢線（資料累積中，需 ≥2 天）</div></div>';
  if (pts.length >= 2) {
    const w = 640, h = 90, n = pts.length;
    const xs = pts.map((_, i) => i * (w - 20) / (n - 1) + 10);
    const ys = pts.map(p => h - 10 - (p[1] / 100) * (h - 20));
    const poly = xs.map((x, i) => `${x.toFixed(0)},${ys[i].toFixed(0)}`).join(' ');
    const dots = xs.map((x, i) => `<circle cx="${x.toFixed(0)}" cy="${ys[i].toFixed(0)}" r="2.5" fill="#60a5fa"/>`).join('');
    trendBlock = `<div class="trend-wrap"><div class="t-title">AI 工具重要度趨勢（${pts[0][0].slice(5)} → ${pts[n - 1][0].slice(5)}）</div><svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none"><polyline points="${poly}" fill="none" stroke="#60a5fa" stroke-width="2"/>${dots}</svg></div>`;
  }

  el.style.display = '';
  el.innerHTML = `<h2>📡 AI 需求溫度計</h2><div class="goal">追蹤台灣職場「使用 AI 工具」的需求強度與變化趨勢</div>`
    + `<div class="baro-grid">${cardsHtml}</div>${barsBlock}${trendBlock}`
    + `<div class="caveat">※ 鎖定樣本以 AI／跨域關鍵字搜尋，絕對值代表「該區段」而非全體勞動市場；趨勢比絕對值更可靠。「全市場基準」取自 1111 全產業最新職缺樣本對照。</div>`;
}

async function init() {
  setupEvents();
  renderBarometer();

  // Load manual tags
  try {
    const mt = await fetchJSON(`${DATA_BASE}/manual-tags.json`);
    if (mt && Array.isArray(mt)) mt.forEach(t => state.manualTags.add(t));
  } catch {}

  // Load curated dates index
  try {
    const curated = await fetchJSON(`${DATA_BASE}/curated-dates.json`);
    if (curated && typeof curated === 'object') state.curatedDates = curated;
  } catch {}

  // Sync tag folders with version check
  try {
    const defaults = await fetchJSON(`${DATA_BASE}/default-tags.json`);
    if (defaults && Array.isArray(defaults)) {
      const TAG_VERSION = 6;  // bump this when defaults change
      const savedVersion = parseInt(localStorage.getItem('job-radar-tag-version') || '0');
      if (savedVersion < TAG_VERSION) {
        // Fresh install or version upgrade: use defaults only
        state.tagFolders = defaults;
        saveTagFolders();
        localStorage.setItem('job-radar-tag-version', String(TAG_VERSION));
      }
    }
  } catch {}

  // Load default child-tag assignments (article → child tag mapping)
  try {
    const defaultChildTags = await fetchJSON(`${DATA_BASE}/default-article-tags.json`);
    if (defaultChildTags && typeof defaultChildTags === 'object') {
      let merged = 0;
      for (const [artId, childTags] of Object.entries(defaultChildTags)) {
        const existing = state.tags[artId] || [];
        for (const ct of childTags) {
          if (!existing.includes(ct)) { existing.push(ct); merged++; }
        }
        if (existing.length > 0) state.tags[artId] = existing;
      }
      if (merged > 0) localStorage.setItem(LS_TAGS, JSON.stringify(state.tags));
    }
  } catch {}

  // Render tag tree from localStorage
  renderTagTree();

  // Build date index for calendar
  await buildDateIndex();

  // Find latest date with data
  const sorted = [...state.availableDates].sort();
  if (sorted.length > 0) {
    const latest = sorted[sorted.length - 1];
    state.calYear = parseInt(latest.slice(0, 4));
    state.calMonth = parseInt(latest.slice(5, 7)) - 1;
    await showDay(latest);
  } else {
    renderCalendar();
    await showDay(new Date().toISOString().slice(0, 10));
  }
}

init();
