const express = require('express');
const router = express.Router();
const newsService = require('../services/newsService');

/**
 * GET /news
 * Query Parameters: category (optional), page (optional)
 * Optimized for Infinite Scroll
 */
router.get('/news', async (req, res, next) => {
  try {
    const { category, page } = req.query;
    
    // Default to 'general' category and page 1
    const newsCategory = (category || 'general').toLowerCase();
    const newsPage = parseInt(page) || 1;

    // Use newsService to fetch optimized news
    const result = await newsService.fetchNews(newsCategory, newsPage);
    
    // Return standard format for infinite scroll
    res.json({
      success: true,
      page: result.page,
      articles: result.articles
    });

  } catch (error) {
    next(error);
  }
});

module.exports = router;
