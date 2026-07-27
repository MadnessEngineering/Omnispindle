"""Tests for compact_todo helper — MCP response token efficiency."""
import json
import re

from Omnispindle.tools import (
    apply_response_diet,
    apply_todo_list_diet,
    compact_log_list,
    compact_stats_facets,
    compact_todo,
    compact_todo_list,
)


SAMPLE_TODO = {
    "_id": "6a1688c4c71b6c7a9939efd0",
    "id": "9fbe29b1-9f9c-481c-83a1-11b5e295dde5",
    "description": "fix the projects not selected bug",
    "project": "inventorium",
    "priority": "Medium",
    "status": "pending",
    "target": "user",
    "tags": ["bug-fix"],
    "created_at": 1779861700,
    "updated_at": 1779861713,
    "source": "personal",
    "metadata": {
        "created_by_ai": True,
        "user_id": "google-oauth2|115459928137014510094",
        "user_email": "danedens31@gmail.com",
        "chat_context": True,
        "tags": ["bug-fix"],  # duplicates top-level
        "complexity": "Medium",
        "blockers": ["abc-123"],
    },
    "notes": "Long multi-paragraph notes that bloat responses..." * 15,
}


def test_compact_always_strips_id_and_source():
    out = compact_todo(SAMPLE_TODO)
    assert "_id" not in out
    assert "source" not in out
    assert out["id"] == SAMPLE_TODO["id"]


def test_compact_strips_noise_metadata():
    out = compact_todo(SAMPLE_TODO)
    md = out["metadata"]
    for noise_key in ("user_id", "user_email", "created_by_ai", "chat_context"):
        assert noise_key not in md, f"{noise_key} should be stripped"
    # keep useful keys
    assert md["complexity"] == "Medium"
    assert md["blockers"] == ["abc-123"]


def test_compact_dedupes_metadata_tags():
    out = compact_todo(SAMPLE_TODO)
    # metadata.tags duplicates top-level tags → removed
    assert "tags" not in out.get("metadata", {})
    # top-level tags preserved
    assert out["tags"] == ["bug-fix"]


def test_compact_keeps_distinct_metadata_tags():
    doc = dict(SAMPLE_TODO)
    doc["metadata"] = dict(doc["metadata"])
    doc["metadata"]["tags"] = ["different", "tags"]
    out = compact_todo(doc)
    assert out["metadata"]["tags"] == ["different", "tags"]


def test_brief_strips_notes_and_updated_at():
    out = compact_todo(SAMPLE_TODO, brief=True)
    assert "notes" not in out
    assert "updated_at" not in out
    # essentials preserved
    assert out["description"] == SAMPLE_TODO["description"]
    assert out["status"] == "pending"


def test_brief_reduces_metadata_to_whitelist():
    out = compact_todo(SAMPLE_TODO, brief=True)
    md = out.get("metadata", {})
    # only blockers/files/complexity allowed in brief
    assert set(md.keys()) <= {"blockers", "files", "complexity"}
    assert md["blockers"] == ["abc-123"]
    assert md["complexity"] == "Medium"


def test_compact_todo_list_handles_none_entries():
    docs = [SAMPLE_TODO, None, dict(SAMPLE_TODO, id="other")]
    out = compact_todo_list(docs)
    assert len(out) == 2  # None dropped


def test_brief_response_is_substantially_smaller():
    full = json.dumps(compact_todo(SAMPLE_TODO))
    brief = json.dumps(compact_todo(SAMPLE_TODO, brief=True))
    # Brief should be at least 60% smaller given the bloated notes field
    assert len(brief) < len(full) * 0.4, f"brief={len(brief)} not much smaller than full={len(full)}"


def test_metadata_removed_when_empty_after_strip():
    doc = {
        "id": "x",
        "description": "test",
        "metadata": {"user_id": "noise", "user_email": "noise@x.com"},
    }
    out = compact_todo(doc)
    # all metadata keys stripped → metadata dropped entirely
    assert "metadata" not in out


def test_non_dict_passthrough():
    assert compact_todo("not a dict") == "not a dict"
    assert compact_todo(None) is None


# --- empty-field stripping -------------------------------------------------

def test_compact_drops_empty_fields():
    doc = {"id": "x", "description": "test", "ticket": "", "notes": "",
           "tags": [], "metadata": {}, "target": "user"}
    out = compact_todo(doc)
    for empty_key in ("ticket", "notes", "tags", "metadata"):
        assert empty_key not in out, f"{empty_key} should be stripped"
    assert out["target"] == "user"


def test_compact_keeps_falsy_but_meaningful_values():
    doc = {"id": "x", "description": "test", "metadata": {"archived": False, "hops": 0}}
    out = compact_todo(doc)
    assert out["metadata"] == {"archived": False, "hops": 0}


