import json
from pathlib import Path

db_path = Path("db.json")
if db_path.exists():
    db = json.load(open(db_path, encoding='utf-8'))
    summaries = [a for a in db if a.get('aiSummary')]
    print(f"Total articles: {len(db)}")
    print(f"Articles with AI summaries: {len(summaries)}")
    for a in summaries[:5]:
        print(f"\n- TITLE: {a.get('title')[:100]}")
        print(f"  AI SUMMARY: {a.get('aiSummary')}")
else:
    print("db.json not found")
