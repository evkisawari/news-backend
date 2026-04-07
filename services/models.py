"""
services/models.py — SQLAlchemy ORM models for NewsArticles and UserProfiles.
"""
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import JSONB

# Render/Alembic normalization: postgres -> postgresql
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/news_db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class NewsArticle(Base):
    """Stores fetched articles (Step 7: Persisted in PostgreSQL)."""
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True)
    stable_id = Column(String, unique=True, index=True)  # MD5 fingerprint
    title = Column(String, index=True)
    description = Column(Text)
    url = Column(String)
    source = Column(String)
    category = Column(String, index=True)
    published_at = Column(DateTime)
    image_url = Column(String)
    score = Column(Float)
    ai_summary = Column(Text)
    is_exploration = Column(Boolean, default=False)
    source_type = Column(String)  # newsdata, gnews, rss
    weight = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserProfile(Base):
    """Stores anonymous user preferences (Step 14: Personalization loop)."""
    __tablename__ = "user_profiles"

    user_id = Column(String, primary_key=True, index=True)
    category_scores = Column(JSONB, default=dict)  # category -> float
    keyword_scores = Column(JSONB, default=dict)   # keyword -> count
    seen_articles = Column(JSONB, default=list)    # list of stable_ids

    total_events = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Safely inject the new seen_articles column into existing production databases
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS seen_articles JSONB DEFAULT '[]'::jsonb;"))
    except Exception as e:
        print("[DB] Note: Could not alter user_profiles (might already exist or unsupported):", e)
        
    print("[DB] Tables initialized in PostgreSQL.")
