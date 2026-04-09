
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta, timezone
import os

cred_path = r"c:\Users\dparw\News backend\serviceAccountKey.json"

def check_recent():
    cred = credentials.Certificate(cred_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    docs = db.collection('news').where('syncedAt', '>', cutoff).get()
    
    print(f"Articles synced in last 10 minutes: {len(docs)}")
    
    for doc in docs[:5]:
        data = doc.to_dict()
        print(f" - {data.get('title')} ({data.get('source')})")

if __name__ == "__main__":
    check_recent()
