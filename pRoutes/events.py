"""
pRoutes/events.py — POST /api/news/events user event tracking.

Steps 14-16: Captures clicks/reads/skips, updates user profile,
feeds the personalization loop.
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from engine.database import load_db
from engine.profiles import profile_store
from engine.config import BOOST_KEYWORDS

router = APIRouter()

VALID_EVENTS = {'click', 'read', 'skip', 'save'}


class EventPayload(BaseModel):
    userId:   str
    stableId: str
    event:    str
    duration: Optional[int] = 0
    category: Optional[str] = None

    @field_validator('event')
    @classmethod
    def validate_event(cls, v: str) -> str:
        if v not in VALID_EVENTS:
            raise ValueError(f"event must be one of {VALID_EVENTS}")
        return v

    @field_validator('userId', 'stableId')
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty")
        return v.strip()


@router.post("/events")
async def track_event(payload: EventPayload):
    # Resolve category + keyword signals from stored article
    category = payload.category
    keywords = []

    try:
        db = load_db()
        article = next(
            (a for a in db if a.get('_stableId') == payload.stableId),
            None
        )
        if article:
            category = category or article.get('category', '')
            cat_keywords = BOOST_KEYWORDS.get(category or '', [])
            title_lower  = (article.get('title', '') or '').lower()
            keywords = [kw for kw in cat_keywords if kw in title_lower]
    except Exception as e:
        print(f"[EVENTS] Article lookup error: {e}")

    # Update profile (non-blocking persist inside)
    profile_store.update_profile(
        user_id=payload.userId,
        category=category or '',
        event=payload.event,
        keywords=keywords,
        duration=payload.duration or 0,
    )

    print(
        f"[EVENT] {payload.userId[:8]}… → "
        f"{payload.event} | cat={category} | dur={payload.duration}s"
    )
    return {'success': True}
