
import os
from dotenv import load_dotenv
load_dotenv()

from services.models import SessionLocal, NewsArticle

def repair():
    db = SessionLocal()
    try:
        affected = db.query(NewsArticle).filter(NewsArticle.published_at == None).update({
            "published_at": NewsArticle.visible_at
        }, synchronize_session=False)
        db.commit()
        print(f"Repaired {affected} articles (set published_at = visible_at).")
    except Exception as e:
        print(f"Repair failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    repair()
