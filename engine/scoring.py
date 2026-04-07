"""
engine/scoring.py — Personalized scoring engine.

Composite score:
  Recency  (40%) — exponential decay, 12h half-life
  Source   (20%) — trust weight per publisher
  Interest (25%) — user's per-category preference score
  Keyword  (15%) — category-specific trending keyword boost
"""
import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from engine.config import (
    SCORE_RECENCY, SCORE_SOURCE, SCORE_INTEREST, SCORE_KEYWORD,
    RECENCY_HALF_LIFE, RECENCY_FLOOR, BOOST_KEYWORDS,
)


def _parse_pub_date(raw: str) -> float:
    """Return article age in hours. Returns 24.0 on parse failure."""
    try:
        clean = raw.replace('Z', '+00:00').replace(' ', 'T')
        pub = datetime.fromisoformat(clean)
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - pub).total_seconds() / 3600.0
    except Exception:
        return 24.0


def calculate_score(
    article: Dict[str, Any],
    user_profile: Optional[Dict] = None,
) -> float:
    # ── 1. Recency ──────────────────────────────
    age_hours = _parse_pub_date(str(article.get('publishedAt', '') or ''))
    recency = max(RECENCY_FLOOR, math.exp(-age_hours / RECENCY_HALF_LIFE))

    # ── 2. Source Trust ──────────────────────────
    weight = float(article.get('_weight', 1.0))
    source_score = min(1.0, weight / 1.5)

    # ── 3. User Interest ─────────────────────────
    interest = 0.5  # neutral default
    if user_profile and user_profile.get('categoryScores'):
        cat = str(article.get('category', '') or '')
        interest = float(user_profile['categoryScores'].get(cat, 0.5))

    # ── 4. Keyword Boost ─────────────────────────
    cat = str(article.get('category', '') or '')
    keywords = BOOST_KEYWORDS.get(cat, [])
    title_lower = str(article.get('title', '') or '').lower()
    keyword_score = 1.0 if any(k in title_lower for k in keywords) else 0.0

    score = (
        SCORE_RECENCY  * recency       +
        SCORE_SOURCE   * source_score  +
        SCORE_INTEREST * interest      +
        SCORE_KEYWORD  * keyword_score
    )
    return round(min(1.0, max(0.0, score)), 4)
