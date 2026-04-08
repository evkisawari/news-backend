import firebase_admin
from firebase_admin import credentials, firestore
import os
from typing import List, Dict, Any
from datetime import datetime, timedelta

# ── Initialization ──────────────────────────────
# We look for serviceAccountKey.json in the same folder as this script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cred_path = os.path.join(BASE_DIR, "serviceAccountKey.json")
_db = None

def get_firestore():
    global _db
    if _db: return _db
    
    if os.path.exists(cred_path):
        try:
            cred = credentials.Certificate(cred_path)
            # Check if app is already initialized
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            _db = firestore.client()
            return _db
        except Exception as e:
            print(f"[FIREBASE] Failed to initialize: {e}")
            return None
    else:
        print("[FIREBASE] Warning: serviceAccountKey.json not found. Firebase sync will be skipped.")
        return None

def push_news_to_firebase(articles: List[Dict[str, Any]]):
    """Pushes the top scored news to Firestore for ultra-fast Flutter access."""
    db = get_firestore()
    if not db: return

    print(f"[FIREBASE] Syncing {len(articles)} articles to Firestore...")
    
    # We use a batch to send multiple articles in one request (limited to 500 per batch)
    batch = db.batch()
    count = 0
    
    for a in articles:
        # 1. Prepare data for Firebase
        # We use stable_id as the document ID to prevent duplicates
        doc_id = a.get('_stableId')
        if not doc_id: continue
        
        # Firestore doesn't like keys with leading underscores
        clean_data = {
            'stableId':    doc_id,
            'title':       a.get('title'),
            'description': a.get('description'),
            'url':         a.get('url'),
            'source':      a.get('source'),
            'category':    a.get('category', 'world'),
            'image':       a.get('image'),
            'publishedAt': a.get('publishedAt'),
            'score':       a.get('_score', 0.0),
            'aiSummary':   a.get('aiSummary'),
            'visibleAt':   a.get('visibleAt'),
            'isExploration': a.get('isExploration', False),
            'syncedAt':    firestore.SERVER_TIMESTAMP
        }

        doc_ref = db.collection('news').document(doc_id)
        batch.set(doc_ref, clean_data)
        count += 1
        
        # Firestore batch limit is 500
        if count >= 450:
            batch.commit()
            batch = db.batch()
            count = 0
            
    batch.commit()
    print("[FIREBASE] Done. Feed is now live and instant in Firestore.")

def cleanup_old_firebase_news():
    """Purge news older than 3 days from Firebase to keep it light."""
    db = get_firestore()
    if not db: return
    
    three_days_ago = datetime.now() - timedelta(days=3)
    # Note: FireStore queries for cleanup can be slow, usually we just let them sit 
    # or use a TTL policy in the Firebase Console.
    pass
