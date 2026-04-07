"""
services/processor.py — Normalize, clean, deduplicate, and quality-filter articles.
"""
import re
import hashlib
from html.parser import HTMLParser
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urlencode, parse_qs

from services.config import SOURCE_WEIGHTS

_GARBAGE_DOMAINS = {
    'guim.co.uk', 'cnn.it', 'bit.ly', 'tinyurl.com',
    'feeds.reuters.com', 't.co', 'ow.ly',
}
_GARBAGE_EXTS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp',
    '.svg', '.mp4', '.mp3', '.pdf', '.xml', '.json',
}
_TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign',
    'utm_term', 'utm_content', 'ref', 'source',
}


# ──────────────────────────────────────────────
# HTML STRIPPER
# ──────────────────────────────────────────────
class _MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.convert_charrefs = True
        self._parts: List[str] = []

    def handle_data(self, d: str):
        self._parts.append(d)

    def get_data(self) -> str:
        return ' '.join(self._parts)


def strip_html(text: str) -> str:
    if not text:
        return ''
    try:
        s = _MLStripper()
        s.feed(str(text))
        result = s.get_data()
    except Exception:
        result = re.sub(r'<[^>]+>', '', str(text))
    # Collapse whitespace
    result = re.sub(r'\s+', ' ', result)
    # Decode common entities manually (in case HTMLParser missed any)
    result = result.replace('&amp;', '&').replace('&quot;', '"').replace('&apos;', "'")
    return result.strip()


# ──────────────────────────────────────────────
# URL UTILITIES
# ──────────────────────────────────────────────
def clean_url(url_str: str) -> Optional[str]:
    if not url_str:
        return None
    try:
        parsed = urlparse(str(url_str).strip())
        domain = parsed.netloc.lower()
        path = parsed.path.lower()

        if not parsed.scheme.startswith('http'):
            return None
        if any(g in domain for g in _GARBAGE_DOMAINS):
            return None
        if any(path.endswith(ext) for ext in _GARBAGE_EXTS):
            return None

        # Strip tracking params
        qs = {k: v for k, v in parse_qs(parsed.query).items()
              if k not in _TRACKING_PARAMS}
        cleaned = parsed._replace(query=urlencode(qs, doseq=True))
        return cleaned.geturl()
    except Exception:
        return None


# ──────────────────────────────────────────────
# LANGUAGE & FINGERPRINT
# ──────────────────────────────────────────────
def is_english(text: str) -> bool:
    if not text:
        return True
    non_ascii = sum(1 for c in str(text) if ord(c) > 127)
    return (non_ascii / max(len(text), 1)) < 0.15


def make_fingerprint(title: str) -> str:
    normalized = re.sub(r'[^a-z0-9]', '', title.lower())[:60]
    return hashlib.md5(normalized.encode()).hexdigest()


# ──────────────────────────────────────────────
# IMAGE VALIDATOR
# ──────────────────────────────────────────────
_BAD_IMAGE_PATTERNS = [
    'pixel', 'tracking', '/1x1', 'blank.', 'spacer.',
    'logo_rss', 'favicon', 'placeholder',
]

def is_valid_image(url: str) -> bool:
    if not url or not str(url).startswith('http'):
        return False
    url_lower = url.lower()
    if any(p in url_lower for p in _BAD_IMAGE_PATTERNS):
        return False
    return True


# ──────────────────────────────────────────────
# NORMALIZE
# ──────────────────────────────────────────────
def normalize_article(raw: Dict[str, Any], source_type: str) -> Optional[Dict[str, Any]]:
    title = str(raw.get('title', '') or '').strip()
    if not title or len(title) < 10 or not is_english(title):
        return None

    url = clean_url(raw.get('url', ''))
    if not url:
        return None

    image = raw.get('image', '') or ''
    if not is_valid_image(image):
        image = None

    description = strip_html(raw.get('description', '') or '')[:480]
    fp = make_fingerprint(title)
    source = str(raw.get('source', 'Unknown'))
    weight = raw.get('_weight', SOURCE_WEIGHTS.get(source, 1.0))

    return {
        'title':       title,
        'description': description,
        'url':         url,
        'source':      source,
        'category':    str(raw.get('category', '')),
        'publishedAt': raw.get('publishedAt', ''),
        'image':       image,
        '_fp':         fp,
        '_stableId':   fp,
        '_weight':     float(weight),
        '_sourceType': source_type,
        '_score':      0.0,
    }


# ──────────────────────────────────────────────
# DEDUPLICATE
# ──────────────────────────────────────────────
def deduplicate(articles: List[Dict]) -> List[Dict]:
    seen: set = set()
    result = []
    for a in articles:
        fp = a.get('_fp')
        if fp and fp not in seen:
            seen.add(fp)
            result.append(a)
    return result


# ──────────────────────────────────────────────
# QUALITY FILTER
# ──────────────────────────────────────────────
def quality_filter(articles: List[Dict]) -> List[Dict]:
    good = []
    for a in articles:
        if not a.get('title') or len(a['title']) < 10:
            continue
        if not a.get('description') or len(a['description']) < 30:
            continue
        if not is_valid_image(a.get('image', '')):
            continue
        if not a.get('url') or not str(a['url']).startswith('http'):
            continue
        good.append(a)
    return good
