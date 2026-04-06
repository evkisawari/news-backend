const express = require('express');
const router = express.Router();
const axios = require('axios');
const OpenAI = require('openai');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const Parser = require('rss-parser');

const DB_PATH = path.join(__dirname, '../db.json');

// ─────────────────────────────────────────────
// CONFIGURATION
// ─────────────────────────────────────────────
const CONFIG = {
  POOL_TTL_MS:        3 * 60 * 1000,   // 3-minute session pools
  POOL_JITTER_MS:     15 * 1000,        // ±15s jitter to avoid sync spikes
  POOL_MAX_SIZE:      100,
  POOL_LOCK_TIMEOUT:  5 * 1000,         // 5s max lock wait
  SOURCE_CACHE_TTL:   10 * 60 * 1000,  // 10-minute source cache
  SUMMARY_CACHE_TTL:  60 * 60 * 1000,  // 1-hour summary cache
  FETCH_LIMIT_MULT:   2,                // fetchLimit = limit * 2, min 20
  RECENCY_HALF_LIFE:  12,               // hours for exponential decay
  RECENCY_FLOOR:      0.1,
  AI_MAX_CONCURRENT:  2,                // max parallel OpenAI calls
  AI_BATCH_SIZE:      4,                // articles per enrichment cycle
  AI_MAX_QUEUE:       50,               // cap queue to avoid runaway
  COOLDOWN_MS:        10 * 1000,        // 10s refresh cooldown
  RANGES_HOURS:       [24, 48, 72],     // parallel fetch windows
};

const BOOST_KEYWORDS = {
  world:      ['war', 'crisis', 'election', 'conflict', 'sanctions', 'diplomacy', 'military'],
  finance:    ['market', 'crash', 'inflation', 'fed', 'recession', 'earnings'],
  technology: ['ai', 'hack', 'breach', 'breakthrough', 'regulation', 'ban'],
  lifestyle:  ['health', 'recall', 'breakthrough', 'study'],
  us:         ['president', 'congress', 'supreme court', 'fda', 'shooting'],
};

const RSS_SOURCES = [
  { name: 'BBC News', url: 'http://feeds.bbci.co.uk/news/rss.xml', category: 'world', weight: 1.5 },
  { name: 'Reuters', url: 'https://feeds.reuters.com/reuters/topNews', category: 'world', weight: 1.5 },
  { name: 'AP News', url: 'https://apnews.com/apf-topnews?format=xml', category: 'world', weight: 1.5 },
  { name: 'Guardian', url: 'https://www.theguardian.com/world/rss', category: 'world', weight: 1.3 },
  { name: 'CNN', url: 'http://rss.cnn.com/rss/edition.rss', category: 'world', weight: 1.2 },
  { name: 'NYT', url: 'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml', category: 'us', weight: 1.5 },
  { name: 'Fox News', url: 'https://moxie.foxnews.com/google-publisher/latest.xml', category: 'us', weight: 1.2 },
  { name: 'TechCrunch', url: 'https://techcrunch.com/feed/', category: 'technology', weight: 1.4 },
  { name: 'The Verge', url: 'https://www.theverge.com/rss/index.xml', category: 'technology', weight: 1.3 },
  { name: 'Wired', url: 'https://www.wired.com/feed/rss', category: 'technology', weight: 1.3 },
  { name: 'Hacker News', url: 'https://hnrss.org/frontpage', category: 'technology', weight: 1.1 },
  { name: 'CNBC', url: 'https://www.cnbc.com/id/100003114/device/rss/rss.html', category: 'finance', weight: 1.4 },
  { name: 'Bloomberg', url: 'https://feeds.bloomberg.com/markets/news.rss', category: 'finance', weight: 1.5 },
  { name: 'Google News', url: 'https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en', category: 'us', weight: 1.0 },
  { name: 'Google News Tech', url: 'https://news.google.com/rss/search?q=technology', category: 'technology', weight: 1.0 }
];

const parser = new Parser({
  customFields: {
    item: [
      ['media:content', 'media', {keepArray: true}],
      ['media:thumbnail', 'mediaThumbnail', {keepArray: true}],
      ['media:group', 'mediaGroup', {keepArray: true}],
      ['enclosure', 'enclosure', {keepArray: true}]
    ]
  }
});

