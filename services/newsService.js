const axios = require('axios');
const cache = require('../utils/cacheProvider');
require('dotenv').config();

const GNEWS_API_BASE_URL = 'https://gnews.io/api/v4/top-headlines';
const API_KEY = process.env.GNEWS_API_KEY;
const DEFAULT_IMAGE_URL = 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=1000&auto=format&fit=crop';

/**
 * Normalize article format from GNews.
 * @param {Object} article 
 * @param {string} category
 * @returns {Object} Normalized article
 */
const normalizeArticle = (article, category) => {
  const imageUrl = article.image || article.urlToImage;
  return {
    title: article.title || 'No Title Available',
    description: article.description || '',
    imageUrl: (imageUrl && imageUrl.startsWith('http')) ? imageUrl : DEFAULT_IMAGE_URL,
    source: article.source ? article.source.name : 'Unknown Source',
    url: article.url,
    publishedAt: article.publishedAt,
    category: category
  };
};

/**
 * Deduplicate articles by URL.
 * @param {Array} articles 
 * @returns {Array} Unique articles
 */
const deduplicateArticles = (articles) => {
  const seenUrls = new Set();
  return articles.filter(article => {
    if (seenUrls.has(article.url)) {
      return false;
    }
    seenUrls.add(article.url);
    return true;
  });
};

/**
 * Fetch news based on category and page.
 * @param {string} category 
 * @param {number} page 
 */
const fetchNews = async (category = 'general', page = 1) => {
  const cacheKey = `news_optimized_${category}_page_${page}`;
  const cachedData = cache.get(cacheKey);

  if (cachedData) {
    return { ...cachedData, fromCache: true };
  }

  try {
    // 1. Fetch primary category results (max=40 for good availability)
    const primaryResponse = await axios.get(GNEWS_API_BASE_URL, {
      params: {
        category: category,
        page: page,
        max: 40,
        apikey: API_KEY,
        lang: 'en'
      },
      timeout: 5000
    });

    const { articles: primaryArticles } = primaryResponse.data;
    
    // 2. Normalize and initial deduplication
    let resultArticles = primaryArticles.map(a => normalizeArticle(a, category));
    resultArticles = deduplicateArticles(resultArticles);

    // 3. Merge Logic: If fewer than 15 articles, supplement from "general"
    if (resultArticles.length < 15 && category !== 'general') {
      console.log(`Insufficient results for ${category} (${resultArticles.length}). Merging with general.`);
      
      const generalResponse = await axios.get(GNEWS_API_BASE_URL, {
        params: {
          category: 'general',
          page: page,
          max: 40,
          apikey: API_KEY,
          lang: 'en'
        },
        timeout: 5000
      });

      const { articles: generalArticles } = generalResponse.data;
      const normalizedGeneral = generalArticles.map(a => normalizeArticle(a, 'general'));

      // Append general articles that don't already exist in resultArticles
      for (const article of normalizedGeneral) {
        if (resultArticles.length >= 15) break;
        if (!resultArticles.find(a => a.url === article.url)) {
          resultArticles.push(article);
        }
      }
    }

    // 4. Ensure exactly 15 articles for consistent infinite scroll
    const finalArticles = resultArticles.slice(0, 15);

    const result = {
      success: true,
      page: parseInt(page),
      articles: finalArticles,
      category: category
    };

    // Cache the result
    cache.set(cacheKey, result);

    return result;

  } catch (error) {
    console.error('GNews API Error:', error.message);

    if (error.response) {
      const { status } = error.response;
      if (status === 401) throw new Error('Invalid GNews API Key.');
      if (status === 403) throw new Error('API Rate limit exceeded.');
      if (status === 429) throw new Error('Too many requests. Please wait.');
    }

    throw new Error('Failed to fetch news. Please try again later.');
  }
};

module.exports = {
  fetchNews
};
