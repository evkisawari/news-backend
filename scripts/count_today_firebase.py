
from services.firebase_service import get_firestore
from datetime import datetime, timezone, timedelta

def count_today():
    db = get_firestore()
    if not db:
        print("Could not connect to Firebase")
        return
    
    # 1. Get count of all articles today
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    docs = db.collection('news').where('publishedAt', '>=', today_start).get()
    print(f"Total articles in Firebase from today: {len(docs)}")
    
    # 2. Break down by category
    cats = {}
    for d in docs:
        c = d.to_dict().get('category', 'unknown')
        cats[c] = cats.get(c, 0) + 1
    
    print("Breakdown by Category:")
    for c, count in cats.items():
        print(f" - {c}: {count}")

if __name__ == "__main__":
    count_today()