// ─────────────────────────────────────────────
// CACHE STORES
// ─────────────────────────────────────────────
const sourceCache   = new Map(); // GNews raw results
const summaryCache  = new Map(); // AI summaries { text, timestamp }
const sessionPools  = new Map(); // Ranked article pools
const poolLocks     = new Map(); // Promise-based build locks
const cooldownMap   = new Map(); // Per-type refresh cooldown
const lastGoodPool  = new Map(); // Fallback: last successful pool

// ─────────────────────────────────────────────
// OPENAI CLIENT
// ─────────────────────────────────────────────
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

// ─────────────────────────────────────────────
// AI PRIORITY QUEUE (Anti-Starvation + Throttle)
// ─────────────────────────────────────────────
const aiQueue    = [];
const aiInFlight = new Set();
let   aiWorkerRunning = false;

function enqueueAI(article, priority = 0) {
  if (aiQueue.length >= CONFIG.AI_MAX_QUEUE) return;
  const url = article.url;
  if (summaryCache.has(url)) return; // Already cached
  if (aiInFlight.has(url)) return;   // Currently processing
  if (aiQueue.some(j => j.url === url)) return; // Already queued

  aiQueue.push({ article, url, priority, enqueuedAt: Date.now() });
  aiQueue.sort((a, b) => {
    // Anti-starvation: age boost of 0.1 per second waiting
    const aScore = a.priority + (Date.now() - a.enqueuedAt) / 10000;
    const bScore = b.priority + (Date.now() - b.enqueuedAt) / 10000;
    return bScore - aScore;
  });

  if (!aiWorkerRunning) runAIWorker();
}

async function runAIWorker() {
  aiWorkerRunning = true;
  while (aiQueue.length > 0 && aiInFlight.size < CONFIG.AI_MAX_CONCURRENT) {
    const batch = aiQueue.splice(0, CONFIG.AI_BATCH_SIZE);
    const jobs  = batch.map(job => processAIJob(job));
    await Promise.allSettled(jobs);
  }
  aiWorkerRunning = aiQueue.length > 0;
  if (aiWorkerRunning) setTimeout(runAIWorker, 500);
}

async function processAIJob({ article, url }) {
  if (summaryCache.has(url)) return;
  aiInFlight.add(url);
  try {
    const summary = await fetchAISummary(article);
    if (summary) {
      summaryCache.set(url, { text: summary, timestamp: Date.now() });
      
      // Persist to JSON DB
      const db = loadDB();
      const idx = db.findIndex(a => a._stableId === article._stableId);
      if (idx !== -1) {
        db[idx].aiSummary = summary;
        saveDB(db);
      }
    }
  } finally {
    aiInFlight.delete(url);
  }
}

async function fetchAISummary(article) {
  const fullText = `${article.title}. ${article.description || ''} ${article.content || ''}`.trim();
  if (fullText.length < 50) return null;

  const response = await openai.responses.create({
    model: 'gpt-5-nano',
    input: `You are a professional news editor creating summaries for a mobile news app like Inshorts.

Task:
Summarize the given news article into a concise, clear, and engaging summary for fast mobile reading.

Rules:
- Target length: 55–65 words
- Focus on key facts only (who, what, where, why)
- No opinions, speculation, or filler
- Single paragraph, neutral language
- Do NOT repeat the headline
- Do NOT say "the article says"

Output: Return ONLY the summary text.

Article:
${fullText.substring(0, 1500)}`,
    store: true,
  }, { timeout: 8000 });

  return response.output_text?.trim() || null;
}

// ─────────────────────────────────────────────
// UTILITY: CONTENT VALIDATION
// ─────────────────────────────────────────────
function isEnglish(text) {
  if (!text) return true;
  // Basic ASCII check — rejects titles with too many non-English characters
  const nonAsciis = text.match(/[^\x00-\x7F]/g) || [];
  return (nonAsciis.length / text.length) < 0.1;
}

function cleanArticleURL(urlStr) {
  try {
    const url = new URL(urlStr);
    // Strip common tracking parameters
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'ref', 'source'].forEach(p => url.searchParams.delete(p));
    
    const domain = url.hostname.toLowerCase();
    const pathname = url.pathname.toLowerCase();

    // Reject Known Garbage (Image CDNs, short-links, and absolute redirectors)
    const garbageDomains = ['guim.co.uk', 'cnn.it', 'bit.ly', 'tinyurl.com', 'feeds.reuters.com'];
    if (garbageDomains.some(d => domain.includes(d))) return null;
    
    // Reject non-HTML extensions
    if (pathname.match(/\.(jpg|jpeg|png|gif|webp|svg|mp4|mp3|pdf|txt|xml|json)$/)) return null;

    return url.toString();
  } catch {
    return null;
  }
}

