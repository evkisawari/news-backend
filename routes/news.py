"""
routes/news.py — GET /api/news feed endpoint.

Steps 12-13: Cursor pagination + 15% exploration injection.
"""
import base64
import json
import random
import time
from datetime import datetime, timezone
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
    type:   str            = Query('home'),
    limit:  int            = Query(FEED_DEFAULT_LIMIT, ge=1, le=50),
    cursor: Optional[str]  = Query(None),
    userId: Optional[str]  = Query(None),
    fresh:  bool           = Query(False),
    screen: str            = Query('home'), # 'home' or 'explore'
):
    # Resolve category alias
    type_lower = type.lower()
    cat = CATEGORY_ALIASES.get(type_lower, type_lower)
    
    # ── Background refresh (with cooldown) ────
    if fresh:
        from services.fetchers import sync_all_categories
        now = time.time()
        sync_cat = 'us' if cat in ['home', 'all'] else cat
        last = _cooldowns.get(sync_cat, 0.0)
        if now - last > COOLDOWN_SECONDS:
            _cooldowns[sync_cat] = now
            asyncio.create_task(sync_all_categories())

    # ── Personalisation ──────────────
    profile = profile_store.get_profile(userId) if userId else None
    seen_articles = profile.get('seenArticles', []) if profile else []

    # ── Load + filter ─────────────
    try:
        db = load_db()
        # Drip Feed Filter: Hide articles scheduled for the future
        now_iso = datetime.utcnow().isoformat()
        db = [a for a in db if (a.get('visibleAt') or '') <= now_iso]
        
        if cat in ['home', 'all']:
            pool = db
        else:
            pool = [a for a in db if a.get('category') == cat]
    except Exception as e:
        print(f"[API ERROR] Database connectivity issue: {e}")
        return JSONResponse(status_code=500, content={'success': False, 'error': 'Database connectivity issue', 'detail': str(e)})

    if not pool:
        from services.fetchers import sync_all_categories
        asyncio.create_task(sync_all_categories())
        return JSONResponse({
            'success': True, 'type': cat,
            'articles': [], 'total': 0, 'nextCursor': None,
            'meta': {'poolSize': 0, 'personalized': False},
        })

    # ── Filter seen articles ──
    unseen_pool = [a for a in pool if a.get('_stableId') not in seen_articles]
    if len(unseen_pool) < limit:
        unseen_pool = pool # Fallback if empty

    # ── Pagination Offset ──
    start_idx  = 0 if fresh else (decode_cursor(cursor) if cursor else 0)
    page_depth = start_idx // max(1, limit)

    # ── Scoring & Shuffle ──
    noise = (random.random() * 0.05) if (fresh or start_idx == 0) else 0.0
    unseen_pool = [{**a, '_score': calculate_score(a, profile, page_depth) + noise} for a in unseen_pool]
    unseen_pool.sort(key=lambda x: x.get('_score', 0), reverse=True)

    # ── Screen Partitioning ──
    if cat in ['home', 'all']:
        # Home gets the Top 20 tier. Explore skips them.
        start_from = 20 if (screen.lower() == 'explore' and start_idx == 0) else 0
        pool_to_pick = unseen_pool[start_from:]

        # Diversity Picker
        per_cat = {}
        for a in pool_to_pick:
            c = a.get('category', 'unknown')
            if c not in per_cat: per_cat[c] = []
            if len(per_cat[c]) < 5: per_cat[c].append(a)
        
        main_slice = []
        for c_list in per_cat.values(): main_slice.extend(c_list)
        main_slice.sort(key=lambda x: x.get('_score', 0), reverse=True)
        main_slice = main_slice[:limit]
    else:
        # Standard Category
        main_slice = unseen_pool[start_idx : start_idx + limit]
    
    # ── Cursor Update ──
    current_shift = 20 if (screen.lower() == 'explore' and start_idx == 0) else 0
    next_idx   = start_idx + current_shift + len(main_slice)
    has_more   = len(unseen_pool) > next_idx
    next_cursor = encode_cursor(next_idx) if has_more else None

    # ── Exploration Injection ──
    explore_count = max(1, int(limit * EXPLORE_RATIO))
    main_ids = {a.get('_stableId') for a in main_slice if a.get('_stableId')}
    other = [a for a in db if a.get('category') != cat and a.get('_stableId') not in seen_articles and a.get('_stableId') not in main_ids]
    random.shuffle(other)
    exploration = [{**a, 'isExploration': True} for a in other[:explore_count]]

    combined = main_slice + exploration
    
    # ── Async Seen Mark ──
    if userId:
        served_ids = [a.get('_stableId') for a in combined if a.get('_stableId')]
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, profile_store.mark_articles_seen, userId, served_ids)

    # ── Formatting ──
    articles = []
    for idx, item in enumerate(combined):
        ai = get_cached_summary(item.get('url', '')) or item.get('aiSummary')
        desc = ai or (item.get('description') or '')[:400]
        image = item.get('image', '')
        articles.append({
            'id':           start_idx + idx + 1,
            'stableId':     item.get('_stableId', ''),
            'title':        item.get('title', ''),
            'description':  desc,
            'hasAiSummary': bool(ai),
            'image':        image if str(image).startswith('http') else None,
            'url':          item.get('url', ''),
            'source':       item.get('source', 'Unknown'),
            'category':     item.get('category', cat),
            'publishedAt':  item.get('publishedAt', ''),
            'score':        round(float(item.get('_score', 0)), 4),
            'isExploration': bool(item.get('isExploration', False)),
        })

    # Enqueue AI
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
        },
    })


# ── Search endpoint ───────────────────────────
@router.get("/search")
async def search_news(
    q:     str            = Query(..., min_length=1),
    limit: int            = Query(15, ge=1, le=50),
    userId: Optional[str] = Query(None),
):
    """
    Simple keyword search across titles and descriptions.
    Deduplicates by stableId automatically.
    """
    try:
        db = load_db()
        query = q.lower().strip()
        
        # 1. Filter and match
        matches = []
        for a in db:
            title = (a.get('title') or '').lower()
            desc  = (a.get('description') or '').lower()
            if query in title or query in desc:
                matches.append(a)
        
        # 2. Deduplicate by stableId (just in case)
        seen_ids = set()
        unique_matches = []
        for a in matches:
            sid = a.get('_stableId')
            if sid not in seen_ids:
                seen_ids.add(sid)
                unique_matches.append(a)
        
        # 3. Sort by score
        unique_matches.sort(key=lambda x: x.get('_score', 0), reverse=True)
        
        # 4. Format
        results = []
        for a in unique_matches[:limit]:
            results.append({
                'stableId':    a.get('_stableId'),
                'title':       a.get('title'),
                'description': a.get('aiSummary') or a.get('description'),
                'image':       a.get('image'),
                'url':         a.get('url'),
                'source':      a.get('source'),
                'category':    a.get('category'),
                'publishedAt': a.get('publishedAt'),
            })

        return {
            'success':  True,
            'query':    q,
            'articles': results,
            'total':    len(results)
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})
