const express = require('express');
const router = express.Router();
const axios = require('axios');
const OpenAI = require('openai');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

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

const CATEGORY_STRATEGIES = {
  us:         { headlines: { country: 'us', category: 'general', lang: 'en' } },
  world:      { headlines: { lang: 'en' },
                search:    { q: 'war OR conflict OR election OR government OR military OR sanctions OR diplomacy', sortBy: 'publishedAt' } },
  finance:    { headlines: { category: 'business', lang: 'en' },
                search:    { q: 'market OR stocks OR economy OR inflation OR earnings', sortBy: 'publishedAt' } },
  technology: { headlines: { category: 'technology', lang: 'en' },
                search:    { q: 'AI OR software OR startup OR cybersecurity OR "big tech"', sortBy: 'publishedAt' } },
  lifestyle:  { headlines: { category: 'entertainment', lang: 'en' },
                search:    { q: 'travel OR food OR health OR fitness OR fashion', sortBy: 'publishedAt' } },
};

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
    // Maintain max DB size and auto-purge (7 days)
    const now = Date.now();
    const cleanArticles = articles
      .filter(a => (now - new Date(a.publishedAt).getTime()) < 7 * 24 * 3600 * 1000)
      .slice(0, 2000); // Max 2000 items in DB pool
    
    fs.writeFileSync(DB_PATH, JSON.stringify(cleanArticles, null, 2));
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
async function fetchGNews(endpoint, params) {
  const gUrl      = endpoint === 'search'
    ? 'https://gnews.io/api/v4/search'
    : 'https://gnews.io/api/v4/top-headlines';
  const sourceKey = `${endpoint}:${JSON.stringify(params)}`;

  if (sourceCache.has(sourceKey)) {
    const cached = sourceCache.get(sourceKey);
    if (Date.now() - cached.timestamp < CONFIG.SOURCE_CACHE_TTL) {
      return cached.data;
    }
  }

  try {
    const resp = await axios.get(gUrl, {
      params: { ...params, token: process.env.GNEWS_API_KEY },
      timeout: 30000,
    });
    const data = {
      articles:      resp.data.articles      || [],
      totalArticles: resp.data.totalArticles || 0,
    };
    sourceCache.set(sourceKey, { data, timestamp: Date.now() });
    return data;
  } catch (err) {
    console.error(`[GNews ERROR] ${endpoint}:`, err.message);
    return { articles: [], totalArticles: 0 };
  }
}

// ─────────────────────────────────────────────
// PARALLEL RANGE FETCH (0-24h,24-48h,48-72h)
// ─────────────────────────────────────────────
async function fetchParallelRanges(strategy, fetchLimit) {
  const now   = new Date();
  const ranges = CONFIG.RANGES_HOURS.map((hours, i) => {
    const prevHours = CONFIG.RANGES_HOURS[i - 1] || 0;
    const fromDate  = new Date(now - hours * 3600 * 1000).toISOString();
    const toDate    = prevHours === 0 ? now.toISOString()
      : new Date(now - prevHours * 3600 * 1000).toISOString();
    return { from: fromDate, to: toDate, label: `${prevHours}–${hours}h` };
  });

  const fetches = [];
  for (const range of ranges) {
    const params = { max: 10, from: range.from, to: range.to, lang: 'en' };
    // GNews FREE tier doesn't allow from/to on /top-headlines
    if (strategy.headlines && range.label === '0–24h') {
      const { from, to, ...headlineParams } = params;
      fetches.push(
        fetchGNews('headlines', { ...strategy.headlines, ...headlineParams })
          .then(r => ({ ...r, rangeLabel: range.label }))
      );
    }
    if (strategy.search) {
      fetches.push(
        fetchGNews('search', { ...strategy.search, ...params })
          .then(r => ({ ...r, rangeLabel: range.label }))
      );
    }
    if (strategy.headlines && range.label !== '0–24h') {
       const { from, to, ...headlineParams } = params;
       fetches.push(
        fetchGNews('headlines', { ...strategy.headlines, ...headlineParams })
          .then(r => ({ ...r, rangeLabel: range.label }))
      );
    }
  }

  const results    = await Promise.allSettled(fetches);
  const seenFp     = new Set();
  const merged     = [];
  let   totalCount = 0;

  for (const result of results) {
    if (result.status !== 'fulfilled') continue;
    const { articles, totalArticles } = result.value;
    totalCount = Math.max(totalCount, totalArticles || 0);

    for (const article of articles) {
      if (merged.length >= fetchLimit) break;
      const descSnippet = (article.description || '').substring(0, 80).toLowerCase();
      const sourceName  = (article.source?.name || '').toLowerCase();
      const fp          = hash(article.title.toLowerCase() + sourceName + descSnippet);
      if (!seenFp.has(fp)) {
        seenFp.add(fp);
        merged.push({ ...article, _fp: fp, _stableId: hash(article.url || article.title + article.publishedAt) });
      }
    }
    if (merged.length >= fetchLimit) break;
  }

  return { articles: merged, totalArticles: totalCount };
}

