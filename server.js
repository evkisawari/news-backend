const express = require('express');
const cors = require('cors');
require('dotenv').config();
const newsRoutes = require('./routes/newsRoutes');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.use('/api', newsRoutes);

// Catch-all route 404
app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: 'Route not found'
  });
});

// Generic Error Handling Middleware
app.use((err, req, res, next) => {
  console.error('Unhandled Error:', err);

  const statusCode = err.status || 500;
  const message = err.message || 'An internal server error occurred';

  res.status(statusCode).json({
    success: false,
    error: message,
    stack: process.env.NODE_ENV === 'development' ? err.stack : undefined
  });
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
  console.log(`API Key set for GNews: ${process.env.GNEWS_API_KEY ? 'Yes' : 'No'}`);
});
