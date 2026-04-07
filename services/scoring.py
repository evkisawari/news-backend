"""
services/scoring.py — Personalized scoring engine.

Composite score:
  Recency  (40%) — exponential decay, 12h half-life
  Source   (20%) — trust weight per publisher
  Interest (25%) — user's per-category preference score
  Keyword  (15%) — category-specific trending keyword boost
"""
import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from services.config import (
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
    page_depth: int = 0,
) -> float:
    # ── 1. Recency ──────────────────────────────
    age_hours = _parse_pub_date(str(article.get('publishedAt', '') or ''))
    recency = max(RECENCY_FLOOR, math.exp(-age_hours / RECENCY_HALF_LIFE))

    # ── Progression Logic (Time vs Interest based on Depth) ──
    # Page 0: strongly favor recent
    # Page 1: mild mix
    # Page 2+: ignore time, purely base on user interest and absolute score
    weight_recency  = SCORE_RECENCY
    weight_interest = SCORE_INTEREST

    if page_depth == 0:
        weight_recency = 0.60
        weight_interest = 0.10
    elif page_depth == 1:
        weight_recency = 0.25
        weight_interest = 0.35
    else:
        weight_recency = 0.05
        weight_interest = 0.55

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
        weight_recency  * recency       +
        SCORE_SOURCE   * source_score  +
        weight_interest * interest      +
        SCORE_KEYWORD  * keyword_score
    )
    return round(min(1.0, max(0.0, score)), 4)
