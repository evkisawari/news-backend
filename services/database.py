"""
services/database.py — PostgreSQL article storage & deduplication.
"""
from datetime import datetime, timezone
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
        now = datetime.now(timezone.utc)
        count = 0
        
        for a in articles:
            try:
                # ── Deduplication (Step 5: Fingerprint check) ──
                sid = a.get('_stableId')
                if not sid: continue
                
                existing = db.query(NewsArticle).filter_by(stable_id=sid).first()
                
                if existing:
                    # Update score/summary if changed
                    existing.score = a.get('_score', existing.score)
                    if a.get('aiSummary'):
                        existing.ai_summary = a['aiSummary']
                else:
                    # Insert new
                    new_art = NewsArticle(
                        stable_id      = sid,
                        title          = a.get('title'),
                        description    = a.get('description'),
                        url            = a.get('url'),
                        source         = a.get('source'),
                        category       = a.get('category'),
                        published_at   = _parse_dt(a.get('publishedAt')),
                        image_url      = a.get('image'),
                        score          = a.get('_score', 0.0),
                        ai_summary     = a.get('aiSummary'),
                        is_exploration = a.get('isExploration', False),
                        source_type    = a.get('_sourceType'),
                        weight         = a.get('_weight', 1.0)
                    )
                    db.add(new_art)
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

