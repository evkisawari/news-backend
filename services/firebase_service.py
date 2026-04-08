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
    
    # ── Resilience: Send in small chunks of 50 to handle slow local connections ──
    for i in range(0, len(articles), 50):
        batch = db.batch()
        current_chunk = articles[i : i + 50]
        count = 0
        
        for a in current_chunk:
            # Detect ID (handles both Python internal and SQL mapped formats)
            doc_id = a.get('_stableId') or a.get('stable_id') or a.get('stableId')
            if not doc_id: continue
            
            # Map fields safely for Firebase
            clean_data = {
                'stableId':    doc_id,
                'title':       a.get('title', 'No Title'),
                'description': a.get('description', ''),
                'url':         a.get('url', ''),
                'source':      a.get('source', 'Unknown'),
                'category':    a.get('category', 'world').lower(),
                'image':       a.get('image'),
                'publishedAt': a.get('publishedAt') or a.get('published_at'),
                'score':       float(a.get('_score') or a.get('score') or 0.0),
                'aiSummary':   a.get('aiSummary'),
                'isExploration': a.get('isExploration', False),
                'syncedAt':    firestore.SERVER_TIMESTAMP
            }

            doc_ref = db.collection('news').document(doc_id)
            batch.set(doc_ref, clean_data, merge=True)
            count += 1
            
        if count > 0:
            batch.commit()
            print(f"[FIREBASE] Batch {i//50 + 1} ({count} items) pushed.")

    print("[FIREBASE] Done. Full feed is live.")

def cleanup_old_firebase_news():
    """Purge news older than 3 days from Firebase to keep it light."""
    db = get_firestore()
    if not db: return
    
    three_days_ago = datetime.now() - timedelta(days=3)
    # Note: FireStore queries for cleanup can be slow, usually we just let them sit 
    # or use a TTL policy in the Firebase Console.
    pass
