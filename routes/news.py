"""
routes/news.py — GET /api/news feed endpoint.

Steps 12-13: Cursor pagination + 15% exploration injection.
"""
import base64
import json
import random
import time
from datetime import datetime, timezone, timedelta
import difflib
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
    category: str            = Query('all'),
    limit:  int            = Query(FEED_DEFAULT_LIMIT, ge=1, le=120),
    cursor: Optional[str]  = Query(None),
    userId: Optional[str]  = Query(None),
    fresh:  bool           = Query(False),
    screen: str            = Query('home'), # 'home' or 'explore'
):
    # Resolve category alias
    cat_lower = category.lower()
    cat = CATEGORY_ALIASES.get(cat_lower, cat_lower)
    
    # [REMOVED] Sync is now strictly decoupled from web requests.
    # Flutter Pull-to-Refresh only fetches from our local DB.
    # Global sync only happens via the hourly scheduler in app.py.

    start_time = time.time()
    
    # ── Personalisation ──────────────
    profile = profile_store.get_profile(userId) if userId else None
    seen_articles = profile.get('seenArticles', []) if profile else []

    # ── Load + Filter (DATABASE LEVEL) ──
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        raw_db = load_db(category=cat, now_iso=now_iso) 
        total_in_db = len(raw_db)
        
        # We now have exactly what we need for this category/time
        db = raw_db
        drip_filtered = 0 # Handled by SQL now
        if screen.lower() == 'explore':
            # 1. Recency: Mix 7 days of news for variety in Explore
            explore_window = now_dt.replace(tzinfo=None) - timedelta(days=7)
            
            def _get_dt(a):
                try: 
                    # Handle Z and ISO formats
                    dt_str = (a.get('publishedAt') or '').replace('Z', '+00:00')
                    return datetime.fromisoformat(dt_str).replace(tzinfo=None)
                except: 
                    return datetime.min
            
            # 2. Filter pool based on window
            db = [a for a in db if _get_dt(a) >= explore_window]
        
        if cat in ['home', 'all']:
            pool = db
        else:
            pool = [a for a in db if str(a.get('category', '')).lower() == cat.lower()]
            
        # 3. Explore Highlight Filter: Filter the final pool if on Explore
        if screen.lower() == 'explore' and len(pool) > 50:
             # We still want enough to fill the page, but let's sort and take the top half 
             # wait, let the scoring handle the order, but we can pre-filter trash.
             pass
    except Exception as e:
        print(f"[API ERROR] Database connectivity issue: {e}")
        return JSONResponse(status_code=500, content={'success': False, 'error': 'Database connectivity issue', 'detail': str(e)})

    if not pool:
        return JSONResponse({
            'success': True, 'type': cat,
            'articles': [], 'total': 0, 'nextCursor': None,
            'meta': {'poolSize': 0, 'personalized': False},
        })

    # ── Filter seen articles (Strict Mode) ──
    unseen_pool = [a for a in pool if a.get('_stableId') not in seen_articles]
    seen_filtered = len(pool) - len(unseen_pool)
    # No fallback! If user is caught up, they stay caught up until the next "Drip" or "Sync".

    # ── Pagination Offset ──
    start_idx  = 0 if fresh else (decode_cursor(cursor) if cursor else 0)
    page_depth = start_idx // max(1, limit)

    # ── Scoring & Shuffle ──
    noise = (random.random() * 0.05) if (fresh or start_idx == 0) else 0.0
    unseen_pool = [{**a, '_score': calculate_score(a, profile, page_depth) + noise} for a in unseen_pool]
    unseen_pool.sort(key=lambda x: x.get('_score', 0), reverse=True)

    # ── Fast Deduplication ──
    safe_pool = []
    seen_ids = set()
    for a in unseen_pool:
        sid = a.get('_stableId') or a.get('url')
        if sid not in seen_ids:
            seen_ids.add(sid)
            safe_pool.append(a)
    unseen_pool = safe_pool

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
    
    # [LOGIC REMOVED]: We no longer mark articles as seen automatically.
    # Articles stay in the "unseen_pool" until the user actually opens them.

    # ── Formatting ──
    articles = []
    for idx, item in enumerate(combined):
        ai = get_cached_summary(item.get('url', '')) or item.get('aiSummary')
        title = (item.get('title') or '').strip()
        raw_desc = (item.get('description') or '').strip()
        
        # Redundancy Filter: If no AI summary, check if description is just the title
        desc = ai
        if not ai:
            # Clean up the raw description (strip HTML and whitespace)
            clean_raw = raw_desc.replace('\n', ' ').strip()
            # If the description is just the title, or is too short to be useful, we hide it for a cleaner UI
            if clean_raw == title or len(clean_raw.split()) < 5:
                desc = None
            else:
                desc = clean_raw[:400]

        image = item.get('image', '')
        articles.append({
            'id':           start_idx + idx + 1,
            'stableId':     item.get('_stableId', ''),
            'title':        title,
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

    # Enqueue AI (Step 14: Parallel summarization)
    for i, a in enumerate(main_slice[:12]):
        if not a.get('aiSummary') and not get_cached_summary(a.get('url', '')):
            # CRITICAL: If description is redundant or missing, give it MAX priority
            # to hide the raw title from the user as fast as possible.
            has_desc = bool((a.get('description') or '').strip())
            is_redundant = (a.get('description') or '').strip() == (a.get('title') or '').strip()
            
            prio = 100 if (not has_desc or is_redundant) else (50 - i)
            enqueue(a, priority=prio)

    # ── Step 15: PRO LOGGING & AUDIT ──
    duration = time.time() - start_time
    print(f"\n[AUDIT] 📱 FEED REQUEST")
    print(f"       User:     {userId or 'Guest'}")
    print(f"       Screen:   {screen}")
    print(f"       Category: {cat}")
    print(f"       📊 Stats:  TotalDB: {total_in_db} | DripFiltered: {drip_filtered} | SeenFiltered: {seen_filtered} | Final: {len(articles)}")
    print(f"       ⏱️ Time:   {duration:.3f}s\n")

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
