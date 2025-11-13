#!/usr/bin/env python3
"""Find duplicate (email, index_number, level) groups in user_data.user_payments.

This script is non-destructive: it only reports duplicate groups and writes a JSON report.
Run with the same environment used by the app so it picks up MONGODB_URI from env or .env.

Usage:
  python scripts/find_user_payments_duplicates.py

Output:
  - prints summary to stdout
  - writes `duplicates_user_payments.json` in the repo root with details
"""
import os
import json
from pymongo import MongoClient

# Try to load .env if present (so script works when env isn't exported)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # If python-dotenv isn't installed, try a simple .env parse
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as ef:
            for line in ef:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

MONGODB_URI = os.environ.get('MONGODB_URI')
if not MONGODB_URI:
    print("ERROR: MONGODB_URI not set in environment or .env. Set it or update .env file.")
    raise SystemExit(1)

client = MongoClient(MONGODB_URI)
db = client.get_database('user_data')
coll = db.get_collection('user_payments')

pipeline = [
    {
        "$group": {
            "_id": {"email": "$email", "index_number": "$index_number", "level": "$level"},
            "count": {"$sum": 1},
            "ids": {"$push": "$_id"}
        }
    },
    {"$match": {"count": {"$gt": 1}, "_id.email": {"$ne": None}}},
    {"$limit": 1000}
]

results = list(coll.aggregate(pipeline, allowDiskUse=True))

report = {
    "total_duplicate_groups": len(results),
    "groups": []
}

for grp in results:
    report["groups"].append({
        "email": grp["_id"]["email"],
        "index_number": grp["_id"]["index_number"],
        "level": grp["_id"]["level"],
        "count": grp["count"],
        "ids": [str(i) for i in grp["ids"]]
    })

out_path = os.path.join(os.getcwd(), 'duplicates_user_payments.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2)

print(f"Found {report['total_duplicate_groups']} duplicate groups. Report written to: {out_path}")
if report['total_duplicate_groups'] > 0:
    print("Sample group:")
    sample = report['groups'][0]
    print(json.dumps(sample, indent=2))
