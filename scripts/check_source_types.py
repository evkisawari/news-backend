
import firebase_admin
from firebase_admin import credentials, firestore
import os

cred_path = r"c:\Users\dparw\News backend\serviceAccountKey.json"

def check_for_newsdata():
    cred = credentials.Certificate(cred_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    docs = db.collection('news').get()
    
    newsdata_found = False
    for doc in docs:
        data = doc.to_dict()
        # In fetchers.py, NewsData sources use 'item.get('source_id')'
        # e.g. 'bbc-news', 'reuters', etc.
        # It's hard to tell without the tag, but usually they are short IDs.
        
        # Wait, I should check if there's any article with a sourceType field?
        # Oh, in firebase_service.py, it doesn't push it.
        pass

    # Let's check the local db.json if it has _sourceType
    import json
    db_json_path = r"c:\Users\dparw\News backend\db.json"
    if os.path.exists(db_json_path):
        with open(db_json_path, 'r', encoding='utf-8') as f:
            local_articles = json.load(f)
            counts = {}
            for a in local_articles:
                st = a.get('_sourceType', 'unknown')
                counts[st] = counts.get(st, 0) + 1
            print("Local db.json counts:")
            for k, v in counts.items():
                print(f"  {k}: {v}")

if __name__ == "__main__":
    check_for_newsdata()
