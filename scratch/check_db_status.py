from dotenv import load_dotenv
load_dotenv()

from services.models import SessionLocal, NewsArticle
from datetime import datetime, timezone

def check_db():
    db = SessionLocal()
    try:
        count = db.query(NewsArticle).count()
        print(f"Total articles in DB: {count}")
        
        now = datetime.utcnow()
        visible_count = db.query(NewsArticle).filter(NewsArticle.visible_at <= now).count()
        print(f"Visible articles (ready for app): {visible_count}")
        
        latest = db.query(NewsArticle).order_by(NewsArticle.published_at.desc()).first()
        if latest:
            print(f"Latest article: {latest.title} (Published: {latest.published_at})")
        else:
            print("No articles found in DB.")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
