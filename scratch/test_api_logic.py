
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

from services.database import load_db

def test_load():
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    
    print(f"Testing load_db with now_iso={now_iso}")
    articles = load_db(category='all', now_iso=now_iso)
    print(f"Found {len(articles)} articles for 'all'")
    
    if articles:
        print(f"First article: {articles[0].get('title')} (publishedAt: {articles[0].get('publishedAt')}, visibleAt: {articles[0].get('visibleAt')})")
    
    cat_articles = load_db(category='technology', now_iso=now_iso)
    print(f"Found {len(cat_articles)} articles for 'technology'")

if __name__ == "__main__":
    test_load()
