import httpx
import json
import time

def verify():
    base_url = "http://localhost:5000"
    print(f"🚀 Starting Comprehensive Verification on {base_url}\n")
    
    # 1. Health check
    print("📋 [1/4] Checking /api/health...")
    try:
        r = httpx.get(f"{base_url}/api/health", timeout=5)
        print(f"   Status: {r.status_code}")
        print(f"   Body: {r.text}")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")

    # 2. News Feed (Technology)
    print("\n📰 [2/4] Checking /api/news?type=technology&limit=5...")
    try:
        r = httpx.get(f"{base_url}/api/news?type=technology&limit=5", timeout=5)
        data = r.json()
        print(f"   Status: {r.status_code}")
        print(f"   Articles Found: {len(data.get('articles', []))}")
        if data.get('articles'):
            print(f"   Sample Title: {data['articles'][0]['title'][:60]}...")
            print(f"   AI Summary Present: {data['articles'][0].get('hasAiSummary')}")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")

    # 3. User Events
    print("\n🖱️ [3/4] Checking /api/news/events (POST)...")
    try:
        payload = {
            "userId": "u_verify_test",
            "stableId": "test_id_123",
            "event": "click",
            "category": "technology"
        }
        r = httpx.post(f"{base_url}/api/news/events", json=payload, timeout=5)
        print(f"   Status: {r.status_code}")
        print(f"   Body: {r.text}")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")

    # 4. External Integrations (via script)
    print("\n🌐 [4/4] Double-checking external APIs (Newsdata/OpenAI)...")
    from test_integrations import test_all_integrations
    import asyncio
    asyncio.run(test_all_integrations())

    print("\n🏁 VERIFICATION COMPLETE")

if __name__ == "__main__":
    verify()
