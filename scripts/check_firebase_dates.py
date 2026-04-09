
from services.firebase_service import get_firestore
from datetime import datetime

def check_firebase():
    db = get_firestore()
    if not db:
        print("Could not connect to Firebase")
        return
    
    # Check US category
    docs = db.collection('news').where('category', '==', 'us').order_by('publishedAt', direction='DESCENDING').limit(10).get()
    print(f"Total US articles found: {len(docs)}")
    for d in docs:
        data = d.to_dict()
        print(f" - {data.get('publishedAt')} | {data.get('title')[:50]}...")

if __name__ == "__main__":
    check_firebase()
