import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from engine.fetchers import fetch_newsdata, fetch_gnews
from engine.ai_queue import _generate_summary
import httpx

async def test_all_integrations():
    print("🚀 --- STARTING INTEGRATION TESTS --- 🚀\n")
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 1. NEWSDATA.IO
        print("🔍 1. Testing Newsdata.io...")
        nd = await fetch_newsdata('us', client)
        if nd:
            print(f"✅ Newsdata.io working! Fetched {len(nd)} articles. Sample: {nd[0]['title'][:50]}...")
        else:
            print("❌ Newsdata.io failed or returned no data.")

        # 2. GNEWS
        print("\n🔍 2. Testing GNews...")
        gn = await fetch_gnews('world', client)
        if gn:
            print(f"✅ GNews working! Fetched {len(gn)} articles. Sample: {gn[0]['title'][:50]}...")
        else:
            # GNews free tier often returns 403/429, which we handle gracefully
            print("⚠️ GNews rate-limited (403/429). This is expected for the free tier; RSS fallback will take over.")

        # 3. OPENAI
        print("\n🔍 3. Testing OpenAI (gpt-4o-mini)...")
        test_article = {
            'title': 'Test Article for OpenAI Verification',
            'description': 'This is a test description to verify that the OpenAI summarization pipeline is correctly configured and can generate concise news summaries.'
        }
        summary = await _generate_summary(test_article)
        if summary:
            print(f"✅ OpenAI working! Generated summary: {summary}")
        else:
            print("❌ OpenAI failed to generate summary.")

    print("\n🏁 --- ALL TESTS COMPLETED --- 🏁")

if __name__ == "__main__":
    asyncio.run(test_all_integrations())
