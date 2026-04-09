
from services.firebase_service import get_firestore

def purge_fast():
    db = get_firestore()
    docs = db.collection('news').limit(200).get()
    while len(docs) > 0:
        batch = db.batch()
        for d in docs:
            batch.delete(d.reference)
        batch.commit()
        print(f"Deleted {len(docs)} articles...")
        docs = db.collection('news').limit(200).get()
    print("🔥 FIRESTORE WIPED CLEAN (FAST).")

if __name__ == "__main__":
    purge_fast()