# --- iso_dates -------------------------------------------------------------

def test_iso_dates_off_by_default():
    out = compact_todo(SAMPLE_TODO)
    assert "created_at_iso" not in out
    assert out["created_at"] == SAMPLE_TODO["created_at"]


def test_iso_dates_mirrors_epoch_without_replacing_it():
    out = compact_todo(SAMPLE_TODO, iso_dates=True)
    # epoch preserved so `since`-style change detection keeps working
    assert out["created_at"] == SAMPLE_TODO["created_at"]
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", out["created_at_iso"])
    assert "updated_at_iso" in out


def test_iso_dates_skips_non_epoch_values():
    doc = {"id": "x", "description": "d", "created_at": "not-a-timestamp"}
    out = compact_todo(doc, iso_dates=True)
    assert "created_at_iso" not in out


def test_compact_todo_list_passes_iso_flag():
    out = compact_todo_list([SAMPLE_TODO], iso_dates=True)
    assert "created_at_iso" in out[0]


# --- apply_response_diet: search_todos auto-sizing -------------------------

def _todo(i, notes_len):
    return {"id": f"id-{i}", "description": "d", "notes": "x" * notes_len,
            "metadata": {"district": "core", "files": ["a.py"]}}


def test_diet_multi_hit_fat_notes_goes_brief():
    items, diet = apply_response_diet([_todo(i, 900) for i in range(4)])
    assert diet == "brief"
    assert all("notes" not in i for i in items)
    # brief metadata whitelist applied too
    assert all("district" not in i.get("metadata", {}) for i in items)


def test_diet_multi_hit_thin_notes_stays_full():
    items, diet = apply_response_diet([_todo(i, 20) for i in range(3)])
    assert diet == "full"
    assert all("notes" in i for i in items)


def test_diet_single_hit_keeps_notes():
    items, diet = apply_response_diet([_todo(0, 3000)])
    assert diet == "full"
    assert len(items[0]["notes"]) == 3000


def test_diet_single_hit_oversized_truncates_with_pointer():
    items, diet = apply_response_diet([_todo(0, 9000)])
    assert diet == "truncated"
    notes = items[0]["notes"]
    assert len(notes) < 9000
    assert "9000 chars total" in notes and "get_todo('id-0')" in notes


def test_diet_empty_and_missing_notes():
    assert apply_response_diet([]) == ([], "full")
    assert apply_response_diet([{"id": "a"}, {"id": "b"}])[1] == "full"


# --- apply_response_diet: description snippets + coordinates ---------------

def _hit(i, desc_len, notes_len=0):
    return {
        "id": f"id-{i}",
        "description": "x" * desc_len,
        "notes": "n" * notes_len,
        "metadata": {"coordinates": {"x": 1.0, "y": 2.0, "z": 3.0}, "files": ["a.py"]},
    }


def test_diet_drops_coordinates_from_search_hits():
    items, _ = apply_response_diet([_hit(i, 10) for i in range(3)])
    assert all("coordinates" not in i.get("metadata", {}) for i in items)
    # the rest of metadata survives
    assert all(i["metadata"]["files"] == ["a.py"] for i in items)


def test_diet_drops_top_level_coordinates():
    # The dashboard writes coordinates at the top level, not under metadata —
    # that's the spelling most live todos actually carry.
    docs = [
        {"id": f"id-{i}", "description": "d",
         "coordinates": {"x": 1.0, "y": 2.0, "z": 0, "lastUpdated": 1784959519242.0}}
        for i in range(3)
    ]
    items, _ = apply_response_diet(docs)
    assert all("coordinates" not in i for i in items)
    assert "coordinates" in docs[0]  # caller's copy untouched


def test_diet_drops_metadata_entirely_when_only_coordinates():
    items, _ = apply_response_diet([
        {"id": "a", "description": "d", "metadata": {"coordinates": {"x": 1}}},
        {"id": "b", "description": "d"},
    ])
    assert "metadata" not in items[0]


def test_diet_does_not_mutate_caller_items():
    original = [_hit(0, 10), _hit(1, 10)]
    apply_response_diet(original)
    assert "coordinates" in original[0]["metadata"]


def test_diet_snips_fat_descriptions_with_pointer():
    items, diet = apply_response_diet([_hit(i, 2000) for i in range(4)])
    assert diet == "truncated"
    assert all(len(i["description"]) < 2000 for i in items)
    assert "2000 chars total" in items[0]["description"]
    assert "get_todo('id-0')" in items[0]["description"]