// ─────────────────────────────────────────────
// SCORING ENGINE
// ─────────────────────────────────────────────
function scoreArticle(article, boostKeywords, sourceFreq) {
  // 1. Recency — exponential decay with floor
  const publishedMs  = new Date(article.publishedAt).getTime();
  const ageHours     = (Date.now() - publishedMs) / 3600000;
  const recencyScore = Math.max(CONFIG.RECENCY_FLOOR, Math.exp(-ageHours / CONFIG.RECENCY_HALF_LIFE));

  // 2. Boost — capped at 1.0
  const titleLower = (article.title || '').toLowerCase();
  const boostScore = boostKeywords.some(k => titleLower.includes(k)) ? 1.0 : 0.0;

  // 3. Diversity — 1 / sqrt(frequency) to penalize source dominance
  const freq         = sourceFreq.get(article.source?.name || 'unknown') || 1;
  const diversScore  = 1 / Math.sqrt(freq);

  return (0.5 * recencyScore) + (0.3 * boostScore) + (0.2 * diversScore);
}

// ─────────────────────────────────────────────
// TIERED SHUFFLE (Applied ONCE at pool build)
// ─────────────────────────────────────────────
function tieredShuffle(articles) {
  const arr  = [...articles];
  const mid  = Math.ceil(arr.length / 2);
  const top  = arr.slice(0, mid);
  const bot  = arr.slice(mid);

  // Top 50%: light probabilistic swap (swap if random < 0.15)
  for (let i = top.length - 1; i > 0; i--) {
    if (Math.random() < 0.15) {
      const j = Math.floor(Math.random() * (i + 1));
      [top[i], top[j]] = [top[j], top[i]];
    }
  }

  // Bottom 50%: full Fisher-Yates shuffle
  for (let i = bot.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [bot[i], bot[j]] = [bot[j], bot[i]];
  }

  return [...top, ...bot];
}

