import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Core Routes (Must be at top for stability)
from routes.news   import router as news_router
from routes.events import router as events_router

# ── Global Engine ───────────────────────────────
scheduler = AsyncIOScheduler(timezone="UTC")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background boot to prevent timeout
    async def _boot_engine():
        await asyncio.sleep(2) 
        try:
            from services.models import init_db
            try:
                init_db()
            except Exception as db_err:
                print(f"[BOOT WARNING] DB Error: {db_err}")
                
            print("[SERVER] News engine active.")
        except Exception as e:
            print(f"[CRITICAL BOOT ERROR] {e}")

    asyncio.create_task(_boot_engine())
    yield

# ── App Definition ─────────────────────────────
app = FastAPI(title="Priority News Engine", version="2.0-python", lifespan=lifespan)

# ── Status Endpoint ─────────────────────────────
@app.get("/api/status")
async def get_status():
    from services.database import get_db_session
    from services.models import NewsArticle
    from sqlalchemy import func
    
    db = next(get_db_session())
    total = db.query(func.count(NewsArticle.id)).scalar()
    last = db.query(NewsArticle).order_by(NewsArticle.created_at.desc()).first()
    
    return {
        "status": "online",
        "total_articles_in_db": total,
        "last_sync_attempt": last.created_at.isoformat() if last else "never",
        "engine_interval": "60 minutes"
    }

# ── Global Scheduler (Top Level) ────────────────
from services.fetchers import sync_all_categories
scheduler.add_job(sync_all_categories, 'interval', minutes=60, id='news_sync')
scheduler.start()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registering routes immediately for Render health check stability
app.include_router(news_router,   prefix="/api/news", tags=["News Feed"])
app.include_router(events_router, prefix="/api/news", tags=["User Events"])

@app.get("/")
async def root():
    return {"status": "Backend Live", "version": "2.0-python"}

@app.get("/api/health")
async def health():
    return {"success": True}

@app.get("/api/unlock-news")
def unlock_all():
    from services.models import SessionLocal, NewsArticle
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        count = db.query(NewsArticle).update({"visible_at": now})
        db.commit()
        return {"success": True, "unlocked": count}
    finally:
        db.close()

@app.get("/api/force-sync")
async def force_sync():
    from services.fetchers import sync_all_categories
    try:
        await sync_all_categories()
        return {"success": True, "message": "Global sync complete! Now use /api/unlock-news to see them."}
    except Exception as e:
        return {"success": False, "error": str(e)}
