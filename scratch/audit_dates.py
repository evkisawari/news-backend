
import os
from dotenv import load_dotenv
load_dotenv()

from services.models import SessionLocal, NewsArticle
from sqlalchemy import desc

def audit_dates():
    db = SessionLocal()
    try:
        print("Checking Top 10 articles by published_at DESC:")
        rows = db.query(NewsArticle).order_by(desc(NewsArticle.published_at)).limit(10).all()
        for i, r in enumerate(rows):
            print(f"{i+1}. Title: {r.title[:40]}... | PublishedAt: {r.published_at} | VisibleAt: {r.visible_at}")
            
        null_count = db.query(NewsArticle).filter(NewsArticle.published_at == None).count()
        print(f"Total articles with NULL published_at: {null_count}")
        
    finally:
        db.close()

if __name__ == "__main__":
    audit_dates()
