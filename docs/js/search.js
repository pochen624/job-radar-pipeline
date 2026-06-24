/* ═══════════════════════════════════════════
   AI Digest Archive — Search (Fuse.js)
   ═══════════════════════════════════════════ */

/**
 * Search articles using Fuse.js fuzzy search.
 * Called from app.js via window.searchArticles.
 */
window.searchArticles = function(articles, query) {
  if (!articles || articles.length === 0 || !query) return [];

  if (typeof Fuse === 'undefined') {
    // Fallback: simple substring match if Fuse.js CDN fails
    const q = query.toLowerCase();
    return articles.filter(a =>
      (a.title || '').toLowerCase().includes(q) ||
      (a.ai_summary || '').toLowerCase().includes(q) ||
      (a.source || '').toLowerCase().includes(q) ||
      (a.tags || []).some(t => t.toLowerCase().includes(q))
    );
  }

  const fuse = new Fuse(articles, {
    keys: [
      { name: 'title', weight: 0.4 },
      { name: 'ai_summary', weight: 0.3 },
      { name: 'source', weight: 0.15 },
      { name: 'tags', weight: 0.15 },
    ],
    threshold: 0.35,
    includeScore: true,
    minMatchCharLength: 2,
  });

  return fuse.search(query).map(r => r.item);
};