// ─────────────────────────────────────────────
// POOL BUILDER (with Promise-based locking)
// ─────────────────────────────────────────────
async function buildOrGetPool(type, forceRefresh = false) {
  const poolKey       = getPoolKey(type);
  const strategy      = CATEGORY_STRATEGIES[type] || CATEGORY_STRATEGIES.us;
  const boostKeywords = BOOST_KEYWORDS[type] || [];

  // Serve existing pool unless forced refresh
  if (!forceRefresh && sessionPools.has(poolKey)) {
    return sessionPools.get(poolKey).articles;
  }

  // If already building — wait for the lock (Promise-based, 5s timeout)
  if (poolLocks.has(poolKey)) {
    try {
      await Promise.race([
        poolLocks.get(poolKey),
        new Promise((_, rej) => setTimeout(() => rej(new Error('LOCK_TIMEOUT')), CONFIG.POOL_LOCK_TIMEOUT)),
      ]);
    } catch {
      // Timeout — serve stale pool or fallback
      console.warn(`[POOL] Lock timeout for ${poolKey}, serving fallback`);
    }
    return (sessionPools.get(poolKey) || lastGoodPool.get(type) || { articles: [] }).articles;
  }

  // Acquire lock
  let resolveLock;
  const lockPromise = new Promise(res => { resolveLock = res; });
  poolLocks.set(poolKey, lockPromise);
  console.log(`[POOL] Building pool: ${poolKey}`);

  try {
    const fetchLimit = Math.max(CONFIG.POOL_MAX_SIZE, 40);
    const { articles: raw, totalArticles } = await fetchParallelRanges(strategy, fetchLimit);

    if (raw.length === 0) {
      throw new Error('EMPTY_FETCH');
    }

    // Compute source frequency for diversity scoring
    const sourceFreq = new Map();
    raw.forEach(a => {
      const s = a.source?.name || 'unknown';
      sourceFreq.set(s, (sourceFreq.get(s) || 0) + 1);
    });

    // Score & sort
    const scored = raw
      .map(a => ({ ...a, _score: scoreArticle(a, boostKeywords, sourceFreq) }))
      .sort((a, b) => b._score - a._score)
      .slice(0, CONFIG.POOL_MAX_SIZE);

    // ONE-TIME tiered shuffle
    const pool = tieredShuffle(scored);

    // PERSIST TO DISK
    const db = loadDB();
    const dbMap = new Map(db.map(v => [v._stableId, v]));
    
    pool.forEach(a => {
      // Preserve AI summary if it exists in DB
      if (dbMap.has(a._stableId)) {
        const existing = dbMap.get(a._stableId);
        if (existing.aiSummary) a.aiSummary = existing.aiSummary;
      }
      dbMap.set(a._stableId, a);
    });
    
    saveDB(Array.from(dbMap.values()).sort((a,b) => new Date(b.publishedAt) - new Date(a.publishedAt)));

    const entry = { articles: pool, totalArticles, timestamp: Date.now() };
    sessionPools.set(poolKey, entry);
    lastGoodPool.set(type, entry); // Save as fallback

    console.log(`[POOL] Committed ${pool.length} articles for ${poolKey}`);

    // Enqueue top articles for AI enrichment (background, non-blocking)
    pool.slice(0, 20).forEach((a, i) => enqueueAI(a, 20 - i));

    return pool;

  } catch (err) {
    console.error(`[POOL] Build failed for ${poolKey}:`, err.message);
    // Return last good pool on failure
    const fallback = lastGoodPool.get(type);
    if (fallback) {
      console.warn(`[POOL] Serving cached fallback for ${type}`);
      return fallback.articles;
    }
    return [];
  } finally {
    poolLocks.delete(poolKey);
    resolveLock();
  }
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
// CRON FETCH LOGIC (Mega-Pool Sync)
// ─────────────────────────────────────────────
async function runCronFetch() {
  console.log('[CRON] Starting 15-min MEGA-SYNC (Target: 150 articles per category)...');
  const types = Object.keys(CATEGORY_STRATEGIES);
  
  for (const type of types) {
    try {
      console.log(`[CRON] Harvesting mega-pool for: ${type}`);
      // Run multiple pool builds to saturate the 100-150 article goal
      for (let i = 0; i < 3; i++) {
        await buildOrGetPool(type, true); // Force fresh fetch
        await new Promise(r => setTimeout(r, 4000)); // Stagger to avoid 429
      }
    } catch (err) {
      console.error(`[CRON] Error for ${type}:`, err.message);
    }
  }
  console.log('[CRON] Mega-Sync complete. Local pool is primed.');
}

// Run initial sync after 3 second delay (let server bind first)
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

    // ── Get pool from Local DB (Zero API Latency) ────────────
    let pool = [];
    
    if (forceRefresh) {
      console.log(`[REFRESH] Manual override: Syncing NEW news for ${type}...`);
      // Run sync in background so the user gets instant local results
      runCronFetch();
    }
    
    // 1. Try Session Cache first
    const poolKey = getPoolKey(type);
    if (!forceRefresh && sessionPools.has(poolKey)) {
      pool = sessionPools.get(poolKey).articles;
    } else {
      // 2. Read from local Mega-Pool DB
      const db = loadDB();
      const strat = CATEGORY_STRATEGIES[type] || {};
      
      pool = db.filter(a => {
         if (strat.headlines?.category && a.category === strat.headlines.category) return true;
         if (a.category === type) return true;
         return a._type === type || type === 'us';
      });
      
      // Auto-populate session pool from DB
      if (pool.length > 0) {
        sessionPools.set(poolKey, { articles: pool, totalArticles: pool.length, timestamp: Date.now() });
      } else {
        // Absolute last resort: build if dry
        pool = await buildOrGetPool(type);
      }
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
    const articles = pageSlice.map((item, idx) => {
      const cachedSummary = summaryCache.get(item.url);
      const aiSummary     = cachedSummary ? cachedSummary.text : null;
      const description   = aiSummary || buildFallbackDescription(item);

      return {
        id:          startIdx + idx + 1,
        stableId:    item._stableId,
        title:       item.title,
        description,
        aiSummary,
        hasAiSummary: !!aiSummary,
        image:       item.image?.startsWith('http') ? item.image : null,
        url:         item.url,
        source:      item.source?.name || 'Unknown',
        publishedAt: item.publishedAt,
        score:       parseFloat((item._score || 0).toFixed(3)),
      };
    });

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
  runCronFetch
};
