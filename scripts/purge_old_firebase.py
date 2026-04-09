
from services.firebase_service import get_firestore
from datetime import datetime, timezone, timedelta

def purge_old():
    db = get_firestore()
    # Find anything from April 4th (or earlier)
    # Today is April 9th. We want to keep ONLY April 7, 8, 9.
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    iso_cutoff = cutoff.isoformat()
    
    docs = db.collection('news').where('publishedAt', '<', iso_cutoff).get()
    print(f"Purging {len(docs)} stale news docs...")
    
    batch = db.batch()
    for d in docs:
        batch.delete(d.reference)
    
    if len(docs) > 0:
        batch.commit()
    print("Purge complete.")

if __name__ == "__main__":
    purge_old()
