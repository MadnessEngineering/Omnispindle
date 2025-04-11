import sys
import os

# Add src directory to the path so we can import our module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Try importing our collections
try:
    from Omnispindle.tools import todos_collection, lessons_collection, db, mongo_client
    print(f"MongoDB connection successful")
    print(f"Database: {db.name}")
    print(f"Collections:")
    print(f"  - todos: {todos_collection.name}")
    print(f"  - lessons: {lessons_collection.name}")
    print("Collection names in database:", db.list_collection_names())
except Exception as e:
    print(f"Error: {str(e)}")
