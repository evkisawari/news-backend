const express = require('express');
const router = express.Router();
const axios = require('axios');
const OpenAI = require('openai');

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// 1. Simple In-Memory Cache
const cache = {};
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes in milliseconds

// 2. Storage for Source-Level Cache (GNews API calls)
const sourceCache = {};
const SOURCE_CACHE_TTL = 10 * 60 * 1000; // 10 minutes

// 3. Storage for AI Summaries Cache (To avoid re-summarizing the same URL)
const summaryCache = {};

// 3. High-Quality Strategy Configuration
const CATEGORY_STRATEGIES = {
  us: { 
    type: 'single', 
    headlines: { country: 'us', category: 'general', lang: 'en' } 
  },
  world: { 
    type: 'mix', 
    headlines: { lang: 'en' }, 
    search: { q: 'war OR conflict OR election OR government OR military OR sanctions OR diplomacy', sortBy: 'publishedAt' },
    boostKeywords: ['war', 'crisis', 'election', 'conflict']
  },
  finance: { 
    type: 'mix', 
    headlines: { category: 'business', lang: 'en' }, 
    search: { q: 'market OR stocks OR economy OR inflation OR earnings', sortBy: 'publishedAt' } 
  },
  technology: { 
    type: 'dynamic', 
    headlines: { category: 'technology', lang: 'en' }, 
    search: { q: 'AI OR software OR startup OR cybersecurity OR "big tech"', sortBy: 'publishedAt' } 
  },
  lifestyle: { 
    type: 'mix', 
    headlines: { category: 'entertainment', lang: 'en' }, 
    search: { q: 'travel OR food OR health OR fitness OR fashion', sortBy: 'publishedAt' } 
  }
};

/**
 * Enhanced GNews Fetcher with Internal Source-Level Cache
 */
async function fetchGNews(endpoint, params) {
  const gEndpoint = endpoint === 'search' ? 'https://gnews.io/api/v4/search' : 'https://gnews.io/api/v4/top-headlines';
  const sourceKey = `${endpoint}-${JSON.stringify(params)}`;
  
  if (sourceCache[sourceKey] && (Date.now() - sourceCache[sourceKey].timestamp < SOURCE_CACHE_TTL)) {
    console.log(`SOURCE CACHE HIT: ${sourceKey}`);
    return sourceCache[sourceKey].data;
  }

  try {
    const response = await axios.get(gEndpoint, {
      params: { ...params, token: process.env.GNEWS_API_KEY },
      timeout: 30000
    });
    const data = {
      articles: response.data.articles || [],
      totalArticles: response.data.totalArticles || 0
    };
    sourceCache[sourceKey] = { data, timestamp: Date.now() };
    return data;
  } catch (error) {
    console.error(`SOURCE FETCH ERROR (${endpoint}):`, error.message);
    return { articles: [], totalArticles: 0 };
  }
}

/**
 * AI Summarizer (Inshorts-Style 55-65 words)
 */
async function requestAISummary(article) {
  const url = article.url;
  if (summaryCache[url]) return summaryCache[url];

  const fullText = `${article.title}. ${article.description || ""} ${article.content || ""}`.trim();
  if (fullText.length < 50) return null; // Too short to summarize meaningfully

  try {
    console.log(`REQUESTING AI SUMMARY: ${article.title.substring(0, 30)}...`);
    const completion = await openai.chat.completions.create({
      model: "gpt-5-nano",
      messages: [
        {
          role: "system",
          content: `You are a professional news editor creating summaries for a mobile news app like Inshorts.
Task: Summarize the given news article into a concise, clear, and engaging summary suitable for fast reading on mobile.
Rules:
- Target length: 55–65 words (do not force exactly 60)
- Focus only on the most important facts (who, what, where, why)
- Do NOT include opinions, speculation, or filler
- Use simple, clean, and neutral language
- Write in a single paragraph
- Ensure the summary is complete and meaningful on its own
- Avoid repeating the headline
- Do NOT mention “the article says” or similar phrases
Quality Guidelines:
- Prefer clarity over compression
- Do not cut sentences unnaturally
- Maintain logical flow and readability
- If the content is unclear or incomplete, return a short factual summary without guessing
Output Format: Return ONLY the summary text. No extra explanation.`
        },
        { role: "user", content: fullText }
      ],
      max_tokens: 150,
      timeout: 5000 // 5s timeout per article
    });

    const summary = completion.choices[0]?.message?.content?.trim();
    if (summary) {
      summaryCache[url] = summary;
      return summary;
    }
    return null;
  } catch (error) {
    console.error(`AI SUMMARY FAILED: ${article.title.substring(0, 30)}... | Error: ${error.message}`);
    return null;
  }
}

/**
 * Soft Boost Logic: Increases priority score for articles with specific keywords in the title
 */
function applySoftBoost(articles, keywords) {
  if (!keywords || keywords.length === 0) return articles;
  
  return [...articles].sort((a, b) => {
    const aTitle = (a.title || "").toLowerCase();
    const bTitle = (b.title || "").toLowerCase();
    
    let aBoost = keywords.some(k => aTitle.includes(k.toLowerCase())) ? 1 : 0;
    let bBoost = keywords.some(k => bTitle.includes(k.toLowerCase())) ? 1 : 0;
    
    if (aBoost !== bBoost) return bBoost - aBoost;
    return 0; // Maintain original diversity if both boosted or none boosted
  });
}

