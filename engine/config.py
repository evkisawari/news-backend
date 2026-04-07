"""
engine/config.py — All constants, source definitions, and mappings.
"""

# ──────────────────────────────────────────────
# CATEGORIES
# ──────────────────────────────────────────────
CATEGORIES = ['us', 'world', 'technology', 'business', 'lifestyle', 'science']

CATEGORY_ALIASES = {
    'finance':     'business',
    'general':     'us',
    'sports':      'world',
    'health':      'lifestyle',
    'tech':        'technology',
    'science':     'science',
    'lifestyle':   'lifestyle',
    'us':          'us',
    'world':       'world',
    'technology':  'technology',
    'business':    'business',
}

# ──────────────────────────────────────────────
# SOURCE MAPS
# ──────────────────────────────────────────────
NEWSDATA_CATEGORIES = {
    'us':         {'category': 'top',        'country': 'us'},
    'world':      {'category': 'world',       'country': ''},
    'technology': {'category': 'technology',  'country': ''},
    'business':   {'category': 'business',    'country': ''},
    'lifestyle':  {'category': 'lifestyle',   'country': ''},
    'science':    {'category': 'science',     'country': ''},
}

GNEWS_TOPICS = {
    'us':         'breaking-news',
    'world':      'world',
    'technology': 'technology',
    'business':   'business',
    'lifestyle':  'entertainment',
    'science':    'science',
}

# ──────────────────────────────────────────────
# QUALITY SIGNALS
# ──────────────────────────────────────────────
SOURCE_WEIGHTS: dict = {
    'BBC News':        1.5,
    'Reuters':         1.5,
    'AP':              1.5,
    'Associated Press':1.5,
    'The New York Times': 1.5,
    'NYT':             1.5,
    'Bloomberg':       1.5,
    'Guardian':        1.3,
    'The Guardian':    1.3,
    'CNN':             1.2,
    'Fox News':        1.2,
    'CNBC':            1.4,
    'The Verge':       1.3,
    'TechCrunch':      1.4,
    'Wired':           1.3,
    'Ars Technica':    1.2,
    'NASA':            1.4,
    'Science Daily':   1.3,
    'Business Insider':1.3,
    'Forbes':          1.2,
    'Hacker News':     1.1,
    'New Scientist':   1.2,
}

BOOST_KEYWORDS: dict = {
    'world':      ['war', 'crisis', 'election', 'conflict', 'sanctions', 'diplomacy', 'military', 'ceasefire', 'attack', 'strike'],
    'business':   ['market', 'crash', 'inflation', 'fed', 'recession', 'earnings', 'stocks', 'oil', 'tariff', 'economy'],
    'technology': ['ai', 'hack', 'breach', 'breakthrough', 'regulation', 'ban', 'launch', 'robot', 'openai', 'chatgpt'],
    'lifestyle':  ['health', 'recall', 'breakthrough', 'study', 'diet', 'wellness', 'trend', 'cancer', 'food'],
    'us':         ['president', 'congress', 'supreme court', 'fda', 'shooting', 'trump', 'white house', 'senate', 'election'],
    'science':    ['discovery', 'research', 'study', 'climate', 'space', 'nasa', 'breakthrough', 'mission', 'planet'],
}

# ──────────────────────────────────────────────
# RSS FALLBACK SOURCES
# ──────────────────────────────────────────────
RSS_SOURCES: list = [
    # World
    {'name': 'BBC News',       'url': 'http://feeds.bbci.co.uk/news/rss.xml',                         'category': 'world',      'weight': 1.5},
    {'name': 'AP News',        'url': 'https://apnews.com/apf-topnews?format=xml',                     'category': 'world',      'weight': 1.5},
    {'name': 'The Guardian',   'url': 'https://www.theguardian.com/world/rss',                         'category': 'world',      'weight': 1.3},
    {'name': 'CNN',            'url': 'http://rss.cnn.com/rss/edition.rss',                            'category': 'world',      'weight': 1.2},
    # US
    {'name': 'NYT',            'url': 'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',     'category': 'us',         'weight': 1.5},
    {'name': 'Fox News',       'url': 'https://moxie.foxnews.com/google-publisher/latest.xml',         'category': 'us',         'weight': 1.2},
    {'name': 'Google News US', 'url': 'https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en',        'category': 'us',         'weight': 1.0},
    # Technology
    {'name': 'TechCrunch',     'url': 'https://techcrunch.com/feed/',                                  'category': 'technology', 'weight': 1.4},
    {'name': 'The Verge',      'url': 'https://www.theverge.com/rss/index.xml',                        'category': 'technology', 'weight': 1.3},
    {'name': 'Wired',          'url': 'https://www.wired.com/feed/rss',                                'category': 'technology', 'weight': 1.3},
    {'name': 'Ars Technica',   'url': 'https://feeds.arstechnica.com/arstechnica/index',               'category': 'technology', 'weight': 1.2},
    {'name': 'Hacker News',    'url': 'https://hnrss.org/frontpage',                                   'category': 'technology', 'weight': 1.1},
    # Business
    {'name': 'CNBC',           'url': 'https://www.cnbc.com/id/100003114/device/rss/rss.html',         'category': 'business',   'weight': 1.4},
    {'name': 'Bloomberg',      'url': 'https://feeds.bloomberg.com/markets/news.rss',                  'category': 'business',   'weight': 1.5},
    {'name': 'Business Insider','url': 'https://feeds.businessinsider.com/custom/all',                 'category': 'business',   'weight': 1.3},
    {'name': 'Forbes',         'url': 'https://www.forbes.com/business/feed2/',                        'category': 'business',   'weight': 1.2},
    # Lifestyle
    {'name': 'BBC Lifestyle',  'url': 'http://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml',  'category': 'lifestyle',  'weight': 1.3},
    {'name': 'NYT Style',      'url': 'https://rss.nytimes.com/services/xml/rss/nyt/FashionandStyle.xml', 'category': 'lifestyle', 'weight': 1.2},
    # Science
    {'name': 'NASA',           'url': 'https://www.nasa.gov/rss/dyn/breaking_news.rss',               'category': 'science',    'weight': 1.4},
    {'name': 'Science Daily',  'url': 'https://www.sciencedaily.com/rss/all.xml',                     'category': 'science',    'weight': 1.3},
    {'name': 'New Scientist',  'url': 'https://www.newscientist.com/feed/home/?cmpid=RSS|NSNS',       'category': 'science',    'weight': 1.2},
]

# ──────────────────────────────────────────────
# SCORING WEIGHTS
# ──────────────────────────────────────────────
SCORE_RECENCY  = 0.40
SCORE_SOURCE   = 0.20
SCORE_INTEREST = 0.25
SCORE_KEYWORD  = 0.15

RECENCY_HALF_LIFE = 12   # hours
RECENCY_FLOOR     = 0.10

# ──────────────────────────────────────────────
# ENGINE CONSTANTS
# ──────────────────────────────────────────────
TARGET_PER_CATEGORY  = 30    # Min articles to fetch before skipping fallback
DB_MAX_PER_CATEGORY  = 200   # Max articles stored per category
FEED_DEFAULT_LIMIT   = 20    # Default articles per API request
EXPLORE_RATIO        = 0.15  # 15% exploration injection
ARTICLE_MAX_AGE_HRS  = 48    # Discard articles older than this
COOLDOWN_SECONDS     = 10    # Min seconds between forced refreshes

# AI
AI_MAX_CONCURRENT = 3
AI_MAX_QUEUE      = 50
SUMMARY_CACHE_TTL = 3600  # 1 hour in seconds
