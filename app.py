import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ── Global Engine ───────────────────────────────
scheduler = AsyncIOScheduler(timezone="UTC")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bypass Render 502 errors by booting a shell instantly."""
    async def _total_boot():
        await asyncio.sleep(5) 
        try:
            # Step 1: Initialize DB architecture
            from services.models import init_db
            init_db()
            
            # Step 2: Clean up database
            from scripts.cleanup_db import cleanup_duplicates
            cleanup_duplicates()

            # Step 3: Deferred Route Registration
            from routes.news   import router as news_router
            from routes.events import router as events_router
            app.include_router(news_router,   prefix="/api/news", tags=["News Feed"])
            app.include_router(events_router, prefix="/api/news", tags=["User Events"])

            # Step 4: Start Background Sync
            from services.fetchers import sync_all_categories
            scheduler.add_job(
                sync_all_categories,
                trigger='interval',
                hours=1,
                id='news_sync',
                replace_existing=True,
                max_instances=1,
            )
            scheduler.start()
            print("[SERVER] All systems online (News + Events + Sync).")
        except Exception as e:
            print(f"[BOOT ERROR] {e}")

    asyncio.create_task(_total_boot())
    yield
    try:
        scheduler.shutdown(wait=False)
    except:
        pass

# ── App Definition ─────────────────────────────
app = FastAPI(
    title="Priority News Engine",
    version="2.0-python",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Fast Health Checks ─────────────────────────
@app.get("/")
async def root():
    return {"status": "Backend Live", "version": "2.0-python"}

@app.get("/api/health")
async def health():
    return {"success": True, "ping": "pong"}

@app.get("/api/unlock-news")
def unlock_all():
    """Manual trigger to bypass the drip-feed delay."""
    from services.models import SessionLocal, NewsArticle
    db = SessionLocal()
    try:
        count = db.query(NewsArticle).update({"visible_at": datetime.utcnow()})
        db.commit()
        return {"success": True, "unlocked": count}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()
