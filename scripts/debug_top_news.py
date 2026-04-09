
from services.firebase_service import get_firestore

def debug():
    db = get_firestore()
    docs = db.collection('news').order_by('publishedAt', direction='DESCENDING').limit(10).get()
    print("--- TOP 10 IN FIRESTORE ---")
    for d in docs:
        data = d.to_dict()
        print(f"{data.get('publishedAt')} | Score: {data.get('score')} | {data.get('title')[:60]}")

if __name__ == "__main__":
    debug()
