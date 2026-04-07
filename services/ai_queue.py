"""
services/ai_queue.py — Background OpenAI summary queue.

Uses asyncio tasks to generate 55-65 word summaries for articles
without blocking the feed response. Persists summaries to db.json.
"""
import asyncio
import os
from datetime import datetime
from typing import Dict, Any, Optional

from openai import AsyncOpenAI

from services.config import AI_MAX_CONCURRENT, AI_MAX_QUEUE, SUMMARY_CACHE_TTL
from services.scraper import scrape_article

# ── In-process state ────────────────────────────
_client: Optional[AsyncOpenAI] = None
_summary_cache: Dict[str, Dict] = {}   # url → { text, timestamp }
_in_flight: set = set()
_queue: list = []
_worker_running: bool = False


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


# ── Cache helpers ────────────────────────────────
def get_cached_summary(url: str) -> Optional[str]:
    entry = _summary_cache.get(url)
    if not entry:
        return None
    if (datetime.utcnow().timestamp() - entry['timestamp']) > SUMMARY_CACHE_TTL:
        del _summary_cache[url]
        return None
    return entry['text']


def prune_cache():
    now = datetime.utcnow().timestamp()
    stale = [k for k, v in _summary_cache.items()
             if now - v['timestamp'] > SUMMARY_CACHE_TTL]
    for k in stale:
        del _summary_cache[k]


# ── Queue management ─────────────────────────────
def enqueue(article: Dict[str, Any], priority: int = 0):
    url = article.get('url', '')
    if not url:
        return
    if len(_queue) >= AI_MAX_QUEUE:
        return
    if get_cached_summary(url):
        return
    if url in _in_flight:
        return
    if any(j['url'] == url for j in _queue):
        return

    _queue.append({'article': article, 'url': url, 'priority': priority})
    _queue.sort(key=lambda x: x['priority'], reverse=True)

    # Spawn worker as a task (non-blocking)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_run_worker())
    except RuntimeError:
        pass


async def _run_worker():
    global _worker_running
    if _worker_running:
        return
    _worker_running = True
    try:
        while _queue and len(_in_flight) < AI_MAX_CONCURRENT:
            job = _queue.pop(0)
            asyncio.create_task(_process_job(job))
    finally:
        _worker_running = False


async def _process_job(job: Dict):
    url = job['url']
    article = job['article']

    if get_cached_summary(url):
        return

    _in_flight.add(url)
    try:
        # 1. Attempt to scrape 250 words of real context from the source URL
        scraped_text = await scrape_article(url, max_words=250)
        
        # 2. Generate summary (using scraped text if available, else original snippet)
        summary = await _generate_summary(article, rich_text=scraped_text)
        
        if summary:
            _summary_cache[url] = {
                'text': summary,
                'timestamp': datetime.utcnow().timestamp(),
            }
            # Persist to db.json
            try:
                from services.database import load_db, save_db
                db = load_db()
                updated = False
                for a in db:
                    if a.get('_stableId') == article.get('_stableId'):
                        a['aiSummary'] = summary
                        updated = True
                        break
                if updated:
                    save_db(db, sort=False)
            except Exception as e:
                print(f"[AI] DB persist error: {e}")
    except Exception as e:
        print(f"[AI] Process error for {url[:50]}: {e}")
    finally:
        _in_flight.discard(url)


async def _generate_summary(article: Dict, rich_text: Optional[str] = None) -> Optional[str]:
    # Use scraped text if available, fallback to Title + Description snippet
    if rich_text and len(rich_text) > 100:
        context = f"TITLE: {article.get('title', '')}\nCONTENT: {rich_text}"
        mode = "SUMMARIZE AND REWRITE"
    else:
        context = f"{article.get('title', '')}. {article.get('description', '') or ''}".strip()
        mode = "EXPAND AND REWRITE"

    if len(context) < 50:
        return None

    try:
        response = await _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": (
                    "You are a professional news editor writing final 60-word articles for a mobile news app.\n"
                    f"{mode} the provided information into exactly 55-65 words.\n"
                    "Rules:\n"
                    "- Focus on key facts: who, what, where, why.\n"
                    "- Do NOT repeat the headline directly.\n"
                    "- Do NOT say 'the article says' or 'according to'.\n"
                    "- Write in a highly engaging, professional journalistic tone as if it is the full story. Single paragraph.\n"
                    "- Return ONLY the rewritten text.\n\n"
                    f"Information: {context[:2000]}"
                ),
            }],
            max_tokens=150,
            temperature=0.5,
            timeout=8.0,
        )
        result = (response.choices[0].message.content or '').strip()
        return result if result else None
    except Exception as e:
        print(f"[AI] OpenAI error: {e}")
        return None
