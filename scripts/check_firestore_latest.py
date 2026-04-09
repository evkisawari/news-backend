
from services.firebase_service import get_firestore
from datetime import datetime

def check_latest_firestore():
    db = get_firestore()
    if not db: 
        print("No DB connection")
        return
    docs = db.collection('news').order_by('publishedAt', direction='DESCENDING').limit(10).get()
    print(f"--- LATEST 10 IN FIRESTORE ---")
    for d in docs:
        data = d.to_dict()
        print(f"{data.get('publishedAt')} | {data.get('title')[:60]}...")

if __name__ == "__main__":
    check_latest_firestore()
