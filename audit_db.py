from services.models import SessionLocal, NewsArticle
from services.firebase_service import get_firestore

def audit_databases():
    # 1. Count Local SQL articles
    session = SessionLocal()
    try:
        sql_count = session.query(NewsArticle).count()
        print(f"📊 PostgreSQL Articles: {sql_count}")
    except Exception as e:
        print(f"⚠️ Could not check PostgreSQL (likely waiting for Render): {e}")
    finally:
        session.close()

    # 2. Count Firebase articles
    db = get_firestore()
    if db:
        try:
            # Note: For large collections, we'd use aggregation, but for <1k docs this is fine
            docs = db.collection('news').get()
            print(f"🔥 Firebase Articles: {len(docs)}")
        except Exception as e:
            print(f"⚠️ Firebase check failed: {e}")
    else:
        print("⚠️ Firebase not initialized.")

if __name__ == "__main__":
    audit_databases()
