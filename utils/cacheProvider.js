const NodeCache = require('node-cache');
const cache = new NodeCache({ stdTTL: 900 }); // 15 min default TTL

/**
 * Generic cache provider interface to allow easy migration to Redis.
 */
const cacheProvider = {
  get: (key) => {
    return cache.get(key);
  },
  set: (key, value, ttl = 900) => {
    return cache.set(key, value, ttl);
  },
  del: (key) => {
    return cache.del(key);
  },
  flush: () => {
    return cache.flushAll();
  }
};

module.exports = cacheProvider;
