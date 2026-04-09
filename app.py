import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Core Routes
from routes.news   import router as news_router
from routes.events import router as events_router

# ── Global Engine ───────────────────────────────
scheduler = AsyncIOScheduler(timezone="UTC")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background boot
    async def _boot_engine():
        await asyncio.sleep(5) 
        try:
            from services.models import init_db
            from services.fetchers import sync_all_categories
            init_db()
            
            # Start scheduler inside lifespan (Safe Mode)
            if not scheduler.running:
                from datetime import datetime
                scheduler.add_job(
                    sync_all_categories, 
                    'interval', 
                    minutes=60, 
                    id='news_sync',
                    next_run_time=datetime.now(timezone.utc)
                )
                scheduler.start()
                
            print("[SERVER] News engine active.")
        except Exception as e:
            print(f"[BOOT ERROR] {e}")

    asyncio.create_task(_boot_engine())
    yield

# ── App Definition ─────────────────────────────
app = FastAPI(title="Priority News Engine", version="2.0-python", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

from fastapi import BackgroundTasks

@app.get("/api/force-sync")
async def force_sync(background_tasks: BackgroundTasks):
    from services.fetchers import sync_all_categories
    background_tasks.add_task(sync_all_categories)
    return {"success": True, "message": "Manual sync started in background. News will appear shortly!"}