function getFallbackImage(source) {
  const map = {
    'BBC News':     'https://upload.wikimedia.org/wikipedia/commons/thumb/6/62/BBC_News_2019.svg/1200px-BBC_News_2019.svg.png',
    'Reuters':     'https://www.reuters.com/pf/resources/images/reuters/logo-vertical.png?d=122',
    'AP News':      'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Associated_Press_logo_2012.svg/1200px-Associated_Press_logo_2012.svg.png',
    'Guardian':     'https://assets.guim.co.uk/images/favicons/og-image.png',
    'CNN':          'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/CNN.svg/1200px-CNN.svg.png',
    'NYT':          'https://static01.nyt.com/images/misc/NYT_logo_rss_250x40.png',
    'Fox News':     'https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Fox_News_Channel_logo.svg/1200px-Fox_News_Channel_logo.svg.png',
    'TechCrunch':   'https://techcrunch.com/wp-content/uploads/2015/02/cropped-cropped-favicon-gradient.png',
    'The Verge':    'https://upload.wikimedia.org/wikipedia/commons/thumb/a/af/The_Verge_logo.svg/1200px-The_Verge_logo.svg.png',
    'Wired':        'https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Wired_logo.svg/1200px-Wired_logo.svg.png',
    'CNBC':         'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/CNBC_logo.svg/1200px-CNBC_logo.svg.png',
    'Bloomberg':    'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Bloomberg_Logo.svg/1200px-Bloomberg_Logo.svg.png',
    'Google News': 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/da/Google_News_icon.svg/1200px-Google_News_icon.svg.png'
  };

  return map[source] || 'https://via.placeholder.com/1200x800?text=News+Update';
}

// ─────────────────────────────────────────────
// UTILITY: METADATA SCRAPER (Fallback for missing RSS images)
// ─────────────────────────────────────────────
const imageScrapeCache = new Map();

