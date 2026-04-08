from services.firebase_service import push_news_to_firebase
import os

test_article = [{
    '_stableId': 'test_sync_id',
    'title': '🔥 Firebase Connection Verified!',
    'description': 'If you see this in Firestore, your news app is now running at ultra-speed.',
    'url': 'https://google.com',
    'source': 'System Test',
    'category': 'world',
    'image': 'https://picsum.photos/400/300',
    'publishedAt': '2026-04-08T12:00:00Z',
    '_score': 10.0,
    'visibleAt': '2026-04-08T12:00:00Z'
}]

print("🧪 Starting Firebase Direct Test...")
try:
    push_news_to_firebase(test_article)
    print("✅ TEST COMPLETE. Check your Firestore 'news' collection!")
except Exception as e:
    print(f"❌ TEST FAILED: {e}")
