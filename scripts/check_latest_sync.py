
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone
import os

cred_path = r"c:\Users\dparw\News backend\serviceAccountKey.json"

def check_latest():
    cred = credentials.Certificate(cred_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    docs = db.collection('news').order_by('syncedAt', direction=firestore.Query.DESCENDING).limit(1).get()
    
    if docs:
        data = docs[0].to_dict()
        print(f"Latest sync in Firestore: {data.get('syncedAt')}")
    else:
        print("No articles found.")

if __name__ == "__main__":
    check_latest()
