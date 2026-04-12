
import httpx
import json

url_explore = "https://news-backend-1-bisp.onrender.com/api/news?limit=10&category=all&screen=explore"
url_home = "https://news-backend-1-bisp.onrender.com/api/news?limit=10&category=all&screen=home"

def check_prod():
    for name, url in [("EXPLORE", url_explore), ("HOME", url_home)]:
        try:
            print(f"Hiting PROD {name} URL: {url}")
            resp = httpx.get(url, timeout=30.0)
            print(f"Status: {resp.status_code}")
            data = resp.json()
            print(f"Success: {data.get('success')}")
            articles = data.get('articles', [])
            print(f"Article count: {len(articles)}")
            if articles:
                for a in articles:
                    print(f" - {a.get('title')} ({a.get('publishedAt')})")
            else:
                print("NO ARTICLES RETURNED.")
                print(f"Meta: {data.get('meta')}")
            print("-" * 20)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check_prod()
