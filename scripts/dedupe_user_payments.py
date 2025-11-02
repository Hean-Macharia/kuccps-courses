#!/usr/bin/env python3
"""Deduplicate user_data.user_payments by keeping the oldest document per (email,index_number,level).

This script is destructive (deletes duplicate docs) but will:
 - export a full JSON backup of the collection before making changes
 - write a deletion log with IDs removed
 - attempt to recreate the unique partial index afterwards

Usage:
  python scripts/dedupe_user_payments.py

Configure MONGODB_URI in environment or in .env at repo root.
"""
import os
import json
import datetime
from pymongo import MongoClient

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

MONGODB_URI = os.environ.get('MONGODB_URI')
if not MONGODB_URI:
    print("ERROR: MONGODB_URI not set in environment or .env. Abort.")
    raise SystemExit(1)

client = MongoClient(MONGODB_URI)
db = client.get_database('user_data')
coll = db.get_collection('user_payments')

timestamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
backup_dir = os.path.join(os.getcwd(), 'backups')
os.makedirs(backup_dir, exist_ok=True)
backup_file = os.path.join(backup_dir, f'user_payments_backup_{timestamp}.json')

print(f"Exporting full collection to {backup_file}...")
with open(backup_file, 'w', encoding='utf-8') as bf:
    try:
        cursor = coll.find({})
        for doc in cursor:
            d = dict(doc)
            d['_id'] = str(d.get('_id'))
            bf.write(json.dumps(d, default=str) + "\n")
    except Exception as e:
        # Some Atlas tiers disallow noCursorTimeout or long-running cursors; fall back to materializing
        print(f"Warning: streaming backup failed ({e}), falling back to in-memory fetch")
        docs = list(coll.find({}))
        for doc in docs:
            d = dict(doc)
            d['_id'] = str(d.get('_id'))
            bf.write(json.dumps(d, default=str) + "\n")

print("Backup complete.")

# Find duplicate groups
pipeline = [
    {
        "$group": {
            "_id": {"email": "$email", "index_number": "$index_number", "level": "$level"},
            "count": {"$sum": 1},
            "ids": {"$push": "$_id"}
        }
    },
    {"$match": {"count": {"$gt": 1}, "_id.email": {"$ne": None}}}
]

duplicates = list(coll.aggregate(pipeline, allowDiskUse=True))
print(f"Found {len(duplicates)} duplicate groups to process")

deleted_ids = []
for grp in duplicates:
    ids = grp['ids']
    # sort ObjectIds lexicographically which corresponds to insertion order (oldest first)
    ids_sorted = sorted(ids)
    keep = ids_sorted[0]
    to_remove = ids_sorted[1:]
    if to_remove:
        print(f"Keeping {keep} and deleting {len(to_remove)} duplicates for {grp['_id']}")
        res = coll.delete_many({"_id": {"$in": to_remove}})
        deleted_ids.extend([str(i) for i in to_remove])

# write deletion log
log_file = os.path.join(backup_dir, f'deleted_user_payments_{timestamp}.json')
with open(log_file, 'w', encoding='utf-8') as lf:
    json.dump({"deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}, lf, indent=2)

print(f"Deleted {len(deleted_ids)} documents. Deletion log: {log_file}")

# Try to recreate unique partial index now that duplicates removed
partial_filter = { 'email': {'$type': 'string'}, 'index_number': {'$type': 'string'}, 'level': {'$type': 'string'} }
try:
    print("Attempting to create unique partial index on user_payments...")
    coll.create_index([('email', 1), ('index_number', 1), ('level', 1)], name='unique_email_index_level', unique=True, partialFilterExpression=partial_filter)
    print("✅ Unique partial index created successfully")
except Exception as e:
    print(f"⚠️ Failed to create unique index after dedupe: {e}")

print("Dedupe run complete.")
