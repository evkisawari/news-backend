
import asyncio
import httpx
from services.fetchers import sync_all_categories
from services.firebase_service import push_news_to_firebase
from services.processor import deduplicate

async def test_push_to_firebase():
    print("🚀 STARTING LOCAL PROD PUSH (FIREBASE ONLY)...")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # We manually collect news and skip Postgres
        from services.fetchers import sync_category, CATEGORIES
        all_news = []
        for cat in CATEGORIES:
            try:
                cat_news = await sync_category(cat, client)
                all_news.extend(cat_news)
            except Exception as e:
                print(f"Error {cat}: {e}")
        
        # Deduplicate
        final = deduplicate(all_news)
        final.sort(key=lambda x: x.get('publishedAt', ''), reverse=True)
        
        print(f"✅ Found {len(final)} fresh articles. Pushing to FIREBASE now...")
        push_news_to_firebase(final[:100]) # Push top 100 fresh articles
        print("🎉 SUCCESS! Fresh news is now in your Prod Firestore.")

if __name__ == "__main__":
    asyncio.run(test_push_to_firebase())
