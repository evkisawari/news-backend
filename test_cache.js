const axios = require('axios');

async function testBackend() {
  const baseUrl = 'http://localhost:5000/api'; // Assuming default port
  
  try {
    console.log('--- Testing /health endpoint ---');
    const health = await axios.get(`${baseUrl}/health`);
    console.log('Health Response:', health.data);

    console.log('\n--- Testing Cache (First request) ---');
    const start1 = Date.now();
    const res1 = await axios.get(`${baseUrl}/news?page=1&limit=5`);
    const end1 = Date.now();
    console.log(`First request took: ${end1 - start1}ms`);

    console.log('\n--- Testing Cache (Second request - SAME KEY) ---');
    const start2 = Date.now();
    const res2 = await axios.get(`${baseUrl}/news?page=1&limit=5`);
    const end2 = Date.now();
    console.log(`Second request took: ${end2 - start2}ms (Should be fast)`);

    console.log('\n--- Testing Cache (Different Key - page=2) ---');
    const start3 = Date.now();
    const res3 = await axios.get(`${baseUrl}/news?page=2&limit=5`);
    const end3 = Date.now();
    console.log(`Different key request took: ${end3 - start3}ms (Should be slow)`);

    console.log('\n--- Testing Force Refresh ---');
    const start4 = Date.now();
    const res4 = await axios.get(`${baseUrl}/news?page=1&limit=5&refresh=true`);
    const end4 = Date.now();
    console.log(`Force refresh request took: ${end4 - start4}ms (Should be slow)`);

  } catch (error) {
    console.error('Test failed:', error.message);
    console.log('Make sure the backend is running at http://localhost:5000');
  }
}

testBackend();
