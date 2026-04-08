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
        await asyncio.sleep(3) 
        try:
            from services.models import init_db
            from services.fetchers import sync_all_categories
            # Initialize DB and run cleanup
            init_db()
            
            # Start scheduler (every 60 mins)
            scheduler.add_job(sync_all_categories, trigger='interval', hours=1, id='news_sync')
            scheduler.start()
            print("[SERVER] News engine active.")
        except Exception as e:
            print(f"[BOOT ERROR] {e}")

    asyncio.create_task(_boot_engine())
    yield
    try:
        scheduler.shutdown(wait=False)
    except:
        pass

# ── App Definition ─────────────────────────────
app = FastAPI(title="Priority News Engine", version="2.0-python", lifespan=lifespan)

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
        count = db.query(NewsArticle).update({"visible_at": datetime.utcnow()})
        db.commit()
        return {"success": True, "unlocked": count}
    finally:
        db.close()
