
import requests
import os
from dotenv import load_dotenv
load_dotenv()

def test_keys():
    print("--- API KEY AUDIT ---")
    
    # 1. NewsData.io
    for i in range(1, 4):
        key = os.getenv(f'NEWSDATA_KEY_{i}') or os.getenv('NEWSDATA_KEY')
        if not key: continue
        url = f'https://newsdata.io/api/1/news?apikey={key}&country=us&language=en'
        try:
            r = requests.get(url)
            data = r.json()
            if data.get('status') == 'success':
                print(f"NEWSDATA KEY {i}: ✅ WORKING. Found {len(data.get('results', []))} articles.")
            else:
                print(f"NEWSDATA KEY {i}: ❌ FAILED. {data.get('results', {}).get('message', 'Unknown error')}")
        except Exception as e:
            print(f"NEWSDATA KEY {i}: ⚠️ ERROR: {e}")

    # 2. GNews
    for i in range(1, 4):
        key = os.getenv(f'GNEWS_API_KEY_{i}')
        if not key: continue
        url = f'https://gnews.io/api/v4/top-headlines?token={key}&lang=en&country=us'
        try:
            r = requests.get(url)
            if r.status_code == 200:
                print(f"GNEWS KEY {i}: ✅ WORKING. Found {len(r.json().get('articles', []))} articles.")
            else:
                print(f"GNEWS KEY {i}: ❌ FAILED (Status {r.status_code}). {r.json().get('errors', 'Unknown error')}")
        except Exception as e:
            print(f"GNEWS KEY {i}: ⚠️ ERROR: {e}")

if __name__ == "__main__":
    test_keys()