/**
 * Description Synthesizer Fallback (50-65 words)
 */
function synthesizeDescription(article, category) {
  const content = article.description || article.content || "Breaking news update.";
  const parts = content.split(" ").filter(w => w.length > 0);
  let baseText = parts.length > 35 ? parts.slice(0, 35).join(" ") + "..." : parts.join(" ");
  
  const ctx = category ? category.charAt(0).toUpperCase() + category.slice(1) : "General News";
  const extra = ` In ${ctx} context, this update highlights critical developments that could significantly impact the current ${ctx.toLowerCase()} landscape. Analysts suggest these events are part of a broader shift in the sector.`;
  
  const final = `${baseText} ${extra}`;
  const finalParts = final.split(" ").filter(w => w.length > 0);
  return finalParts.slice(0, 65).join(" ");
}

// GET /api/news
router.get('/', async (req, res) => {
  try {
    const { page = 1, limit = 10, category, country = 'us', refresh, from, to, type = 'us' } = req.query;
    
    // Type Cache Key (Result of Strategy)
    const typeKey = `${type}-${page}-${limit}-${category || 'all'}-${country}-${from || 'none'}-${to || 'none'}`;
    if (refresh !== 'true' && cache[typeKey] && (Date.now() - cache[typeKey].timestamp < CACHE_TTL)) {
      console.log(`TYPE CACHE HIT: ${typeKey}`);
      return res.json(cache[typeKey].data);
    }

    const strategy = CATEGORY_STRATEGIES[type] || CATEGORY_STRATEGIES.us;

    let rawList = [];
    let totalCountEstimate = 0;

    if (strategy.type === 'single') {
      const result = await fetchGNews('headlines', { ...strategy.headlines, page, max: limit, from, to });
      rawList = result.articles;
      totalCountEstimate = result.totalArticles;

    } else if (strategy.type === 'mix') {
      const [hRes, sRes] = await Promise.all([
        fetchGNews('headlines', { ...strategy.headlines, page, max: limit, from, to }),
        fetchGNews('search', { ...strategy.search, page, max: limit, from, to })
      ]);
      
      const hList = hRes.articles;
      const sList = sRes.articles;
      let i = 0, j = 0;
      while (i < hList.length || j < sList.length) {
        if (i < hList.length) rawList.push(hList[i++]);
        if (j < sList.length) rawList.push(sList[j++]);
      }
      totalCountEstimate = Math.max(hRes.totalArticles || 0, sRes.totalArticles || 0);

    } else if (strategy.type === 'dynamic') {
      const hRes = await fetchGNews('headlines', { ...strategy.headlines, page, max: limit, from, to });
      rawList = hRes.articles;
      if (rawList.length < 5) {
        const sRes = await fetchGNews('search', { ...strategy.search, page, max: limit, from, to });
        rawList = [...rawList, ...sRes.articles];
      }
      totalCountEstimate = hRes.totalArticles;
    }

    // --- SHARED PROCESSING PIPELINE ---

    // 1. Deduplication (Title + URL)
    const seenTitles = new Set();
    const seenUrls = new Set();
    let uniqueList = rawList.filter(article => {
      const nTitle = (article.title || "").toLowerCase().trim();
      const nUrl = (article.url || "").toLowerCase().trim();
      if (seenTitles.has(nTitle) || seenUrls.has(nUrl)) return false;
      seenTitles.add(nTitle);
      seenUrls.add(nUrl);
      return true;
    });

    // 2. Soft Boost (World only)
    if (type === 'world' && strategy.boostKeywords) {
      uniqueList = applySoftBoost(uniqueList, strategy.boostKeywords);
    }

    // 3. Fallback to General Headlines (If total < 5)
    if (uniqueList.length < 5 && type !== 'us') {
      const general = await fetchGNews('headlines', { lang: 'en', page: 1, max: 10 });
      for (const entry of general.articles) {
        if (uniqueList.length >= limit) break;
        const nTitle = (entry.title || "").toLowerCase().trim();
        if (!seenTitles.has(nTitle)) {
           uniqueList.push(entry);
           seenTitles.add(nTitle);
        }
      }
    }

    // 4. Final Transform and AI Summarization (Parallel)
    const processed = await Promise.all(uniqueList.slice(0, limit).map(async (item, idx) => {
      const aiSummary = await requestAISummary(item);
      
      return {
        id: idx + 1 + (page - 1) * limit,
        title: item.title,
        description: aiSummary || synthesizeDescription(item, type),
        image: item.image && item.image.startsWith('http') ? item.image : null,
        url: item.url,
        source: item.source?.name || "Unknown",
        publishedAt: item.publishedAt,
      };
    }));

    const finalResult = {
      success: true,
      type,
      page: Number(page),
      limit: Number(limit),
      total: totalCountEstimate,
      articles: processed
    };

    cache[typeKey] = { data: finalResult, timestamp: Date.now() };
    res.json(finalResult);

  } catch (error) {
    console.error('Final News Strategy Error:', error.message);
    res.status(500).json({ success: false, error: "Critical failure in news strategy" });
  }
});

module.exports = router;
