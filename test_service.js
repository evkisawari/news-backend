const newsService = require('./services/newsService');
const axios = require('axios');

// Mock axios to test data availability and category merging
if (true) { // Always mock for logic verification
  console.log('Using manual mock for testing logic...');
  axios.get = async (url, config) => {
    const { category, page } = config.params;
    
    // Simulate low results for 'low-category' to test merging
    if (category === 'low-category') {
      return {
        data: {
          articles: [
            {
              title: `Low Result 1`,
              url: `https://test.com/low/1`,
              image: 'https://test.com/image1.jpg',
              source: { name: 'Test Source' },
              publishedAt: new Date().toISOString()
            }
          ],
          totalArticles: 1
        }
      };
    }

    // Default 'general' category for merging
    if (category === 'general') {
       return {
        data: {
          articles: Array.from({ length: 20 }, (_, i) => ({
            title: `General Article ${i}`,
            url: `https://test.com/general/${i}`,
            image: null, // Test image fallback
            source: { name: 'General Source' },
            publishedAt: new Date().toISOString()
          })),
          totalArticles: 100
        }
      };
    }

    return {
      data: {
        articles: [
          {
            title: `Valid Article 1`,
            url: `https://test.com/${category}/1`,
            image: 'https://test.com/image1.jpg',
            source: { name: 'Test Source' },
            publishedAt: new Date().toISOString()
          }
        ],
        totalArticles: 10
      }
    };
  };
}

const test = async () => {
  try {
    console.log('--- Testing Category Merging (low-category -> +general) ---');
    const startMerge = Date.now();
    const res1 = await newsService.fetchNews('low-category', 1);
    const endMerge = Date.now();
    console.log(`Merged articles count: ${res1.articles.length} (expected 15)`);
    console.log(`Time taken: ${endMerge - startMerge}ms`);
    
    const generalCount = res1.articles.filter(a => a.category === 'general').length;
    const lowCount = res1.articles.filter(a => a.category === 'low-category').length;
    console.log(`From low-category: ${lowCount}, From general: ${generalCount}`);

    console.log('\n--- Testing Image Fallback ---');
    const generalArticle = res1.articles.find(a => a.category === 'general');
    console.log(`Fallback Image Used? ${generalArticle.imageUrl.includes('unsplash.com')}`);
    
    console.log('\n--- Testing Exactly 15 Articles ---');
    console.log(`Is count exactly 15? ${res1.articles.length === 15}`);

    process.exit(0);
  } catch (err) {
    console.error('Test failed:', err.stack);
    process.exit(1);
  }
};

test();
