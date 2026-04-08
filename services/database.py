"""
services/database.py — PostgreSQL article storage & deduplication.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from services.models import SessionLocal, NewsArticle
from services.config import ARTICLE_MAX_AGE_HRS, DB_MAX_PER_CATEGORY, CATEGORIES


def load_db() -> List[Dict[str, Any]]:
    """Fetch all articles from PostgreSQL (Step 12: Feed generation)."""
    db = SessionLocal()
    try:
        # Fetch all articles directly, maintaining pagination/limit logic elsewhere
        rows = db.query(NewsArticle).order_by(desc(NewsArticle.score)).all()
        return [_to_dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] Load error: {e}")
        return []
    finally:
        db.close()


def save_db(articles: List[Dict[str, Any]], sort: bool = True) -> List[Dict[str, Any]]:
    """Upsert articles into PostgreSQL (Step 9: Sync persistence)."""
    db = SessionLocal()
    try:
        # Pre-fetch existing titles for fuzzy deduplication
        existing_rows = db.query(NewsArticle.title).all()
        existing_titles = [r[0].lower() for r in existing_rows if r[0]]
        import difflib

        # Track counts per category for the Drip Feed
        cat_counts = {c: 0 for c in CATEGORIES}

        for a in articles:
            try:
                sid = a.get('_stableId')
                title = (a.get('title') or '').strip()
                cat = a.get('category', 'world')
                if not sid or not title: continue
                
                # 1. Exact ID check
                existing = db.query(NewsArticle).filter_by(stable_id=sid).first()
                
                if existing:
                    existing.score = a.get('_score', existing.score)
                    if a.get('aiSummary'): existing.ai_summary = a['aiSummary']
                else:
                    # 2. Fuzzy Title check (Catch clones before they enter the DB)
                    t_lower = title.lower()
                    # Only check against the most recent 100 titles to keep it fast
                    if any(difflib.SequenceMatcher(None, t_lower, t).ratio() > 0.85 for t in existing_titles[-100:]):
                        continue # Skip this clone
                    
                    # Drip Feed (Per Category): 5 instantly, then 2 every 10 mins
                    cur_cat_count = cat_counts.get(cat, 0)
                    delay_min = max(0, ((cur_cat_count - 5) // 2) * 10) if cur_cat_count > 5 else 0
                    cat_counts[cat] = cur_cat_count + 1

                    new_art = NewsArticle(
                        stable_id      = sid,
                        title          = title,
                        description    = a.get('description'),
                        url            = a.get('url'),
                        source         = a.get('source'),
                        category       = cat,
                        published_at   = _parse_dt(a.get('publishedAt')),
                        image_url      = a.get('image'),
                        score          = a.get('_score', 0.0),
                        ai_summary     = a.get('aiSummary'),
                        is_exploration = a.get('isExploration', False),
                        source_type    = a.get('_sourceType'),
                        weight         = a.get('_weight', 1.0),
                        visible_at     = datetime.utcnow() + timedelta(minutes=delay_min)
                    )
                    db.add(new_art)
                    existing_titles.append(t_lower)
                    count += 1
            except Exception as e:
                print(f"[DB] Item save error for stable_id {a.get('_stableId')}: {e}")
                db.rollback() # Rollback the individual item failure to keep session clean

        db.commit()
        
        # ── Step 8: Retention (Cleanup) ─────────────────
        # Delete articles older than X hours
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) # naive for compare if db is naive
        # Actually models use utcnow, let's stick to naive comparison or handle both
        # SQLAlchemy handles naive datetimes for Postgres usually
        from datetime import timedelta
        limit_dt = datetime.utcnow() - timedelta(hours=ARTICLE_MAX_AGE_HRS)
        db.query(NewsArticle).filter(NewsArticle.published_at < limit_dt).delete()
        db.commit()

        print(f"[DB] Saved {count} new articles. Total archived updated.")
        # Return all for compatibility feed logic
        return load_db()

    except Exception as e:
        print(f"[DB] Save error: {e}")
        db.rollback()
        return articles
    finally:
        db.close()


def _to_dict(row: NewsArticle) -> Dict[str, Any]:
    """Convert SQLAlchemy row to engine-compatible dictionary."""
    return {
        'title':         row.title,
        'description':   row.description,
        'url':           row.url,
        'source':        row.source,
        'category':      row.category,
        'publishedAt':   row.published_at.isoformat() if row.published_at else '',
        'image':         row.image_url,
        'aiSummary':     row.ai_summary,
        'hasAiSummary':  bool(row.ai_summary),
        '_stableId':     row.stable_id,
        '_score':        row.score,
        'isExploration': row.is_exploration,
        '_sourceType':   row.source_type,
        '_weight':       row.weight,
        'visibleAt':     row.visible_at.isoformat() if row.visible_at else '',
    }


def _parse_dt(raw: Any) -> Optional[datetime]:
    if not raw: return None
    if isinstance(raw, datetime): return raw
    try:
        # Handle '2026-04-07 13:00:00', ISO, or GNews format
        clean = str(raw).replace('Z', '+00:00').replace(' ', 'T')
        # If it's a short date like '2026-04-07', fromisoformat works
        dt = datetime.fromisoformat(clean)
        # Ensure it's naive UTC as per our convention
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception as e:
        # Fallback for GNews style or others
        try:
            from dateutil import parser
            dt = parser.parse(str(raw))
            return dt.replace(tzinfo=None)
        except Exception:
            print(f"[DB] Date parse failed for '{raw}': {e}")
            return None

