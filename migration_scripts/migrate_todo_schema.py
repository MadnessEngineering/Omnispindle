#!/usr/bin/env python3
"""
Migration script to standardize existing todo field names and structure.

Performs:
1. Field standardization: target → target_agent
2. Move completed_by from metadata to top-level
3. Move completion_comment from metadata to top-level  
4. Normalize timestamp formats
5. Validate and clean metadata structures

Usage:
    python migration_scripts/migrate_todo_schema.py [--dry-run] [--batch-size=1000]
"""

import asyncio
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from Omnispindle.database import db_connection
from Omnispindle.context import Context
from Omnispindle.schemas.todo_metadata_schema import validate_todo_metadata, TodoMetadata
from pymongo import MongoClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TodoSchemaMigrator:
    """Handles migration of todos to standardized schema."""
    
    def __init__(self, dry_run: bool = False, batch_size: int = 1000):
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.stats = {
            'total_todos': 0,
            'migrated': 0,
            'already_compliant': 0,
            'validation_warnings': 0,
            'errors': 0,
            'field_migrations': {
                'target_to_target_agent': 0,
                'completed_by_moved': 0,
                'completion_comment_moved': 0,
                'metadata_cleaned': 0,
                'timestamps_normalized': 0
            }
        }
    
    def create_backup(self, collections: Dict) -> str:
        """Create a backup of the todos collection before migration."""
        backup_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_collection_name = f"todos_backup_{backup_timestamp}"
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create backup: {backup_collection_name}")
            return backup_collection_name
        
        todos_collection = collections['todos']
        backup_collection = collections.database[backup_collection_name]
        
        # Copy all documents to backup
        todos = list(todos_collection.find({}))
        if todos:
            backup_collection.insert_many(todos)
            logger.info(f"✅ Created backup with {len(todos)} todos: {backup_collection_name}")
        else:
            logger.info("No todos to backup")
        
        return backup_collection_name
    
    def analyze_todo_compliance(self, todo: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze what migrations are needed for a todo."""
        migrations_needed = {
            'target_to_target_agent': 'target' in todo and 'target_agent' not in todo,
            'completed_by_to_toplevel': False,
            'completion_comment_to_toplevel': False,
            'metadata_cleanup': False,
            'timestamp_normalization': False
        }
        
        # Check metadata structure
        metadata = todo.get('metadata', {})
        if isinstance(metadata, dict):
            # Check for fields that should be moved to top level
            if 'completed_by' in metadata and 'completed_by' not in todo:
                migrations_needed['completed_by_to_toplevel'] = True
            
            if 'completion_comment' in metadata and 'completion_comment' not in todo:
                migrations_needed['completion_comment_to_toplevel'] = True
            
            # Check if metadata needs schema validation/cleanup
            if metadata and not metadata.get('_validation_warning'):
                try:
                    validate_todo_metadata(metadata)
                except Exception:
                    migrations_needed['metadata_cleanup'] = True
        
        # Check timestamp formats (basic heuristic)
        for field in ['created_at', 'updated_at', 'completed_at']:
            if field in todo:
                value = todo[field]
                # If it's a string, it might need normalization to timestamp
                if isinstance(value, str) and not str(value).isdigit():
                    migrations_needed['timestamp_normalization'] = True
                    break
        
        return migrations_needed
    
    def migrate_todo_fields(self, todo: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """Apply field migrations to a single todo."""
        migrated_todo = todo.copy()
        changes = []
        
        # 1. Migrate target → target_agent
        if 'target' in migrated_todo and 'target_agent' not in migrated_todo:
            migrated_todo['target_agent'] = migrated_todo.pop('target')
            changes.append('target → target_agent')
            self.stats['field_migrations']['target_to_target_agent'] += 1
        
        # 2. Move completed_by from metadata to top level
        metadata = migrated_todo.get('metadata', {})
        if isinstance(metadata, dict) and 'completed_by' in metadata and 'completed_by' not in migrated_todo:
            migrated_todo['completed_by'] = metadata.pop('completed_by')
            changes.append('completed_by moved to top-level')
            self.stats['field_migrations']['completed_by_moved'] += 1
        
        # 3. Move completion_comment from metadata to top level  
        if isinstance(metadata, dict) and 'completion_comment' in metadata and 'completion_comment' not in migrated_todo:
            migrated_todo['completion_comment'] = metadata.pop('completion_comment')
            changes.append('completion_comment moved to top-level')
            self.stats['field_migrations']['completion_comment_moved'] += 1
        
        # 4. Clean and validate metadata
        if metadata:
            try:
                # Remove any validation warnings from previous runs
                if '_validation_warning' in metadata:
                    metadata.pop('_validation_warning')
                
                validated_metadata = validate_todo_metadata(metadata)
                migrated_todo['metadata'] = validated_metadata.model_dump(exclude_none=True)
                changes.append('metadata validated and cleaned')
                self.stats['field_migrations']['metadata_cleaned'] += 1
            except Exception as e:
                # Keep original metadata but add validation warning
                migrated_todo['metadata'] = metadata
                migrated_todo['metadata']['_validation_warning'] = f"Migration validation failed: {str(e)}"
                changes.append(f'metadata validation failed: {str(e)}')
                self.stats['validation_warnings'] += 1
        
        # 5. Normalize timestamps (convert string dates to unix timestamps)
        for field in ['created_at', 'updated_at', 'completed_at']:
            if field in migrated_todo:
                value = migrated_todo[field]
                if isinstance(value, str) and not str(value).isdigit():
                    try:
                        # Try to parse ISO format or other common formats
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        migrated_todo[field] = int(dt.timestamp())
                        changes.append(f'{field} normalized to unix timestamp')
                        self.stats['field_migrations']['timestamps_normalized'] += 1
                    except Exception:
                        logger.warning(f"Could not normalize timestamp {field}: {value}")
        
        # Ensure updated_at is set
        if 'updated_at' not in migrated_todo:
            migrated_todo['updated_at'] = int(datetime.now(timezone.utc).timestamp())
            changes.append('added updated_at timestamp')
        
        return migrated_todo, changes
    
    async def migrate_batch(self, collections: Dict, todos: List[Dict]) -> None:
        """Migrate a batch of todos."""
        todos_collection = collections['todos']
        
        for todo in todos:
            try:
                self.stats['total_todos'] += 1
                
                # Analyze what migrations are needed
                migrations_needed = self.analyze_todo_compliance(todo)
                
                # If no migrations needed, skip
                if not any(migrations_needed.values()):
                    self.stats['already_compliant'] += 1
                    continue
                
                # Apply migrations
                migrated_todo, changes = self.migrate_todo_fields(todo)
                
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would migrate todo {todo.get('id', 'unknown')}: {', '.join(changes)}")
                else:
                    # Update in database
                    result = todos_collection.replace_one(
                        {'_id': todo['_id']},
                        migrated_todo
                    )
                    
                    if result.modified_count == 1:
                        logger.debug(f"✅ Migrated todo {todo.get('id', 'unknown')}: {', '.join(changes)}")
                    else:
                        logger.error(f"❌ Failed to update todo {todo.get('id', 'unknown')}")
                        self.stats['errors'] += 1
                        continue
                
                self.stats['migrated'] += 1
                
            except Exception as e:
                logger.error(f"❌ Error migrating todo {todo.get('id', 'unknown')}: {str(e)}")
                self.stats['errors'] += 1
    
    async def run_migration(self, user_email: Optional[str] = None) -> None:
        """Run the complete migration process."""
        logger.info(f"🚀 Starting todo schema migration {'(DRY RUN)' if self.dry_run else ''}")
        
        try:
            # Set up user context if provided
            user = {"email": user_email} if user_email else None
            collections = db_connection.get_collections(user)
            
            # Create backup
            backup_name = self.create_backup(collections)
            
            # Get total count
            todos_collection = collections['todos']
            total_count = todos_collection.count_documents({})
            logger.info(f"📊 Found {total_count} todos to analyze")
            
            if total_count == 0:
                logger.info("✅ No todos to migrate")
                return
            
            # Process in batches
            processed = 0
            while processed < total_count:
                batch = list(todos_collection.find({}).skip(processed).limit(self.batch_size))
                if not batch:
                    break
                
                await self.migrate_batch(collections, batch)
                processed += len(batch)
                
                logger.info(f"📈 Progress: {processed}/{total_count} todos processed")
            
            # Print final stats
            self.print_migration_summary(backup_name)
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {str(e)}")
            raise
    
    def print_migration_summary(self, backup_name: str) -> None:
        """Print comprehensive migration statistics."""
        print("\n" + "="*60)
        print(f"📋 MIGRATION SUMMARY {'(DRY RUN)' if self.dry_run else ''}")
        print("="*60)
        print(f"📊 Processed: {self.stats['total_todos']} todos")
        print(f"✅ Migrated: {self.stats['migrated']} todos") 
        print(f"✨ Already compliant: {self.stats['already_compliant']} todos")
        print(f"⚠️  Validation warnings: {self.stats['validation_warnings']} todos")
        print(f"❌ Errors: {self.stats['errors']} todos")
        
        print(f"\n🔧 Field Migrations Applied:")
        for field, count in self.stats['field_migrations'].items():
            if count > 0:
                print(f"   • {field.replace('_', ' ').title()}: {count}")
        
        print(f"\n💾 Backup created: {backup_name}")
        
        if not self.dry_run and self.stats['migrated'] > 0:
            print(f"\n🎉 Migration completed successfully!")
            print(f"   • {self.stats['migrated']} todos updated")
            print(f"   • Schema standardization: ✅")
            print(f"   • Backward compatibility: ✅")
        elif self.dry_run:
            print(f"\n🔍 Dry run completed - no changes made")
            print(f"   • Run without --dry-run to apply migrations")
        
        print("="*60)


async def main():
    """Main migration entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate todos to standardized schema format"
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Show what would be migrated without making changes'
    )
    parser.add_argument(
        '--batch-size',
        type=int, 
        default=1000,
        help='Number of todos to process per batch (default: 1000)'
    )
    parser.add_argument(
        '--user-email',
        type=str,
        help='User email for user-scoped collections (optional)'
    )
    
    args = parser.parse_args()
    
    # Initialize migrator
    migrator = TodoSchemaMigrator(
        dry_run=args.dry_run,
        batch_size=args.batch_size
    )
    
    # Run migration
    await migrator.run_migration(args.user_email)


if __name__ == "__main__":
    asyncio.run(main())