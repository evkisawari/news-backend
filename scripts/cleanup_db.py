import os
import difflib
from sqlalchemy.orm import Session
from services.models import SessionLocal, NewsArticle
from dotenv import load_dotenv

load_dotenv()

def cleanup_duplicates():
    print("[CLEANUP] Starting deep deduplication of news database...")
    db = SessionLocal()
    try:
        # 1. Fetch all articles ordered by date (newest first)
        articles = db.query(NewsArticle).order_by(NewsArticle.published_at.desc()).all()
        print(f"[CLEANUP] Analyzing {len(articles)} articles...")
        
        seen_titles = []
        to_delete = []
        kept = 0
        
        for a in articles:
            title = (a.title or '').lower().strip()
            if not title:
                to_delete.append(a.id)
                continue
                
            # Check for fuzzy match against articles we've already decided to keep
            is_dupe = False
            # Check against local news window (last 100 kept articles)
            for t in seen_titles[-100:]:
                if difflib.SequenceMatcher(None, title, t).ratio() > 0.85:
                    is_dupe = True
                    break
            
            if is_dupe:
                to_delete.append(a.id)
            else:
                seen_titles.append(title)
                kept += 1
        
        print(f"[CLEANUP] Found {len(to_delete)} duplicate clones to delete.")
        
        # 2. Perform deletion in batches
        if to_delete:
            batch_size = 100
            for i in range(0, len(to_delete), batch_size):
                batch = to_delete[i:i+batch_size]
                db.query(NewsArticle).filter(NewsArticle.id.in_(batch)).delete(synchronize_session=False)
                db.commit()
                print(f"[CLEANUP] Deleted batch {i // batch_size + 1}...")
        
        print(f"[CLEANUP] FINISHED. Kept {kept} unique stories. Database is now clean.")
    except Exception as e:
        print(f"[CLEANUP] ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_duplicates()
