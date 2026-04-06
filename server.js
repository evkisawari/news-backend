require('dotenv').config();
const express = require('express');
const cors = require('cors');
const cron = require('node-cron');
const { router: newsRoutes, runCronFetch } = require('./routes/news.js');

const app = express();
const PORT = process.env.PORT || 5000;

// Enable CORS
app.use(cors());
app.use(express.json());

// CRON Job: Every 10 minutes (RSS harvesting)
cron.schedule('*/10 * * * *', () => {
  console.log('[CRON] Starting 10-minute RSS sync...');
  runCronFetch();
});

// Root Route
app.get('/', (req, res) => {
  res.json({
    status: "Backend working",
    endpoints: ["/api/news?page=1&limit=10", "/api/health"]
  });
});

// Health Check (Warmup) Endpoint
app.get('/api/health', (req, res) => {
  res.status(200).json({ success: true, message: "Server is awake" });
});

// Use News Router
app.use('/api/news', newsRoutes);

// Global 404 Handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: "Route not found"
  });
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
