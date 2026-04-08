"""
main.py — Priority News Engine v2.0 (Python / FastAPI)

Startup sequence:
  1. Register CORS + routers
  2. Start APScheduler (every 12 min → sync_all_categories)
  3. Kick off initial sync 3s after boot (async task)
"""
import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()  # Load .env before anything else

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from routes.news   import router as news_router
from routes.events import router as events_router


# ── Scheduler ────────────────────────────────
scheduler = AsyncIOScheduler(timezone="UTC")


async def _delayed_sync():
    """Initial sync fires 3 seconds after server boot."""
    await asyncio.sleep(3)
    try:
        from services.fetchers import sync_all_categories
        await sync_all_categories()
    except Exception as e:
        print(f"[BOOT SYNC ERROR] {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from services.fetchers import sync_all_categories
    
    # ── Background Startup Tasks ───────────────────────────
    async def _boot_tasks():
        await asyncio.sleep(2) # Give the server a moment to settle
        try:
            # Initialize PostgreSQL Tables (Step 1: DB Readiness)
            from services.models import init_db
            init_db()
            
            # Deep Cleanup Task: Purge existing clones
            from scripts.cleanup_db import cleanup_duplicates
            cleanup_duplicates()
            print("[BOOT TASKS] DB initialized and cleaned.")
        except Exception as e:
            print(f"[BOOT TASKS ERROR] {e}")

    # Kick off background boot processes so the main loop starts immediately
    asyncio.create_task(_boot_tasks())

    # Schedule repeating cron (every 1 hour)
    scheduler.add_job(
        sync_all_categories,
        trigger='interval',
        hours=1,
        id='news_sync',
        replace_existing=True,
        max_instances=1,          # Never overlap
    )
    scheduler.start()
    print("[SCHEDULER] Cron started — sync every 1 hour.")

    # [REMOVED] Initial sync on boot is removed to conserve API quota on Render free tier.
    # Sync will now only happen once per hour via the scheduler or manual refresh cooldown.

    yield  # ── Server running ──────────────────

    # ── Shutdown ──────────────────────────────
    scheduler.shutdown(wait=False)
    print("[SHUTDOWN] Scheduler stopped.")


# ── App factory ───────────────────────────────
app = FastAPI(
    title="Priority News Engine",
    description="16-step personalized news pipeline: Newsdata.io → GNews → RSS → Scoring → Feed",
    version="2.0-python",
    lifespan=lifespan,
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────
app.include_router(news_router,   prefix="/api/news",  tags=["News Feed"])
app.include_router(events_router, prefix="/api/news", tags=["User Events"])


# ── Base routes ───────────────────────────────
@app.get("/", tags=["Root"])
async def root():
    return {
        "status":  "Backend operational",
        "version": "2.0-python",
        "engine":  "Newsdata.io → GNews → RSS → Score → Feed",
        "endpoints": [
            "GET  /api/news?type=us&limit=20&cursor=...&userId=...&fresh=true",
            "POST /api/news/events  {userId, stableId, event, duration}",
            "GET  /api/health",
            "GET  /docs   (Swagger UI)",
        ],
    }


@app.get("/api/health", tags=["Health"])
async def health():
    return {
        "success": True,
        "message": "Server is awake and responding",
        "version": "2.0-python",
    }


@app.get("/test-db")
def test_db():
    import psycopg2, os
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode="require")
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        result = cur.fetchone()
        cur.close()
        conn.close()
        return {"status": "connected", "result": result}
    except Exception as e:
        return {"error": str(e)}


@app.get("/db-check")
def db_check():
    import psycopg2, os
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode="require")
        cur = conn.cursor()
        # Fallback to news_articles if news doesn't exist to prevent crash during test
        try:
            cur.execute("SELECT COUNT(*) FROM news;")
        except psycopg2.errors.UndefinedTable:
            conn.rollback()
            cur.execute("SELECT COUNT(*) FROM news_articles;")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return {"total_articles": count}
    except Exception as e:
        return {"error": str(e)}


@app.get("/sample")
def sample():
    import psycopg2, os
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode="require")
        cur = conn.cursor()
        try:
            cur.execute("SELECT title FROM news LIMIT 5;")
        except psycopg2.errors.UndefinedTable:
            conn.rollback()
            cur.execute("SELECT title FROM news_articles LIMIT 5;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"data": rows}
    except Exception as e:
        return {"error": str(e)}
