const express = require('express');
const router = express.Router();
const axios = require('axios');

// GET /api/news
router.get('/', async (req, res) => {
  try {
    const { page = 1, limit = 10, category } = req.query;
    
    const GNEWS_API_KEY = process.env.GNEWS_API_KEY;
    const GNEWS_API_URL = 'https://gnews.io/api/v4/top-headlines';

    // 4. Fetch from GNews API
    const response = await axios.get(GNEWS_API_URL, {
      params: {
        token: GNEWS_API_KEY,
        lang: 'en',
        max: limit,
        page: page,
        topic: category // only if provided
      },
      timeout: 10000 // Add timeout: 10000
    });

    // 7. Handle Empty API Response
    if (!response.data.articles || response.data.articles.length === 0) {
      return res.json({
        success: true,
        page: Number(page),
        limit: Number(limit),
        total: 0,
        articles: [],
      });
    }

    // 5. FIX DATA QUALITY (IMPORTANT)
    // A. Remove duplicate articles (by title)
    const seenTitles = new Set();
    const uniqueArticles = response.data.articles.filter(article => {
      if (seenTitles.has(article.title)) return false;
      seenTitles.add(article.title);
      return true;
    });

    // B. Shuffle results (avoid repetitive feed)
    const shuffled = uniqueArticles.sort(() => Math.random() - 0.5);

    // 6. Map Clean Response (CRITICAL)
    const articles = shuffled.map((item, index) => ({
      id: index + 1 + (page - 1) * limit,
      title: item.title,
      description: item.description || "No description available",
      
      image: item.image && item.image.startsWith('http')
        ? item.image 
        : null,

      url: item.url,
      source: item.source?.name || "Unknown",
      publishedAt: item.publishedAt,
    }));

    // 8. Final Response Format
    res.json({
      success: true,
      page: Number(page),
      limit: Number(limit),
      total: response.data.totalArticles || articles.length,
      articles,
    });

  } catch (error) {
    // 9. Error Handling
    console.error('GNews Fetch Error:', error.message);
    res.status(500).json({
      success: false,
      error: "Failed to fetch news",
    });
  }
});

module.exports = router;
