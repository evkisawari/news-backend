const express = require('express');
const router = express.Router();
const axios = require('axios');

/**
 * Intelligent Description Synthesizer
 * Ensures the description is between 50-65 words by combining API fields 
 * and adding contextual, non-topic-changing padding if necessary.
 */
const synthesizeDescription = (item, category) => {
  const title = item.title || "";
  const desc = item.description || "";
  const content = (item.content || "").replace(/\[\+\d+ chars\]/g, ""); // Remove [+1234 chars]

  // Combine unique parts of description and content
  let combined = desc;
  if (content.length > desc.length && content.startsWith(desc.substring(0, 10))) {
    combined = content;
  } else if (!desc.includes(content) && !content.includes(desc)) {
    combined = `${desc} ${content}`.trim();
  }

  let words = combined.split(/\s+/).filter(w => w.length > 0);

  // If already matches the target, return it
  if (words.length >= 50 && words.length <= 65) {
    return words.slice(0, 65).join(" ");
  }

  // If too long, trim it
  if (words.length > 65) {
    return words.slice(0, 65).join(" ") + "...";
  }

  // If too short, add contextual padding without changing the topic/meaning
  const sourceName = item.source?.name || "reputable sources";
  const date = item.publishedAt ? new Date(item.publishedAt).toLocaleDateString() : "recently";
  const topic = category || "this field";

  const paddingSentences = [
    `This report, originally documented by ${sourceName}, provides essential insights into ${topic}.`,
    `As a developing story, viewers are encouraged to monitor ${sourceName} for further updates regarding this matter.`,
    `This news piece, published on ${date}, remains a significant development in the current landscape of ${topic}.`,
    `The full context and detailed analysis of this event are being followed closely by industry experts and ${sourceName}.`,
    `Stay informed by checking the original source URL for the complete breakdown of these events.`
  ];

  let i = 0;
  while (words.length < 50 && i < paddingSentences.length) {
    const padWords = paddingSentences[i].split(" ");
    words = [...words, ...padWords];
    i++;
  }

  // Final trim to ensure we are within 50-65 words exactly
  return words.slice(0, 65).join(" ");
};

// Simple In-Memory Cache
const cache = {};
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes in milliseconds

// GET /api/news
router.get('/', async (req, res) => {
  try {
    const { page = 1, limit = 10, category, country = 'us', refresh, from, to, type = 'us' } = req.query;
    
    // 1. Generate unique cache key (including type)
    const cacheKey = `${type}-${page}-${limit}-${category || 'all'}-${country}-${from || 'none'}-${to || 'none'}`;
    const now = Date.now();

    // 2. Check Cache (unless refresh is forced)
    if (refresh !== 'true' && cache[cacheKey]) {
      const { data, timestamp } = cache[cacheKey];
      if (now - timestamp < CACHE_TTL) {
        console.log(`CACHE HIT: ${cacheKey}`);
        return res.json(data);
      }
      console.log(`CACHE EXPIRED: ${cacheKey}`);
      delete cache[cacheKey];
    }

    const GNEWS_API_KEY = process.env.GNEWS_API_KEY;
    const GNEWS_API_URL_HEADLINES = 'https://gnews.io/api/v4/top-headlines';
    const GNEWS_API_URL_SEARCH = 'https://gnews.io/api/v4/search';

    let rawArticles = [];
    let totalArticlesCount = 0;

    // 3. Fetch Data based on Type
    if (type === 'world') {
      console.log(`FETCHING WORLD FEED: Parallel Requests (Headlines + Global Keywords)`);
      
      const [headlinesRes, searchRes] = await Promise.all([
        axios.get(GNEWS_API_URL_HEADLINES, {
          params: { token: GNEWS_API_KEY, lang: 'en', max: limit, page: page, from, to },
          timeout: 30000
        }),
        axios.get(GNEWS_API_URL_SEARCH, {
          params: { 
            token: GNEWS_API_KEY, 
            q: 'war OR conflict OR election OR government OR military OR sanctions OR diplomacy',
            lang: 'en', 
            max: limit, 
            page: page, 
            sortBy: 'publishedAt',
            from, to 
          },
          timeout: 30000
        })
      ]);

      // Combine and Interleave (approx 50/50 balance)
      const hList = headlinesRes.data.articles || [];
      const sList = searchRes.data.articles || [];
      
      let i = 0, j = 0;
      while (i < hList.length || j < sList.length) {
        if (i < hList.length) rawArticles.push(hList[i++]);
        if (j < sList.length) rawArticles.push(sList[j++]);
      }
      totalArticlesCount = (headlinesRes.data.totalArticles || hList.length) + (searchRes.data.totalArticles || sList.length);

    } else {
      // type=us (Default)
      console.log(`FETCHING US FEED: country=us`);
      const response = await axios.get(GNEWS_API_URL_HEADLINES, {
        params: {
          token: GNEWS_API_KEY,
          lang: 'en',
          country: 'us',
          category: category || 'general',
          max: limit,
          page: page,
          from, to
        },
        timeout: 30000
      });
      rawArticles = response.data.articles || [];
      totalArticlesCount = response.data.totalArticles || rawArticles.length;
    }

    // 4. Handle Empty Response
    if (rawArticles.length === 0) {
      return res.json({ success: true, page: Number(page), limit: Number(limit), total: 0, articles: [] });
    }

    // 5. FIX DATA QUALITY (Strict Deduplication: Title + URL)
    const seenTitles = new Set();
    const seenUrls = new Set();
    
    const uniqueArticles = rawArticles.filter(article => {
      const normalizedTitle = (article.title || "").toLowerCase().trim();
      const normalizedUrl = (article.url || "").toLowerCase().trim();
      
      if (seenTitles.has(normalizedTitle) || seenUrls.has(normalizedUrl)) return false;
      
      seenTitles.add(normalizedTitle);
      seenUrls.add(normalizedUrl);
      return true;
    });

    // 6. Map and Interleave limit
    const processedArticles = uniqueArticles.slice(0, limit).map((item, index) => ({
      id: index + 1 + (page - 1) * limit,
      title: item.title,
      description: synthesizeDescription(item, category || (type === 'world' ? 'Global Events' : 'US News')),
      image: item.image && item.image.startsWith('http') ? item.image : null,
      url: item.url,
      source: item.source?.name || "Unknown",
      publishedAt: item.publishedAt,
    }));

    const finalResponse = {
      success: true,
      type,
      page: Number(page),
      limit: Number(limit),
      total: totalArticlesCount,
      articles: processedArticles,
    };

    // 7. Store in Cache
    cache[cacheKey] = { data: finalResponse, timestamp: now };

    res.json(finalResponse);

  } catch (error) {
    console.error('GNews Fetch Error:', error.message);
    res.status(500).json({
      success: false,
      error: "Failed to fetch news",
    });
  }
});

module.exports = router;
