
import json
from datetime import datetime, timedelta, timezone
import os

db_path = r"c:\Users\dparw\News backend\db.json"

def check_local_db():
    if not os.path.exists(db_path):
        print("db.json not found.")
        return
    
    with open(db_path, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=8)
    # Note: Article publishedAt is sometimes naive, sometimes UTC.
    # Our DB helper says it's ISO.
    
    recent = []
    for a in articles:
        pub = a.get('publishedAt')
        if not pub: continue
        try:
            # Simple ISO parse
            dt = datetime.fromisoformat(pub.replace('Z', '+00:00'))
            if dt > cutoff:
                recent.append(a)
        except:
            continue
    
    print(f"Total articles in db.json: {len(articles)}")
    print(f"Articles added in last 8 hours in db.json: {len(recent)}")
    
    counts = {}
    for a in recent:
        st = a.get('_sourceType', 'unknown')
        counts[st] = counts.get(st, 0) + 1
    
    for k, v in counts.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    check_local_db()
