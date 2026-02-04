# Duplicate Activity Log Entries - Fix Documentation

## Problem Description

The Activity Log in Inventorium was showing duplicate log entries for the same update operation. When metadata was updated, users would see:

1. **First log entry** - showing actual changes (e.g., `target_agent: None → user`, `metadata.files: [] → [path]`)
2. **Second log entry** (2 seconds later) - showing metadata change with **identical old/new values**

## Root Cause

The issue was caused by the **hybrid fallback system** in `Omnispindle`:

1. **API call** attempts to update todo → succeeds and logs change
2. **API response fails/times out** (network issue, slow response, etc.)
3. **Hybrid system thinks API failed** → falls back to local database
4. **Local update** re-updates the same todo (no real changes) → logs again with identical values
5. **Result**: Two log entries in database, second one is spurious

### Evidence

Database query showed:
- Entry 1 (14:52:06): `target_agent: null → user`, `metadata.files: [] → [path]`
- Entry 2 (14:52:08): `metadata` change where `old_value === new_value` (identical!)

## Solution

### 1. Prevent Logging Identical Changes (Code Fix)

**File**: `src/Omnispindle/tools.py` (lines 646-664)

**Changes**:
- Added deep comparison for metadata objects using JSON serialization
- Filter out changes where `old_value === new_value`
- Only log if there are actual changes detected
- Added debug logging to track when duplicate logging is prevented

**Code**:
```python
# Build changes list, filtering out identical values
changes = []
for field, value in updates.items():
    if field == 'updated_at':
        continue

    old_value = existing_todo.get(field)

    # Skip if values are identical
    if old_value == value:
        continue

    # For nested objects (like metadata), compare JSON representations
    if isinstance(old_value, dict) and isinstance(value, dict):
        import json as json_lib
        if json_lib.dumps(old_value, sort_keys=True) == json_lib.dumps(value, sort_keys=True):
            logger.debug(f"Skipping metadata log - old and new values are identical")
            continue

    changes.append({"field": field, "old_value": old_value, "new_value": value})

# Only log if there are actual changes
if changes:
    await log_todo_update(...)
else:
    logger.debug(f"No actual changes detected, skipping log entry")
```

### 2. Clean Up Existing Duplicates (Cleanup Script)

**File**: `scripts/dedupe_todo_logs.py`

**Purpose**: Remove existing duplicate log entries from the database

**How it works**:
1. Scans all user databases and `swarmonomicon`
2. Finds `update` logs from the last 7 days
3. Identifies logs where all changes have `old_value === new_value`
4. Removes these spurious log entries

**Usage**:
```bash
cd /Users/d.edens/lab/madness_interactive/projects/common/Omnispindle
python scripts/dedupe_todo_logs.py
```

Or on the server:
```bash
ssh eaws "cd /opt/omnispindle && python scripts/dedupe_todo_logs.py"
```

## Testing

1. **Verify the fix prevents new duplicates**:
   - Update a todo with metadata changes
   - Check Activity Log - should see only ONE entry
   - Check database - should see only ONE log document

2. **Run cleanup script**:
   ```bash
   python scripts/dedupe_todo_logs.py
   ```
   - Should report number of duplicate logs removed

3. **Check Activity Log UI**:
   - Open Dashboard → Activity Log
   - Filter by "Todos Updated"
   - Verify no duplicate entries for same todo/timestamp

## Deployment Checklist

- [x] Fix code in `tools.py` to prevent new duplicates
- [x] Create cleanup script to remove existing duplicates
- [ ] Commit changes to Omnispindle repo
- [ ] Deploy updated Omnispindle to server
- [ ] Run cleanup script on server: `ssh eaws "cd /opt/omnispindle && python scripts/dedupe_todo_logs.py"`
- [ ] Restart Omnispindle service: `ssh eaws "pm2 restart omnispindle"`
- [ ] Verify in Activity Log UI - no more duplicates

## Long-Term Improvements (Optional)

1. **Improve hybrid fallback detection**: Add response validation to distinguish between "API failed" vs "API succeeded but response lost"
2. **Add deduplication at log insertion**: Check for recent identical log entries before inserting
3. **Monitor hybrid fallback rate**: Track how often fallback occurs to optimize API reliability

## Related Files

- `src/Omnispindle/tools.py` - Main fix location
- `src/Omnispindle/hybrid_tools.py` - Hybrid fallback system
- `src/Omnispindle/todo_log_service.py` - Logging service
- `scripts/dedupe_todo_logs.py` - Cleanup script
- `src/components/ActivityLogPanel.jsx` - Frontend display (no changes needed)

## Git Commits

```bash
git add src/Omnispindle/tools.py scripts/dedupe_todo_logs.py docs/DUPLICATE_LOGS_FIX.md
git commit -m "fix(logging): Prevent duplicate activity log entries from hybrid fallback

- Filter out changes where old_value === new_value before logging
- Add deep comparison for metadata objects (JSON serialization)
- Create cleanup script to remove existing duplicate logs
- Resolves issue where hybrid fallback created spurious log entries"
```
