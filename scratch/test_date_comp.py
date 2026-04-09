from datetime import datetime, timezone

now_dt = datetime.now(timezone.utc)
now_iso = now_dt.isoformat()

# Simulate a naive datetime from DB
db_dt = now_dt.replace(tzinfo=None)
db_iso = db_dt.isoformat()

print(f"now_iso: {now_iso}")
print(f"db_iso:  {db_iso}")
print(f"db_iso <= now_iso: {db_iso <= now_iso}")

# Testing with 'Z' vs '+00:00'
z_iso = now_iso.replace('+00:00', 'Z')
print(f"db_iso <= z_iso:  {db_iso <= z_iso}")
