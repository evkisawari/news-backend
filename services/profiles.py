"""
services/profiles.py — PostgreSQL user profile store.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional

from services.models import SessionLocal, UserProfile

# ── Score clamp bounds ──────────────────────────
CAT_SCORE_MIN = 0.10
CAT_SCORE_MAX = 1.00

EVENT_BOOSTS = {
    'save':  0.10,
    'read':  0.07,   # base; duration adds more (up to 0.12 extra)
    'click': 0.05,
    'skip': -0.03,
}


class UserProfileStore:
    """Manages user preference persistence (Step 15: Feedback loop)."""
    
    def get_profile(self, user_id: str) -> Dict[str, Any]:
        """Fetch profile from SQL (Step 12: Weighted scoring)."""
        if not user_id: return {}
        
        db = SessionLocal()
        try:
            row = db.query(UserProfile).filter_by(user_id=user_id).first()
            if not row:
                # Create default
                row = UserProfile(
                    user_id=user_id,
                    category_scores={},
                    keyword_scores={},
                    seen_articles=[],
                    total_events=0
                )
                db.add(row)
                db.commit()
                db.refresh(row)
            
            return {
                'userId':         row.user_id,
                'categoryScores': row.category_scores or {},
                'keywordScores':  row.keyword_scores or {},
                'seenArticles':   row.seen_articles or [],
                'totalEvents':    row.total_events,
                'createdAt':      row.created_at.isoformat() if row.created_at else '',
                'lastUpdated':    row.last_updated.isoformat() if row.last_updated else '',
            }
        except Exception as e:
            print(f"[PROFILES] Fetch error: {e}")
            return {}
        finally:
            db.close()

    def update_profile(
        self,
        user_id: str,
        category: str,
        event: str,
        keywords: Optional[List[str]] = None,
        duration: int = 0,
    ):
        """Update scores in SQL (Step 16: Non-blocking feedback)."""
        if not user_id: return
        
        db = SessionLocal()
        try:
            row = db.query(UserProfile).filter_by(user_id=user_id).first()
            if not row:
                row = UserProfile(user_id=user_id, category_scores={}, keyword_scores={})
                db.add(row)

            cat = (category or '').lower().strip()
            
            # ── 1. Category Score ──────────────────
            if cat:
                scores = dict(row.category_scores or {})
                current = float(scores.get(cat, 0.5))
                base_delta = EVENT_BOOSTS.get(event, 0.0)

                if event == 'read':
                    duration_bonus = min(0.12, (duration or 0) / 300.0)
                    base_delta += duration_bonus

                new_score = round(max(CAT_SCORE_MIN, min(CAT_SCORE_MAX, current + base_delta)), 4)
                scores[cat] = new_score
                row.category_scores = scores

            # ── 2. Keyword Counts ──────────────────
            if keywords:
                k_scores = dict(row.keyword_scores or {})
                for kw in keywords:
                    k_scores[kw] = k_scores.get(kw, 0) + 1
                row.keyword_scores = k_scores

            row.total_events = (row.total_events or 0) + 1
            row.last_updated = datetime.utcnow()
            
            db.commit()
        except Exception as e:
            print(f"[PROFILES] Update error: {e}")
        finally:
            db.close()

    def mark_articles_seen(self, user_id: str, stable_ids: List[str], reset: bool = False):
        """Append articles to user's seen list, or reset it. (Step 15b: Stateful progress)."""
        if not user_id or (not stable_ids and not reset): return

        db = SessionLocal()
        try:
            row = db.query(UserProfile).filter_by(user_id=user_id).first()
            if not row:
                row = UserProfile(user_id=user_id, category_scores={}, keyword_scores={}, seen_articles=[])
                db.add(row)
            
            if reset:
                row.seen_articles = []
            else:
                existing = row.seen_articles or []
                # append without duplicates, limit to latest 3000 to save space
                new_seen = list(set(existing + stable_ids))
                row.seen_articles = new_seen[-3000:]
            
            db.commit()
        except Exception as e:
            print(f"[PROFILES] Seen tracking error: {e}")
            db.rollback()
        finally:
            db.close()

# Singleton
profile_store = UserProfileStore()

