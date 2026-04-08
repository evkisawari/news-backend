import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv

load_dotenv()

def purge_news():
    print("🧹 [PURGE] Connecting to Firestore...")
    # Use existing firebase service logic to get db
    try:
        from services.firebase_service import get_firestore
        db = get_firestore()
        if not db:
            print("❌ [ERROR] Could not initialize Firestore. Check serviceAccountKey.json")
            return

        collection = db.collection('news')
        
        print("🔍 Scanning for records to purge...")
        docs = list(collection.limit(500).get()) # Limit to 500 per batch
        
        if not docs:
            print("✅ Collection already empty.")
            return

        print(f"🗑️ Deleting {len(docs)} documents...")
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        
        batch.commit()
        print(f"✨ [SUCCESS] Purged {len(docs)} articles. Run again if more remain.")
    except Exception as e:
        print(f"❌ [ERROR] Purge failed: {e}")

if __name__ == "__main__":
    purge_news()
