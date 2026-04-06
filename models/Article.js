const mongoose = require('mongoose');

const articleSchema = new mongoose.Schema({
  stableId: { type: String, required: true, unique: true, index: true },
  title: { type: String, required: true },
  description: { type: String },
  aiSummary: { type: String },
  url: { type: String, required: true },
  image: { type: String },
  source: { type: String },
  category: { type: String, required: true, index: true },
  publishedAt: { type: Date, required: true, index: true },
  score: { type: Number, default: 0 },
  createdAt: { type: Date, default: Date.now, expires: '7d' } // Auto-delete after 7 days
});

module.exports = mongoose.model('Article', articleSchema);
