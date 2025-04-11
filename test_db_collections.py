import os
from pymongo import MongoClient

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "swarmonomicon")

try:
    print(f"Connecting to MongoDB: {MONGODB_URI}")

    # Create MongoDB connection
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[MONGODB_DB]
    todos_collection = db["todos"]
    lessons_collection = db["lessons_learned"]

    print(f"MongoDB connection successful")
    print(f"Database: {db.name}")
    print(f"Collections:")
    print(f"  - todos: {todos_collection.name}")
    print(f"  - lessons: {lessons_collection.name}")

    # List all collections in the database
    print(f"Collection names in database: {db.list_collection_names()}")

    # Count documents in each collection
    print(f"Document counts:")
    print(f"  - todos: {todos_collection.count_documents({})}")
    print(f"  - lessons: {lessons_collection.count_documents({})}")

except Exception as e:
    print(f"Error: {str(e)}")
finally:
    # Close connection
    if 'mongo_client' in locals():
        mongo_client.close()
        print("MongoDB connection closed")
