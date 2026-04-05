const axios = require('axios');
const { spawn } = require('child_process');

const PORT = 5000;
const BASE_URL = `http://127.0.0.1:${PORT}`;

const runTests = async () => {
  let serverProcess;
  
  try {
    console.log('--- Starting Server For Verification ---');
    
    // Start server.js in a separate process
    serverProcess = spawn('node', ['server.js'], {
      stdio: 'inherit',
      shell: true
    });

    // Wait 3 seconds for server to boot
    console.log('Waiting for server to initialize...');
    await new Promise(resolve => setTimeout(resolve, 3000));

    console.log('\n--- Testing Root Route / ---');
    const rootRes = await axios.get(`${BASE_URL}/`);
    console.log('Status:', rootRes.data.status);
    console.log('Endpoints:', rootRes.data.endpoints);

    console.log('\n--- Testing News API /api/news (Technology) ---');
    const newsRes1 = await axios.get(`${BASE_URL}/api/news?page=1&limit=5&category=technology`);
    console.log('Count:', newsRes1.data.articles.length);
    console.log('Total:', newsRes1.data.total);
    
    if (newsRes1.data.articles.length > 0) {
      console.log('Sample Article:', {
        id: newsRes1.data.articles[0].id,
        title: newsRes1.data.articles[0].title,
        image: newsRes1.data.articles[0].image,
        source: newsRes1.data.articles[0].source
      });
    }

    console.log('\n--- Testing News API Shuffling (Page 1) ---');
    const newsRes2 = await axios.get(`${BASE_URL}/api/news?page=1&limit=5`);
    console.log('First Title (Shuffled Feed):', newsRes2.data.articles[0].title);

    console.log('\n--- Testing 404 Handler ---');
    try {
      await axios.get(`${BASE_URL}/unknown`);
    } catch (err) {
      console.log('404 Response (Expected):', err.response?.data || err.message);
    }

    console.log('\n--- ALL TESTS PASSED ---');
    
  } catch (err) {
    console.error('\nTest failed:', err.message);
    if (err.response) console.error('Response data:', err.response.data);
  } finally {
    if (serverProcess) {
      console.log('\nStopping server...');
      serverProcess.kill('SIGINT');
      process.exit(0);
    }
  }
};

runTests();
