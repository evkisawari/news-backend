"""
engine/database.py — Thread-safe JSON article store.
"""
import json
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

DB_PATH = Path(__file__).parent.parent / "db.json"
_lock = threading.Lock()


def load_db() -> List[Dict[str, Any]]:
    try:
        if not DB_PATH.exists():
            return []
        with _lock:
            with open(DB_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[DB] Load error: {e}")
        return []


def save_db(articles: List[Dict[str, Any]], sort: bool = True) -> List[Dict[str, Any]]:
    try:
        from engine.config import ARTICLE_MAX_AGE_HRS, DB_MAX_PER_CATEGORY, CATEGORIES

        now = datetime.now(timezone.utc)
        fresh = []
        for a in articles:
            try:
                raw = str(a.get('publishedAt', '') or '').replace('Z', '+00:00').replace(' ', 'T')
                pub = datetime.fromisoformat(raw)
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if (now - pub).total_seconds() / 3600 < ARTICLE_MAX_AGE_HRS:
                    fresh.append(a)
            except Exception:
                fresh.append(a)  # Keep if date can't be parsed

        if sort:
            fresh.sort(key=lambda x: x.get('_score', 0), reverse=True)

        # Cap: top N total (spread across categories)
        max_total = DB_MAX_PER_CATEGORY * len(CATEGORIES)
        final = fresh[:max_total]

        with _lock:
            with open(DB_PATH, 'w', encoding='utf-8') as f:
                json.dump(final, f, indent=2, ensure_ascii=False)

        print(f"[DB] Saved {len(final)} articles.")
        return final

    except Exception as e:
        print(f"[DB] Save error: {e}")
        return articles
