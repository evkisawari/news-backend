const axios = require('axios');

async function verifyImages() {
  const baseUrl = 'http://localhost:5000/api/news';
  
  try {
    console.log('--- Verifying Image Extraction from RSS ---');
    const res = await axios.get(`${baseUrl}?limit=20&refresh=true`);
    
    if (!res.data.success) {
      console.error('API Error:', res.data.error);
      return;
    }

    const articles = res.data.articles;
    console.log(`Fetched ${articles.length} articles.\n`);

    articles.forEach((a, i) => {
      console.log(`[${i + 1}] ${a.source}: ${a.title}`);
      console.log(`    URL: ${a.url.substring(0, 60)}...`);
      console.log(`    Image: ${a.image || 'NONE'}`);
      
      if (a.image) {
        const isTracker = a.image.includes('pixel') || a.image.includes('tracking') || a.image.includes('/1x1');
        if (isTracker) {
          console.log('    ⚠️  WARNING: Potential tracker detected!');
        } else if (a.image.includes('placeholder') || a.image.includes('wikimedia') || a.image.includes('via.placeholder')) {
          console.log('    ℹ️  INFO: Using fallback/brand logo.');
        } else {
          console.log('    ✅ SUCCESS: Valid article image.');
        }
      } else {
        console.log('    ❌ ERROR: No image found.');
      }
      console.log('--------------------------------------------------');
    });

  } catch (error) {
    console.error('Verification failed:', error.message);
    console.log('Ensure the server is running with node server.js');
  }
}

verifyImages();
