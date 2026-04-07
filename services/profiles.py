"""
services/profiles.py — Anonymous user profile store.

Persists category preference scores and keyword counts to user_profiles.json.
Updates are non-blocking (run_in_executor).
"""
import json
import asyncio
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

PROFILES_PATH = Path(__file__).parent.parent / "user_profiles.json"
_lock = threading.Lock()

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
    def __init__(self):
        self._profiles: Dict[str, Dict] = {}
        self._load()

    # ── Persistence ─────────────────────────────
    def _load(self):
        try:
            if PROFILES_PATH.exists():
                with open(PROFILES_PATH, 'r', encoding='utf-8') as f:
                    self._profiles = json.load(f)
            print(f"[PROFILES] Loaded {len(self._profiles)} user profiles.")
        except Exception as e:
            print(f"[PROFILES] Load error: {e}")
            self._profiles = {}

    def _save(self):
        try:
            with _lock:
                with open(PROFILES_PATH, 'w', encoding='utf-8') as f:
                    json.dump(self._profiles, f, indent=2)
        except Exception as e:
            print(f"[PROFILES] Save error: {e}")

    def _schedule_save(self):
        """Non-blocking background save."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.run_in_executor(None, self._save)
            else:
                self._save()
        except Exception:
            self._save()

    # ── Profile access ──────────────────────────
    def get_profile(self, user_id: str) -> Dict[str, Any]:
        if not user_id:
            return {}
        if user_id not in self._profiles:
            self._profiles[user_id] = {
                'userId':         user_id,
                'categoryScores': {},   # category → float [0.1, 1.0]
                'keywordScores':  {},   # keyword  → int count
                'totalEvents':    0,
                'createdAt':      datetime.utcnow().isoformat(),
                'lastUpdated':    datetime.utcnow().isoformat(),
            }
        return self._profiles[user_id]

    # ── Profile update (Step 15-16: Feedback Loop) ──
    def update_profile(
        self,
        user_id: str,
        category: str,
        event: str,
        keywords: Optional[List[str]] = None,
        duration: int = 0,
    ):
        if not user_id:
            return

        profile = self.get_profile(user_id)
        cat = (category or '').lower().strip()

        # ── Category score adjustment ────────────
        if cat:
            current = float(profile['categoryScores'].get(cat, 0.5))
            base_delta = EVENT_BOOSTS.get(event, 0.0)

            # For 'read', add duration bonus (max +0.12 for 5+ min reads)
            if event == 'read':
                duration_bonus = min(0.12, (duration or 0) / 300.0)
                base_delta += duration_bonus

            new_score = current + base_delta
            profile['categoryScores'][cat] = round(
                max(CAT_SCORE_MIN, min(CAT_SCORE_MAX, new_score)), 4
            )

        # ── Keyword counts ───────────────────────
        for kw in (keywords or []):
            profile['keywordScores'][kw] = profile['keywordScores'].get(kw, 0) + 1

        profile['totalEvents'] = profile.get('totalEvents', 0) + 1
        profile['lastUpdated'] = datetime.utcnow().isoformat()
        self._profiles[user_id] = profile

        # Async-persist
        self._schedule_save()


# Singleton
profile_store = UserProfileStore()
