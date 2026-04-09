from services.models import SessionLocal, NewsArticle
from sqlalchemy import desc
from dotenv import load_dotenv
import os

load_dotenv()

def check_db_freshness():
    session = SessionLocal()
    try:
        print(f"Connecting to: {os.getenv('DATABASE_URL')}")
        articles = session.query(NewsArticle).order_by(desc(NewsArticle.published_at)).limit(10).all()
        print(f"\nTotal articles in DB: {session.query(NewsArticle).count()}")
        print("\n--- TOP 10 LATEST ARTICLES ---")
        for i, a in enumerate(articles):
            print(f"{i+1}. [{a.category}] {a.title}")
            print(f"   Published At: {a.published_at}")
            print(f"   Visible At: {a.visible_at}")
            print(f"   Source: {a.source}")
            print("-" * 30)
    finally:
        session.close()

if __name__ == "__main__":
    check_db_freshness()
