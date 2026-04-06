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
    const { page = 1, limit = 10, category, country = 'us', refresh, from, to } = req.query;
    
    // 1. Generate unique cache key (including date range)
    const cacheKey = `${page}-${limit}-${category || 'all'}-${country}-${from || 'none'}-${to || 'none'}`;
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
    const GNEWS_API_URL = 'https://gnews.io/api/v4/top-headlines';

    // 3. Fetch from GNews API
    console.log(`FETCHING FRESH DATA: ${cacheKey}`);
    const response = await axios.get(GNEWS_API_URL, {
      params: {
        token: GNEWS_API_KEY,
        lang: 'en',
        max: limit,
        page: page,
        topic: category, // only if provided
        country: country,
        from: from, // ISO 8601
        to: to      // ISO 8601
      },
      timeout: 30000 // Increased for reliability during cold starts
    });

    // 4. Handle Empty API Response
    if (!response.data.articles || response.data.articles.length === 0) {
      const emptyResult = {
        success: true,
        page: Number(page),
        limit: Number(limit),
        total: 0,
        articles: [],
      };
      return res.json(emptyResult);
    }

    // 5. FIX DATA QUALITY
    const seenTitles = new Set();
    const uniqueArticles = response.data.articles.filter(article => {
      if (seenTitles.has(article.title)) return false;
      seenTitles.add(article.title);
      return true;
    });

    const shuffled = uniqueArticles.sort(() => Math.random() - 0.5);

    // 6. Map Clean Response with 50-65 word synthesis
    const articles = shuffled.map((item, index) => ({
      id: index + 1 + (page - 1) * limit,
      title: item.title,
      description: synthesizeDescription(item, category),
      
      image: item.image && item.image.startsWith('http')
        ? item.image 
        : null,

      url: item.url,
      source: item.source?.name || "Unknown",
      publishedAt: item.publishedAt,
    }));

    // 7. Final Response Format
    const finalResponse = {
      success: true,
      page: Number(page),
      limit: Number(limit),
      total: response.data.totalArticles || articles.length,
      articles,
    };

    // 8. Store in Cache
    cache[cacheKey] = {
      data: finalResponse,
      timestamp: now
    };

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
