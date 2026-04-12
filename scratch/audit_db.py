
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

from services.models import SessionLocal, NewsArticle
from sqlalchemy import func

def audit():
    db = SessionLocal()
    try:
        total = db.query(NewsArticle).count()
        print(f"Total articles in DB: {total}")
        
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        visible = db.query(NewsArticle).filter(NewsArticle.visible_at <= now).count()
        print(f"Visible articles (now={now}): {visible}")
        
        future = db.query(NewsArticle).filter(NewsArticle.visible_at > now).count()
        print(f"Future articles: {future}")
        
        if total > 0:
            latest = db.query(NewsArticle).order_by(NewsArticle.published_at.desc()).first()
            print(f"Latest published_at: {latest.published_at}")
            print(f"Latest visible_at: {latest.visible_at}")
            
            # Check categories
            cats = db.query(NewsArticle.category, func.count(NewsArticle.id)).group_by(NewsArticle.category).all()
            print("Categories:")
            for cat, count in cats:
                print(f"  {cat}: {count}")
    finally:
        db.close()

if __name__ == "__main__":
    audit()
