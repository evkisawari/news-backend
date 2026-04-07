"""
routes/news.py — GET /api/news feed endpoint.

Steps 12-13: Cursor pagination + 15% exploration injection.
"""
import base64
import json
import random
import time
import asyncio
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services.database import load_db
from services.profiles import profile_store
from services.scoring import calculate_score
from services.ai_queue import get_cached_summary, enqueue
from services.config import CATEGORY_ALIASES, FEED_DEFAULT_LIMIT, EXPLORE_RATIO, COOLDOWN_SECONDS

router = APIRouter()

# Per-category refresh cooldowns
_cooldowns: dict = {}


# ── Cursor helpers ────────────────────────────
def encode_cursor(index: int) -> str:
    return base64.b64encode(json.dumps({'idx': index}).encode()).decode()


def decode_cursor(cursor: str) -> int:
    try:
        return int(json.loads(base64.b64decode(cursor).decode()).get('idx', 0))
    except Exception:
        return 0


# ── Feed endpoint ─────────────────────────────
@router.get("")
async def get_news(
    type:   str            = Query('us'),
    limit:  int            = Query(FEED_DEFAULT_LIMIT, ge=1, le=50),
    cursor: Optional[str]  = Query(None),
    userId: Optional[str]  = Query(None),
    fresh:  bool           = Query(False),
):
    # Resolve category alias
    cat = CATEGORY_ALIASES.get(type.lower(), type.lower())
    if cat not in [
        'us', 'world', 'technology', 'business', 'lifestyle', 'science'
    ]:
        cat = 'us'

    # ── Background refresh (with cooldown) ────
    if fresh:
        from services.fetchers import sync_all_categories
        now = time.time()
        last = _cooldowns.get(cat, 0.0)
        if now - last > COOLDOWN_SECONDS:
            _cooldowns[cat] = now
            asyncio.create_task(sync_all_categories())

    # ── Personalisation ───────────────────────
    profile = profile_store.get_profile(userId) if userId else None

    # ── Load + filter by category ─────────────
    db = load_db()
    pool = [a for a in db if a.get('category') == cat]

    if not pool:
        # Nothing stored yet — trigger sync and return empty
        from services.fetchers import sync_all_categories
        asyncio.create_task(sync_all_categories())
        return JSONResponse({
            'success': True, 'type': cat,
            'articles': [], 'total': 0, 'nextCursor': None,
            'meta': {'poolSize': 0, 'personalized': False},
        })

    # ── Re-score with user profile if we have engagement history ──
    if profile and profile.get('totalEvents', 0) > 0:
        pool = [{**a, '_score': calculate_score(a, profile)} for a in pool]
    pool.sort(key=lambda x: x.get('_score', 0), reverse=True)

    # ── Cursor pagination ─────────────────────
    start_idx  = decode_cursor(cursor) if cursor else 0
    main_slice = pool[start_idx: start_idx + limit]
    next_idx   = start_idx + len(main_slice)
    has_more   = next_idx < len(pool)
    next_cursor = encode_cursor(next_idx) if has_more else None

    # ── Exploration injection (Step 13) ──────
    explore_count = max(1, int(limit * EXPLORE_RATIO))
    other = [a for a in db if a.get('category') != cat]
    random.shuffle(other)
    exploration = [{**a, 'isExploration': True} for a in other[:explore_count]]

    # ── Build response ────────────────────────
    combined = main_slice + exploration
    articles = []
    for idx, item in enumerate(combined):
        ai  = get_cached_summary(item.get('url', '')) or item.get('aiSummary')
        desc = ai or (item.get('description') or '')[:400]

        image = item.get('image', '')
        articles.append({
            'id':           start_idx + idx + 1,
            'stableId':     item.get('_stableId', ''),
            'title':        item.get('title', ''),
            'description':  desc,
            'aiSummary':    ai,
            'hasAiSummary': bool(ai),
            'image':        image if str(image).startswith('http') else None,
            'url':          item.get('url', ''),
            'source':       item.get('source', 'Unknown'),
            'category':     item.get('category', cat),
            'publishedAt':  item.get('publishedAt', ''),
            'score':        round(float(item.get('_score', 0)), 4),
            'isExploration': bool(item.get('isExploration', False)),
        })

    # ── Enqueue AI summaries for top articles (non-blocking) ──
    for i, a in enumerate(main_slice[:10]):
        if not a.get('aiSummary') and not get_cached_summary(a.get('url', '')):
            enqueue(a, priority=50 - i)

    return JSONResponse({
        'success':    True,
        'type':       cat,
        'articles':   articles,
        'total':      len(pool),
        'nextCursor': next_cursor,
        'meta': {
            'poolSize':    len(pool),
            'startIdx':    start_idx,
            'personalized': bool(profile and profile.get('totalEvents', 0) > 0),
            'aiQueue':     0,  # placeholder (could expose ai_queue._queue length)
        },
    })