async function scrapeArticleImage(url) {
  if (!url) return null;
  if (imageScrapeCache.has(url)) return imageScrapeCache.get(url);

  try {
    // Perform a lightweight GET request for the first 10KB of HTML
    const response = await axios.get(url, { 
      timeout: 3000, 
      headers: { 'User-Agent': 'Mozilla/5.0' },
      responseType: 'text',
      maxContentLength: 50000 // Limit to 50KB to save bandwidth
    });

    // Match og:image or twitter:image
    const ogMatch = response.data.match(/<meta [^>]*property=["']og:image["'] [^>]*content=["']([^"']+)["']/i) ||
                    response.data.match(/<meta [^>]*content=["']([^"']+)["'] [^>]*property=["']og:image["']/i);
    
    const src = ogMatch ? ogMatch[1] : null;

    if (src && src.startsWith('http')) {
      imageScrapeCache.set(url, src);
      return src;
    }
  } catch (err) {
    // Silent fail for scraper to avoid blocking the main feed
  }
  return null;
}

function extractImage(item) {
  const candidates = [];
  const push = (obj) => {
    if (!obj || !obj.url) return;
    const url = obj.url;
    if (url.includes('pixel') || url.includes('tracking') || url.includes('/1x1') || !url.startsWith('http')) return;
    candidates.push(obj);
  };

  // 1. Check media:content
  const media = [].concat(item.media || []);
  media.forEach(m => push(m.$ || m));

  // 2. Check mediaGroup
  const group = [].concat(item.mediaGroup || []);
  group.forEach(g => {
    if (g['media:content']) {
      const contents = [].concat(g['media:content']);
      contents.forEach(c => push(c.$ || c));
    }
  });

  // 3. Check enclosure
  const enclosures = [].concat(item.enclosure || []);
  enclosures.forEach(e => push(e.$ || e));

  // 4. Check mediaThumbnail
  const thumbs = [].concat(item.mediaThumbnail || []);
  thumbs.forEach(t => push(t.$ || t));

  if (candidates.length > 0) {
    const sorted = candidates.sort((a, b) => {
      const resA = (parseInt(a.width) || 0) * (parseInt(a.height) || 0);
      const resB = (parseInt(b.width) || 0) * (parseInt(b.height) || 0);
      if (resB !== resA) return resB - resA;
      const score = (url) => {
        let s = 0;
        if (url.includes('large')) s += 10;
        if (url.includes('orig')) s += 10;
        return s;
      };
      return score(b.url) - score(a.url);
    });
    return sorted[0].url;
  }

  // 5. Regex Scan (Raw HTML fields)
  const body = item['content:encoded'] || item.content || item.description || '';
  const imgRegex = /<img[^>]+src=["']([^"']+)["']/gi;
  let match;
  while ((match = imgRegex.exec(body)) !== null) {
    const src = match[1];
    if (src.includes('pixel') || src.includes('tracking') || src.includes('share') || !src.startsWith('http')) continue;
    return src; // Returns the first non-tracker image from body
  }

  return null;
}

function stripHTML(html) {
  if (!html) return '';
  return html
    .replace(/<[^>]*>?/gm, '') // Remove tags
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .trim();
}

// ─────────────────────────────────────────────
// UTILITY: MD5 Hash
// ─────────────────────────────────────────────
function hash(data) {
  return crypto.createHash('md5').update(String(data)).digest('hex');
}

// ─────────────────────────────────────────────
// UTILITY: JSON DB HELPERS
// ─────────────────────────────────────────────
function loadDB() {
  try {
    if (!fs.existsSync(DB_PATH)) return [];
    const data = fs.readFileSync(DB_PATH, 'utf8');
    return JSON.parse(data) || [];
  } catch (err) {
    console.error('[DB] Load Error:', err.message);
    return [];
  }
}

function saveDB(articles) {
  try {
    // 6. Remove Old Articles (> 48 hours)
    const now = Date.now();
    const freshArticles = articles.filter(a => (now - new Date(a.publishedAt).getTime()) < 48 * 3600 * 1000);
    
    // 9. Trim (Top 500)
    const finalPool = freshArticles.slice(0, 500);
    
    fs.writeFileSync(DB_PATH, JSON.stringify(finalPool, null, 2));
    console.log(`[DB] Saved ${finalPool.length} articles to high-speed pool.`);
  } catch (err) {
    console.error('[DB] Save Error:', err.message);
  }
}

// ─────────────────────────────────────────────
// UTILITY: Pool time bucket with jitter
// ─────────────────────────────────────────────
function getTimeBucket(type) {
  // Spread rebuilds across the pool TTL window using type-based offset
  const offset = hash(type).charCodeAt(0) % (CONFIG.POOL_JITTER_MS * 2) - CONFIG.POOL_JITTER_MS;
  return Math.floor((Date.now() + offset) / CONFIG.POOL_TTL_MS);
}

function getPoolKey(type) {
  return `${type}:${getTimeBucket(type)}`;
}

// ─────────────────────────────────────────────
// UTILITY: TTL Cache Cleanup
// ─────────────────────────────────────────────
function evictExpiredCaches() {
  const now = Date.now();

  for (const [key, val] of sessionPools.entries()) {
    if (now - val.timestamp > CONFIG.POOL_TTL_MS + CONFIG.POOL_JITTER_MS * 2) {
      sessionPools.delete(key);
    }
  }

  for (const [key, val] of summaryCache.entries()) {
    if (now - val.timestamp > CONFIG.SUMMARY_CACHE_TTL) {
      summaryCache.delete(key);
    }
  }

  for (const [key, val] of sourceCache.entries()) {
    if (now - val.timestamp > CONFIG.SOURCE_CACHE_TTL) {
      sourceCache.delete(key);
    }
  }
}

setInterval(evictExpiredCaches, 60 * 1000); // Cleanup every minute

// ─────────────────────────────────────────────
// GNEWS FETCHER (with source-level cache)
// ─────────────────────────────────────────────
// ─────────────────────────────────────────────
// 3. NORMALIZE RSS ITEM
// ─────────────────────────────────────────────
function normalizeRSSItem(item, source) {
  const publishedAt = item.pubDate || item.isoDate || new Date().toISOString();
  const rawTitle    = (item.title || 'Untitled').trim();
  
  // 1. English-Only Guard
  if (!isEnglish(rawTitle)) return null;

  // 4. URL Sanitization
  const link = cleanArticleURL(item.link || item.guid || '');
  if (!link) return null;

  // 5. Global Fingerprint (for ID stability)
  const fp = hash(rawTitle.toLowerCase().trim().replace(/[^a-z0-9]/g, ''));
  
  // 3. Precise Image Extraction (Refined Logic)
  let image = extractImage(item);

  // 6. FORCE IMAGE FALLBACK (Logo mapping)
  if (!image) {
     image = getFallbackImage(source.name);
  }

  // 7. CLEAN DESCRIPTION (HTML Stripping)
  const cleanDesc = stripHTML(item.contentSnippet || item.description || '');

  return {
    title: rawTitle,
    description: cleanDesc.substring(0, 480),
    url: link,
    source: source.name,
    category: source.category,
    publishedAt,
    image,
    _fp: fp,
    _stableId: fp,
    _weight: source.weight
  };
}

// ─────────────────────────────────────────────
// 2. PARALLEL RSS FETCH
// ─────────────────────────────────────────────
async function fetchSource(source) {
  try {
    const feed = await parser.parseURL(source.url);
    return feed.items.map(item => normalizeRSSItem(item, source));
  } catch (err) {
    console.error(`[RSS ERROR] ${source.name}:`, err.message);
    return [];
  }
}

// ─────────────────────────────────────────────
// 7. SCORING ENGINE (Recency + Weight + Keyword)
// ─────────────────────────────────────────────
// ─────────────────────────────────────────────
// 7. SCORING ENGINE (Recency + Weight + Keyword)
// ─────────────────────────────────────────────
function calculateScore(article) {
  const publishedMs  = new Date(article.publishedAt).getTime();
  const ageHours     = (Date.now() - publishedMs) / 3600000;
  
  // Exponential decay (50% weight) - returns high-precision float
  const recencyScore = Math.max(CONFIG.RECENCY_FLOOR, Math.exp(-ageHours / CONFIG.RECENCY_HALF_LIFE));
  
  // Weight (30% weight)
  const weightScore = article._weight || 1.0;
  
  // Keyword Boost (20% weight)
  const boostKeywords = BOOST_KEYWORDS[article.category] || [];
  const titleLower    = article.title.toLowerCase();
  const hasBoost      = boostKeywords.some(k => titleLower.includes(k));
  const boostScore    = hasBoost ? 1.0 : 0.0;

  // Final Composite Score (0.0 to 1.0)
  return parseFloat(((0.5 * recencyScore) + (0.3 * (weightScore/2)) + (0.2 * boostScore)).toFixed(4));
}

// ─────────────────────────────────────────────
// SCORING ENGINE
// ─────────────────────────────────────────────
// ─────────────────────────────────────────────
// 11. CLUSTER & DEDUPLICATE (Game Changer)
// ─────────────────────────────────────────────
function clusterAndDeduplicate(articles) {
  const clusters = {};

  articles.forEach(a => {
    // Basic version (fast): key by first 50 chars of normalized title
    const key = a.title.toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 50);

    if (!clusters[key]) clusters[key] = [];
    clusters[key].push(a);
  });

  // Flat version: pick highest scored article from each cluster (Source Priority)
  return Object.values(clusters).map(cluster => {
    return cluster.sort((a, b) => b._score - a._score)[0];
  });
}

// ─────────────────────────────────────────────
// 10. SYNC UNIFIED RSS (11-Step Pipeline)
// ─────────────────────────────────────────────
async function syncUnifiedRSS() {
  console.log('[CRON] Starting 11-step RSS engine sync...');
  
  try {
    // 2. Parallel RSS Fetch
    const results = await Promise.allSettled(RSS_SOURCES.map(s => fetchSource(s)));
    
    // 3. Normalize & 4. Filter Trusted
    const rawArticles = results
      .filter(r => r.status === 'fulfilled')
      .flatMap(r => r.value)
      .filter(a => a !== null);

    // 7. Score
    const scored = rawArticles.map(a => ({
      ...a,
      _score: calculateScore(a)
    }));

    // 11. Cluster & Deduplicate (Pick best source per story)
    const unique = clusterAndDeduplicate(scored);

    // 8. Sort Global (By Rating)
    unique.sort((a, b) => b._score - a._score);

    // 9. Trim & 10. Save db.json
    saveDB(unique);
    
    console.log('[CRON] RSS pipeline complete.');
  } catch (err) {
    console.error('[CRON ERROR] RSS sync failed:', err.message);
  }
}

// ─────────────────────────────────────────────
// POOL BUILDER (Refactored for RSS)
// ─────────────────────────────────────────────
async function buildOrGetPool(type) {
  const poolKey = getPoolKey(type);
  
  // 1. Try Session Cache
  if (sessionPools.has(poolKey)) {
    return sessionPools.get(poolKey).articles;
  }

  // 2. Read from local Mega-Pool DB
  const db = loadDB();
  const pool = db
    .filter(a => a.category === type || type === 'us') // default to us
    .slice(0, 100);

  if (pool.length > 0) {
    sessionPools.set(poolKey, { articles: pool, timestamp: Date.now() });
    
    // Trigger AI enrichment for top articles
    pool.slice(0, 10).forEach((a, i) => enqueueAI(a, 10 - i));
  } else {
    console.warn(`[POOL] DB is empty for ${type}. Triggering sync...`);
    syncUnifiedRSS();
  }

  return pool;
}

// ─────────────────────────────────────────────
// DESCRIPTION FALLBACK (improved)
// ─────────────────────────────────────────────
function buildFallbackDescription(article) {
  const src   = (article.description || article.content || '').trim();
  const words = src.split(/\s+/).filter(Boolean);
  // Use up to 55 words of natural content — no artificial sentence padding
  return words.slice(0, 55).join(' ') + (words.length > 55 ? '...' : '');
}

// ─────────────────────────────────────────────
// CRON SYNC WRAPPER
// ─────────────────────────────────────────────
async function runCronFetch() {
  await syncUnifiedRSS();
}

// Run initial sync after 3 second delay
setTimeout(runCronFetch, 3000);

// ─────────────────────────────────────────────
// GET /api/news
// ─────────────────────────────────────────────
router.get('/', async (req, res) => {
  try {
    const page    = Math.max(1, parseInt(req.query.page) || 1);
    const limit   = Math.min(50, Math.max(1, parseInt(req.query.limit) || 10));
    const type    = (req.query.type || 'us').toLowerCase();
    const refresh = req.query.refresh === 'true';

    // ── Cooldown check ──────────────────────────────────────
    const now          = Date.now();
    const lastRefresh  = cooldownMap.get(type) || 0;
    const onCooldown   = refresh && (now - lastRefresh < CONFIG.COOLDOWN_MS);

    let forceRefresh = refresh && !onCooldown;
    if (forceRefresh) cooldownMap.set(type, now);

    // ── Get pool (Local-First) ──────────────────────────────
    let pool = [];
    
    if (refresh) {
      console.log(`[REFRESH] Background RSS sync triggered for ${type}`);
      runCronFetch(); 
    }
    
    // 1. Try Session Cache
    const poolKey = getPoolKey(type);
    if (!refresh && sessionPools.has(poolKey)) {
      pool = sessionPools.get(poolKey).articles;
    } else {
      // 2. Serve from Local ranked DB
      pool = await buildOrGetPool(type);
    }

    if (!pool || pool.length === 0) {
      // Absolute final fallback — return empty success rather than 500
      return res.json({
        success: true, type, page, limit, total: 0,
        articles: [], meta: { fromCache: true, poolSize: 0 },
      });
    }

    // ── Slice for pagination ─────────────────────────────────
    const startIdx  = (page - 1) * limit;
    const pageSlice = pool.slice(startIdx, startIdx + limit);

    // Enqueue this page's articles for AI (high priority)
    pageSlice.forEach((a, i) => enqueueAI(a, 50 - i));

    // ── Transform response ───────────────────────────────────
    const articles = await Promise.all(pageSlice.map(async (item, idx) => {
      const cachedSummary = summaryCache.get(item.url);
      const aiSummary     = cachedSummary ? cachedSummary.text : null;
      const description   = aiSummary || buildFallbackDescription(item);

      // Robust Image Fetch (Local first, then Scraper)
      let image = item.image;
      if (!image || image.includes('placeholder')) {
        const scraped = await scrapeArticleImage(item.url);
        if (scraped) image = scraped;
      }

      return {
        id:          startIdx + idx + 1,
        stableId:    item._stableId,
        title:       item.title,
        description,
        aiSummary,
        hasAiSummary: !!aiSummary,
        image:       image && image.startsWith('http') ? image : null,
        url:         item.url,
        source:      item.source || 'Unknown',
        publishedAt: item.publishedAt,
        score:       parseFloat((item._score || 0).toFixed(4)),
      };
    }));

    res.json({
      success: true,
      type,
      page,
      limit,
      total:    pool.length,
      articles,
      meta: {
        poolSize:      pool.length,
        poolKey:       getPoolKey(type),
        fromCooldown:  onCooldown,
        aiQueueDepth:  aiQueue.length,
        aiInFlight:    aiInFlight.size,
      },
    });

  } catch (err) {
    console.error('[NEWS ROUTE ERROR]', err.message);
    res.status(500).json({ success: false, error: 'News engine failure', detail: err.message });
  }
});

module.exports = {
  router,
  runCronFetch: syncUnifiedRSS
};
