
from services.firebase_service import get_firestore

def check():
    db = get_firestore()
    docs = db.collection('news').limit(20).get()
    print("--- CATEGORY CHECK ---")
    for d in docs:
        data = d.to_dict()
        print(f"Title: {data.get('title')[:30]}... | Category: '{data.get('category')}'")

if __name__ == "__main__":
    check()
