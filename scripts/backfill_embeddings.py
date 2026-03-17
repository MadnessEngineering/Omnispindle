#!/usr/bin/env python3
"""
Backfill vector embeddings for existing todos and lessons.

Iterates all user databases + shared database, generates Gemini embeddings
for documents that don't yet have an 'embedding' field.

Rate-limited: batches of 10 with 100ms delay between batches.
Idempotent: skips docs that already have embeddings.

Usage:
    python scripts/backfill_embeddings.py [--dry-run] [--db DATABASE_NAME]
"""

import asyncio
import argparse
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

from src.Omnispindle.embeddings import (
    generate_embedding,
    embedding_text_for_todo,
    embedding_text_for_lesson,
    is_available,
)


MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
BATCH_SIZE = 10
BATCH_DELAY = 0.1  # 100ms between batches


async def backfill_collection(collection, doc_type: str, text_fn, dry_run: bool = False) -> dict:
    """
    Backfill embeddings for a single collection.

    Returns:
        dict with counts: processed, embedded, skipped, errors
    """
    stats = {"processed": 0, "embedded": 0, "skipped": 0, "errors": 0}

    # Find docs without embeddings
    cursor = collection.find(
        {"embedding": {"$exists": False}},
        {"_id": 0, "id": 1, "description": 1, "notes": 1, "project": 1,
         "metadata": 1, "topic": 1, "lesson_learned": 1, "language": 1, "tags": 1},
    )
    docs = list(cursor)

    if not docs:
        print(f"  No documents need backfilling in {collection.name}")
        return stats

    print(f"  Found {len(docs)} documents without embeddings in {collection.name}")

    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i : i + BATCH_SIZE]

        for doc in batch:
            stats["processed"] += 1
            doc_id = doc.get("id")
            if not doc_id:
                stats["skipped"] += 1
                continue

            text = text_fn(doc)
            if not text.strip():
                stats["skipped"] += 1
                continue

            if dry_run:
                print(f"    [DRY RUN] Would embed {doc_type} {doc_id}: {text[:80]}...")
                stats["embedded"] += 1
                continue

            try:
                embedding = await generate_embedding(text)
                if embedding:
                    collection.update_one({"id": doc_id}, {"$set": {"embedding": embedding}})
                    stats["embedded"] += 1
                else:
                    stats["errors"] += 1
            except Exception as e:
                print(f"    Error embedding {doc_type} {doc_id}: {e}")
                stats["errors"] += 1

        # Rate limiting between batches
        if i + BATCH_SIZE < len(docs):
            await asyncio.sleep(BATCH_DELAY)
            # Progress indicator
            pct = min(100, int((i + BATCH_SIZE) / len(docs) * 100))
            print(f"    Progress: {pct}% ({i + BATCH_SIZE}/{len(docs)})")

    return stats


async def backfill_database(db, db_name: str, dry_run: bool = False) -> dict:
    """Backfill all collections in a single database."""
    print(f"\nProcessing database: {db_name}")
    results = {}

    # Backfill todos
    todos_col = db["todos"]
    todo_count = todos_col.count_documents({})
    if todo_count > 0:
        print(f"  Todos collection: {todo_count} total documents")
        results["todos"] = await backfill_collection(
            todos_col, "todo", embedding_text_for_todo, dry_run
        )
    else:
        print(f"  Todos collection: empty, skipping")
        results["todos"] = {"processed": 0, "embedded": 0, "skipped": 0, "errors": 0}

    # Backfill lessons
    lessons_col = db["lessons_learned"]
    lesson_count = lessons_col.count_documents({})
    if lesson_count > 0:
        print(f"  Lessons collection: {lesson_count} total documents")
        results["lessons"] = await backfill_collection(
            lessons_col, "lesson", embedding_text_for_lesson, dry_run
        )
    else:
        print(f"  Lessons collection: empty, skipping")
        results["lessons"] = {"processed": 0, "embedded": 0, "skipped": 0, "errors": 0}

    return results


async def main():
    parser = argparse.ArgumentParser(description="Backfill vector embeddings for Omnispindle")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--db", type=str, help="Only process a specific database name")
    args = parser.parse_args()

    if not is_available():
        print("ERROR: GEMINI_API_KEY not set. Cannot generate embeddings.")
        print("Set the environment variable and try again.")
        sys.exit(1)

    print("=== Omnispindle Embedding Backfill ===")
    if args.dry_run:
        print("MODE: DRY RUN (no changes will be made)")
    print(f"MongoDB: {MONGODB_URI}")
    print(f"Batch size: {BATCH_SIZE}, delay: {BATCH_DELAY}s")

    client = MongoClient(MONGODB_URI)
    start_time = time.time()
    all_results = {}

    if args.db:
        # Process a specific database
        db = client[args.db]
        all_results[args.db] = await backfill_database(db, args.db, args.dry_run)
    else:
        # Discover all user databases + shared database
        db_names = client.list_database_names()
        target_dbs = [
            name for name in db_names
            if name.startswith("user_") or name == "swarmonomicon"
        ]
        print(f"\nFound {len(target_dbs)} target databases: {target_dbs}")

        for db_name in sorted(target_dbs):
            db = client[db_name]
            all_results[db_name] = await backfill_database(db, db_name, args.dry_run)

    # Summary
    elapsed = time.time() - start_time
    total_embedded = sum(
        r.get("todos", {}).get("embedded", 0) + r.get("lessons", {}).get("embedded", 0)
        for r in all_results.values()
    )
    total_errors = sum(
        r.get("todos", {}).get("errors", 0) + r.get("lessons", {}).get("errors", 0)
        for r in all_results.values()
    )

    print(f"\n=== Backfill Complete ===")
    print(f"Databases processed: {len(all_results)}")
    print(f"Documents embedded: {total_embedded}")
    print(f"Errors: {total_errors}")
    print(f"Time: {elapsed:.1f}s")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
