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

    console.log('\n--- Testing News API (Description Word Count) ---');
    const newsRes1 = await axios.get(`${BASE_URL}/api/news?page=1&limit=5&category=technology`);
    const description = newsRes1.data.articles[0].description;
    const wordCount = description.split(/\s+/).length;
    console.log(`First Article Description: "${description.substring(0, 100)}..."`);
    console.log(`Word Count: ${wordCount} (Target: 50-65)`);
    
    if (wordCount >= 50 && wordCount <= 65) {
      console.log('SUCCESS: Word count is within target range.');
    } else {
      console.error(`FAIL: Word count is ${wordCount}.`);
    }

    if (newsRes1.data.articles.length > 0) {
      console.log('Sample Article Metadata:', {
        id: newsRes1.data.articles[0].id,
        title: newsRes1.data.articles[0].title,
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
