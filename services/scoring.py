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
    DEFAULT_CATEGORY_PRIORITY, WAR_KEYWORDS
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
    # ── 1. Recency & Metadata ──────────────────
    title_lower = str(article.get('title', '') or '').lower()
    cat = str(article.get('category', '') or '')
    
    # 1. Freshness (Temporal decay)
    hours_old = _parse_pub_date(str(article.get('publishedAt', '') or ''))
    
    # Massive boost for breaking news (last 4 hours)
    if hours_old < 4:
        recency = 1.0 - (hours_old / 24.0)
        recency *= 2.0 # DOUBLE freshness weight for breaking news
    else:
        recency = max(RECENCY_FLOOR, math.exp(-hours_old / RECENCY_HALF_LIFE))

    # ── Progression Logic (Time vs Interest based on Depth) ──
    # Page 0: strongly favor recent
    # Page 1: mild mix
    # Page 2+: ignore time, purely base on user interest and absolute score
    # If user has >= 10 engagement events, they are a "Power User"
    events = int(user_profile.get('totalEvents', 0)) if user_profile else 0
    is_power_user = events >= 10

    if page_depth == 0:
        weight_recency = 0.40  # Dropped from 0.60 to allow high-interest older news to surface
        weight_interest = 0.35 # Increased from 0.15
    elif page_depth == 1:
        weight_recency = 0.20
        weight_interest = 0.50
    else:
        weight_recency = 0.05
        weight_interest = 0.65  # 65% weight for user interest in deep pages
    
    # Power users get high interest weight even on page 0 (+0.15 shift)
    if is_power_user and page_depth == 0:
        weight_recency -= 0.15
        weight_interest += 0.15

    # ── 2. Source Trust ──────────────────────────
    weight = float(article.get('_weight', 1.0))
    source_score = min(1.0, weight / 1.5)

    # ── 3. User Interest (Dynamic Bias) ──────────
    # Starts at high (0.8) for World/US, low (0.3) for Business/Lifestyle.
    # If user has >= 5 engagement events, the profile's score takes full dominance.
    default_bias = DEFAULT_CATEGORY_PRIORITY.get(cat, 0.5)
    
    interest = default_bias
    if user_profile and user_profile.get('categoryScores'):
        custom = float(user_profile['categoryScores'].get(cat, default_bias))
        
        # Smoothly transition from Default Bias to User Choice over 5 clicks
        alpha = min(1.0, events / 5.0)
        interest = (1.0 - alpha) * default_bias + (alpha * custom)

    # ── 4. User Keyword Interest (Hyper-Personalization) ──
    # Check if article title contains keywords the user has engaged with before
    user_k_score = 0.0
    if user_profile and user_profile.get('keywordScores'):
        u_k_scores = user_profile['keywordScores']
        # Normalize: if a keyword has 5+ hits, it's a "Top Interest"
        for kw, count in u_k_scores.items():
            if kw in title_lower:
                user_k_score += min(1.0, count / 5.0) * 0.20 # Max +0.20 per matching keyword
    
    # Merge custom category interest and specific keyword interest
    final_interest = min(1.0, interest + user_k_score)

    # ── 5. Global Keyword Boost ──────────────────
    keywords = BOOST_KEYWORDS.get(cat, [])
    keyword_score = 1.0 if any(k in title_lower for k in keywords) else 0.0

    # ── 5. Global War Priority Boost ───────────
    # If any article contains war terms, it gets an additional +0.15 boost
    war_boost = 0.0
    if any(k in title_lower for k in WAR_KEYWORDS):
        war_boost = 0.15

    # ── 6. Source Ranking (3-Tier Priority) ─────────────────
    source_type = article.get('source_type', 'rss')
    source_name = str(article.get('source', '') or '').lower()
    
    tier_boost = 0.0
    if source_type in ['newsdata', 'gnews']:
        tier_boost = 0.25 # Tier 1: Primary APIs
    elif any(n in source_name for n in ['dainik bhaskar', 'new york times', 'nyt', 'al jazeera']):
        tier_boost = 0.15 # Tier 2: Premium Trusted Sources
    
    # ── 7. Home Feed Focus (Politics, World, War, Sports) ──
    # If a category is part of the 'Hard News' core, it gets extra visibility on Home.
    # Note: 'Hard News' includes us, world, sports and politics (mapped to us).
    cat_focus_boost = 0.0
    if cat in ['us', 'world', 'business', 'sports']:
        cat_focus_boost = 0.10
    
    score = (
        weight_recency  * recency       +
        SCORE_SOURCE   * source_score  +
        weight_interest * final_interest +
        SCORE_KEYWORD  * keyword_score  +
        war_boost +
        tier_boost +
        cat_focus_boost
    )
    return round(min(1.0, max(0.0, score)), 4)
