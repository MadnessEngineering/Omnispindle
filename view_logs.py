#!/usr/bin/env python3
"""
Script to view todo logs from MongoDB
"""

import pymongo
from datetime import datetime
import json
from bson import json_util

# Connect to MongoDB
client = pymongo.MongoClient('mongodb://localhost:27017')
db = client['swarmonomicon']
logs_collection = db['todo_logs']

# List collections to verify
collections = db.list_collection_names()
print(f"Available collections: {collections}")

# Query logs
logs = list(logs_collection.find().sort('timestamp', -1).limit(10))

print(f'Found {len(logs)} logs:')
print('-' * 80)

for log in logs:
    # Format the timestamp
    timestamp = log.get('timestamp')
    formatted_time = datetime.fromtimestamp(timestamp) if timestamp else 'Unknown time'
    
    # Print log details
    print(f"Operation: {log.get('operation', 'unknown')} | "
          f"Todo: {log.get('todoId', 'unknown')} | "
          f"Title: {log.get('todoTitle', 'unknown')} | "
          f"Project: {log.get('project', 'unknown')} | "
          f"Time: {formatted_time}")
    
    # Print changes if any
    changes = log.get('changes', [])
    if changes:
        print("  Changes:")
        for change in changes:
            print(f"    {change.get('field', '')}: "
                  f"{change.get('oldValue', '')} -> {change.get('newValue', '')}")
    
    # Print the full log for debugging
    print(f"  Full log: {json.dumps(json.loads(json_util.dumps(log)), indent=2)}")
    
    print('-' * 80) 
