"""
services/config.py — All constants, source definitions, and mappings.
"""

# ──────────────────────────────────────────────
# CATEGORIES
# ──────────────────────────────────────────────
CATEGORIES = ['us', 'world', 'technology', 'lifestyle', 'science', 'entertainment']

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
    {'name': 'Google News India', 'url': 'https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en',      'category': 'world',      'weight': 1.1},
    {'name': 'Google News Global', 'url': 'https://news.google.com/rss/search?q=USA+world+news&hl=en-US&gl=US&ceid=US:en', 'category': 'world', 'weight': 1.0},
    # US
    {'name': 'NYT',            'url': 'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',     'category': 'us',         'weight': 1.5},
    {'name': 'Fox News',       'url': 'https://moxie.foxnews.com/google-publisher/latest.xml',         'category': 'us',         'weight': 1.2},
    {'name': 'Google News US', 'url': 'https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en',        'category': 'us',         'weight': 1.0},
    {'name': 'Google News Politics', 'url': 'https://news.google.com/rss/search?q=US+politics&hl=en-US&gl=US&ceid=US:en', 'category': 'us', 'weight': 1.1},
    # Technology
    {'name': 'TechCrunch',     'url': 'https://techcrunch.com/feed/',                                  'category': 'technology', 'weight': 1.4},
    {'name': 'The Verge',      'url': 'https://www.theverge.com/rss/index.xml',                        'category': 'technology', 'weight': 1.3},
    {'name': 'Wired',          'url': 'https://www.wired.com/feed/rss',                                'category': 'technology', 'weight': 1.3},
    {'name': 'Google News AI', 'url': 'https://news.google.com/rss/search?q=AI',                       'category': 'technology', 'weight': 1.2},
    {'name': 'Google News Tech', 'url': 'https://news.google.com/rss/search?q=US+technology&hl=en-US&gl=US&ceid=US:en', 'category': 'technology', 'weight': 1.1},
    # Business
    {'name': 'CNBC',           'url': 'https://www.cnbc.com/id/100003114/device/rss/rss.html',         'category': 'business',   'weight': 1.4},
    {'name': 'Google News Biz', 'url': 'https://news.google.com/rss/search?q=business+news&hl=en-US&gl=US&ceid=US:en', 'category': 'business', 'weight': 1.1},
    {'name': 'Google News Finance', 'url': 'https://news.google.com/rss/search?q=finance+stock+market&hl=en-US&gl=US&ceid=US:en', 'category': 'business', 'weight': 1.1},
    # Lifestyle
    {'name': 'BBC Lifestyle',  'url': 'http://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml',  'category': 'lifestyle',  'weight': 1.3},
    {'name': 'NYT Style',      'url': 'https://rss.nytimes.com/services/xml/rss/nyt/FashionandStyle.xml', 'category': 'lifestyle', 'weight': 1.2},
    # Entertainment / Hollywood Elite
    {'name': 'Variety',            'url': 'https://variety.com/feed/',                                                          'category': 'entertainment', 'weight': 1.5},
    {'name': 'Hollywood Reporter', 'url': 'https://www.hollywoodreporter.com/feed/',                                             'category': 'entertainment', 'weight': 1.5},
    {'name': 'Deadline',           'url': 'https://deadline.com/feed/',                                                         'category': 'entertainment', 'weight': 1.5},
    {'name': 'TMZ',                'url': 'https://www.tmz.com/rss.xml',                                                        'category': 'entertainment', 'weight': 1.3},
    {'name': 'People',             'url': 'https://people.com/feed/',                                                           'category': 'entertainment', 'weight': 1.4},
    {'name': 'US Magazine',        'url': 'https://www.usmagazine.com/feed/',                                                   'category': 'entertainment', 'weight': 1.2},
    {'name': 'ET Online',          'url': 'https://www.etonline.com/news/rss',                                                  'category': 'entertainment', 'weight': 1.3},
    {'name': 'E! News',            'url': 'https://www.eonline.com/syndication/feeds/rssfeeds/topstories.xml',                  'category': 'entertainment', 'weight': 1.3},
    {'name': 'CinemaBlend',        'url': 'https://www.cinemablend.com/rss.xml',                                                'category': 'entertainment', 'weight': 1.2},
    {'name': 'Vulture',            'url': 'https://www.vulture.com/rss/index.xml',                                              'category': 'entertainment', 'weight': 1.4},
    {'name': 'IndieWire',          'url': 'https://www.indiewire.com/feed/',                                                    'category': 'entertainment', 'weight': 1.3},
    {'name': 'AV Club',            'url': 'https://www.avclub.com/rss',                                                         'category': 'entertainment', 'weight': 1.2},
    {'name': 'Google News Ent',    'url': 'https://news.google.com/rss/search?q=Entertainment+news&hl=en-US&gl=US&ceid=US:en',    'category': 'entertainment', 'weight': 1.0},
    
    # Science
    {'name': 'NASA',           'url': 'https://www.nasa.gov/rss/dyn/breaking_news.rss',               'category': 'science',    'weight': 1.4},
    {'name': 'Science Daily',  'url': 'https://www.sciencedaily.com/rss/all.xml',                     'category': 'science',    'weight': 1.3},
    {'name': 'New Scientist',  'url': 'https://www.newscientist.com/feed/home/?cmpid=RSS|NSNS',       'category': 'science',    'weight': 1.2},
]

# ──────────────────────────────────────────────
# SCORING DEFAULTS
# ──────────────────────────────────────────────
# If guest or low-engagement user, use these starting points
DEFAULT_CATEGORY_PRIORITY = {
    'world':      0.80,
    'us':         0.80,
    'science':    0.50,
    'technology': 0.50,
    'business':   0.30,
    'lifestyle':  0.30,
}

# Applied regardless of category if title contains these
WAR_KEYWORDS = ['war', 'conflict', 'invasion', 'military', 'frontline', 'strike', 'attack', 'ceasefire', 'border']

SCORE_RECENCY  = 0.40
SCORE_SOURCE   = 0.20
SCORE_INTEREST = 0.25
SCORE_KEYWORD  = 0.15

RECENCY_HALF_LIFE = 48   # hours
RECENCY_FLOOR     = 0.10

# ──────────────────────────────────────────────
# ENGINE CONSTANTS
# ──────────────────────────────────────────────
TARGET_PER_CATEGORY  = 100   # Pulled more per category for massive variety
DB_MAX_PER_CATEGORY  = 1000  # Retention ceiling
FEED_DEFAULT_LIMIT   = 100   # Bigger batches for 1000+ total
EXPLORE_RATIO        = 0.30  # 30% exploration injection (Double!)
ARTICLE_MAX_AGE_HRS  = 120   # retention up to 5 days (User Request: 3-4 days old news)
COOLDOWN_SECONDS     = 3600  # Min seconds between forced refreshes (1 hour)

# AI
AI_MAX_CONCURRENT = 3
AI_MAX_QUEUE      = 50
SUMMARY_CACHE_TTL = 3600  # 1 hour in seconds
