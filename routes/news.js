const express = require('express');
const router = express.Router();

// GET /api/news
router.get('/', (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = parseInt(req.query.limit) || 10;

  // Generate 100 mock news articles with enriched fields
  const allNews = Array.from({ length: 100 }, (_, i) => ({
    id: i + 1,
    title: `News title ${i + 1}`,
    description: `Short description for news ${i + 1}`,
    image: `https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=1000&auto=format&fit=crop&sig=${i}`,
    url: `https://example.com/article/${i + 1}`,
    source: i % 2 === 0 ? "BBC News" : "CNN",
    publishedAt: "2026-01-01T00:00:00Z"
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
