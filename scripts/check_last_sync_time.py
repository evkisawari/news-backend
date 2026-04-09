
from services.firebase_service import get_firestore
from datetime import datetime

def check_last_sync():
    db = get_firestore()
    if not db: return
    docs = db.collection('news').order_by('syncedAt', direction='DESCENDING').limit(1).get()
    if docs:
        data = docs[0].to_dict()
        print(f"Last Sync At: {data.get('syncedAt')}")
        print(f"Last Article: {data.get('title')}")
    else:
        print("No articles found with syncedAt")

if __name__ == "__main__":
    check_last_sync()
