const axios = require('axios');

const PORT = 5000;
const BASE_URL = `http://localhost:${PORT}`;

const test = async () => {
  try {
    console.log('--- Testing Root Route / ---');
    const rootRes = await axios.get(`${BASE_URL}/`);
    console.log('Status:', rootRes.data.status);
    console.log('Endpoints:', rootRes.data.endpoints);

    console.log('\n--- Testing News API /api/news (Page 1) ---');
    const newsRes1 = await axios.get(`${BASE_URL}/api/news?page=1&limit=5`);
    console.log('Count:', newsRes1.data.articles.length);
    console.log('First Title:', newsRes1.data.articles[0].title);

    console.log('\n--- Testing News API /api/news (Page 2) ---');
    const newsRes2 = await axios.get(`${BASE_URL}/api/news?page=2&limit=5`);
    console.log('First Title:', newsRes2.data.articles[0].title);

    console.log('\n--- Testing 404 Handler ---');
    try {
      await axios.get(`${BASE_URL}/unknown`);
    } catch (err) {
      console.log('404 Response:', err.response.data);
    }

    process.exit(0);
  } catch (err) {
    console.error('Test failed. Is the server running?', err.message);
    process.exit(1);
  }
};

test();
