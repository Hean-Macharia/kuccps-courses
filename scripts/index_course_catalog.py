"""Export only course catalog records from the existing MongoDB databases.

Read-only command: python scripts/index_course_catalog.py
Requires MONGODB_URI in the environment or project .env. It never scans the
user_data database and never writes to MongoDB.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
from pymongo import MongoClient  # noqa: E402

load_dotenv(ROOT / ".env")
DATABASES = ("Degree", "diploma", "kmtc", "certificate", "artisan", "Teachers")
FIELDS = (
    "programme_name", "course_name", "programme_code", "course_code",
    "institution_name", "minimum_grade", "minimum_subject_requirements",
    "cut_off_points", "cluster", "duration", "description", "entry_requirements",
)
OUTPUT = ROOT / "knowledge" / "course_catalog.jsonl"


def main():
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise SystemExit("MONGODB_URI is not configured; no catalog export was made.")
    client = MongoClient(uri, serverSelectionTimeoutMS=7000, connectTimeoutMS=7000, readPreference="secondaryPreferred")
    try:
        client.admin.command("ping")
        indexed_at = datetime.now(timezone.utc).isoformat()
        records = []
        for database_name in DATABASES:
            database = client[database_name]
            for collection_name in database.list_collection_names():
                collection = database[collection_name]
                projection = {field: 1 for field in FIELDS}
                for document in collection.find({}, projection).batch_size(500):
                    title = document.get("programme_name") or document.get("course_name")
                    if not title:
                        continue
                    details = {field: document[field] for field in FIELDS if field in document and document[field] not in (None, "", [], {})}
                    # Only serialize catalog fields, never IDs, student profiles or payment information.
                    records.append({
                        "source_type": "course_catalog",
                        "database": database_name,
                        "collection": collection_name,
                        "title": str(title),
                        "content": json.dumps(details, ensure_ascii=False, default=str),
                        "indexed_at": indexed_at,
                    })
        if not records:
            raise SystemExit("No course records were found; any existing local catalog index was left unchanged.")
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        temporary = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as output:
            for record in records:
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
        temporary.replace(OUTPUT)
        print(f"Indexed {len(records)} course records from {len(DATABASES)} read-only catalog databases into {OUTPUT}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