def test_diet_snippet_centres_on_the_match():
    text = "a" * 3000 + "NEEDLE" + "b" * 3000
    items, diet = apply_response_diet(
        [{"id": "x", "description": text}, {"id": "y", "description": text}],
        query="needle",
    )
    assert diet == "truncated"
    assert "NEEDLE" in items[0]["description"]


def test_diet_thin_descriptions_stay_whole():
    items, diet = apply_response_diet([_hit(i, 100) for i in range(4)])
    assert diet == "full"
    assert all(len(i["description"]) == 100 for i in items)


def test_diet_brief_label_wins_over_snippet():
    items, diet = apply_response_diet([_hit(i, 2000, notes_len=900) for i in range(4)])
    assert diet == "brief"
    assert all("notes" not in i for i in items)
    assert "chars total" in items[0]["description"]


def test_diet_single_hit_keeps_full_description():
    items, diet = apply_response_diet([_hit(0, 9000)])
    assert diet == "full"
    assert len(items[0]["description"]) == 9000


# --- apply_todo_list_diet: query_todos auto-sizing -------------------------

def _list_todo(i, notes_len=0, prose_len=0):
    return {
        "id": f"id-{i}",
        "description": f"todo {i}",
        "project": "omnispindle",
        "status": "pending",
        "priority": "Medium",
        "created_at": 1785014364,
        "updated_at": 1785157707,
        "target_agent": "user",
        "notes": "n" * notes_len,
        "metadata": {
            "tags": ["mcp", "perf"],
            "files": ["src/Omnispindle/tools.py"],
            "current_state": "c" * prose_len,
            "target_state": "t" * prose_len,
        },
    }


def test_list_diet_fat_set_slims_to_essentials():
    items, diet = apply_todo_list_diet([_list_todo(i, 300, 300) for i in range(10)])
    assert diet == "brief"
    item = items[0]
    assert set(item) == {"id", "description", "project", "status", "priority", "metadata"}
    assert item["metadata"] == {"tags": ["mcp", "perf"], "files": ["src/Omnispindle/tools.py"]}
    assert "notes" not in item and "created_at" not in item


def test_list_diet_keeps_top_level_tags():
    # compact_todo dedupes metadata.tags up to the top level; the diet must not
    # drop them on the way out.
    docs = [dict(_list_todo(i), tags=["mcp"]) for i in range(10)]
    for d in docs:
        d["notes"] = "n" * 600
    items, diet = apply_todo_list_diet(docs)
    assert diet == "brief"
    assert items[0]["tags"] == ["mcp"]


def test_list_diet_thin_set_passes_through():
    docs = [_list_todo(i) for i in range(5)]
    items, diet = apply_todo_list_diet(docs)
    assert diet == "full"
    assert items[0] is docs[0]


def test_list_diet_single_item_never_slims():
    items, diet = apply_todo_list_diet([_list_todo(0, 9000, 9000)])
    assert diet == "full"
    assert len(items[0]["notes"]) == 9000


def test_list_diet_empty():
    assert apply_todo_list_diet([]) == ([], "full")


def test_list_diet_does_not_mutate_caller_items():
    docs = [_list_todo(i, 600, 600) for i in range(10)]
    apply_todo_list_diet(docs)
    assert "notes" in docs[0] and "current_state" in docs[0]["metadata"]


# --- compact_log_list: query_todo_logs -------------------------------------

def test_compact_log_entry_drops_object_id_and_empties():
    out = compact_log_list([{
        "_id": "68f0c0ffee0000000000dead",
        "todoId": "abc",
        "operation": "update",
        "changes": {},
        "userAgent": "",
        "source": "personal",
    }])
    assert out == [{"todoId": "abc", "operation": "update", "source": "personal"}]


def test_compact_log_list_skips_falsy_entries():
    assert compact_log_list([None, {}, {"_id": "x", "operation": "create"}]) == [
        {"operation": "create"}
    ]


# --- compact_stats_facets: get_metadata_stats ------------------------------

def test_compact_stats_renames_group_key_and_drops_nulls():
    out = compact_stats_facets({
        "tag_stats": [{"_id": "mcp", "count": 4}, {"_id": None, "count": 9}],
        "total_counts": [{"_id": None, "total_todos": 12, "with_tags": 7}],
    })
    assert out["tag_stats"] == [{"value": "mcp", "count": 4}]
    assert out["totals"] == {"total_todos": 12, "with_tags": 7}
    assert "total_counts" not in out


def test_compact_stats_drops_empty_facets():
    out = compact_stats_facets({
        "tag_stats": [{"_id": None, "count": 3}],
        "phase_stats": [{"_id": "build", "count": 1}],
    })
    assert "tag_stats" not in out
    assert out["phase_stats"] == [{"value": "build", "count": 1}]


def test_compact_stats_passthrough_non_dict():
    assert compact_stats_facets(None) is None
