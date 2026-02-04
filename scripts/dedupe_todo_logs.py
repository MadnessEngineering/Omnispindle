#!/usr/bin/env python3
"""
Deduplicate todo_logs entries where metadata changes show identical old/new values.

This script:
1. Finds log entries where changes have identical old_value and new_value
2. Removes these spurious log entries (caused by hybrid fallback creating duplicates)
3. Operates on all user databases
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

def has_identical_changes(log_entry):
    """
    Check if a log entry has any changes where old_value === new_value.

    Args:
        log_entry: The log document from MongoDB

    Returns:
        True if all changes are identical (spurious update), False otherwise
    """
    changes = log_entry.get('changes', [])
    if not changes:
        return False

    all_identical = True
    has_metadata = False

    for change in changes:
        field = change.get('field')
        old_value = change.get('old_value')
        new_value = change.get('new_value')

        # Check if values are identical
        if old_value != new_value:
            # For dicts, compare JSON representations
            if isinstance(old_value, dict) and isinstance(new_value, dict):
                if json.dumps(old_value, sort_keys=True) != json.dumps(new_value, sort_keys=True):
                    all_identical = False
                    break
            else:
                all_identical = False
                break

        if field == 'metadata':
            has_metadata = True

    # Only consider it a duplicate if it has metadata changes and all are identical
    return has_metadata and all_identical


def dedupe_logs_for_database(client, db_name):
    """
    Deduplicate logs for a specific database.

    Args:
        client: MongoDB client
        db_name: Database name

    Returns:
        Number of logs removed
    """
    logger.info(f"Processing database: {db_name}")

    db = client[db_name]
    logs_collection = db['todo_logs']

    # Find recent update logs (last 7 days to avoid processing everything)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    query = {
        'operation': 'update',
        'timestamp': {'$gte': seven_days_ago}
    }

    logs = list(logs_collection.find(query).sort('timestamp', -1))
    logger.info(f"  Found {len(logs)} recent update logs")

    removed_count = 0
    for log in logs:
        if has_identical_changes(log):
            log_id = log['_id']
            timestamp = log.get('timestamp', 'unknown')
            todo_id = log.get('todoId', 'unknown')

            logger.info(f"  Removing duplicate log: {log_id} (todo: {todo_id}, time: {timestamp})")
            logs_collection.delete_one({'_id': log_id})
            removed_count += 1

    logger.info(f"  Removed {removed_count} duplicate logs from {db_name}")
    return removed_count


def main():
    """Main deduplication script"""
    logger.info("Starting todo_logs deduplication")
    logger.info(f"Connecting to MongoDB: {MONGODB_URI}")

    try:
        client = MongoClient(MONGODB_URI)

        # Get all databases
        all_dbs = client.list_database_names()

        # Filter for user databases and swarmonomicon
        target_dbs = [db for db in all_dbs if db.startswith('user_') or db == 'swarmonomicon']

        logger.info(f"Found {len(target_dbs)} databases to process")

        total_removed = 0
        for db_name in target_dbs:
            try:
                removed = dedupe_logs_for_database(client, db_name)
                total_removed += removed
            except Exception as e:
                logger.error(f"Error processing {db_name}: {str(e)}")
                continue

        logger.info(f"✅ Deduplication complete! Removed {total_removed} duplicate log entries total")

    except Exception as e:
        logger.error(f"❌ Deduplication failed: {str(e)}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
