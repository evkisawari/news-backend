import asyncio
from services.scraper import scrape_article

async def test():
    urls = [
        "https://www.scotusblog.com/",
        "https://www.theguardian.com/international",
        "https://techmeme.com/"
    ]
    
    for url in urls:
        print(f"\n--- Testing URL: {url} ---")
        text = await scrape_article(url, max_words=150)
        if text:
            print(f"Extraction SUCCESS. Length: {len(text)} chars / {len(text.split())} words.")
            print("Preview:", text[:300], "...")
        else:
            print("Extraction FAILED.")

if __name__ == "__main__":
    asyncio.run(test())
