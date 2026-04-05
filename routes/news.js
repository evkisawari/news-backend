const express = require('express');
const router = express.Router();

// GET /api/news
router.get('/', (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = parseInt(req.query.limit) || 10;

  // Generate 50 mock news articles
  const allNews = Array.from({ length: 50 }, (_, i) => ({
    id: i + 1,
    title: `News ${i + 1}`,
    description: `Description for news ${i + 1}`
  }));

  const start = (page - 1) * limit;
  const end = start + limit;

  const paginatedNews = allNews.slice(start, end);

  res.json({
    success: true,
    page,
    limit,
    total: allNews.length,
    articles: paginatedNews
  });
});

module.exports = router;
