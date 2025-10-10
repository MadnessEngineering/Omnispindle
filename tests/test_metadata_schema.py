"""
Comprehensive tests for todo metadata schema validation.

Tests the standardized metadata schema for:
- Schema validation works correctly
- Backward compatibility is maintained
- Error handling for invalid data
- Edge cases and boundary conditions
"""

import pytest
import time
from uuid import uuid4
from typing import Dict, Any
from pydantic import ValidationError

# Import the schemas we're testing
from src.Omnispindle.schemas.todo_metadata_schema import (
    TodoMetadata,
    TodoSchema,
    TodoCreateRequest,
    TodoUpdateRequest,
    PriorityLevel,
    StatusLevel,
    ComplexityLevel,
    validate_todo_metadata,
    validate_todo
)


class TestTodoMetadata:
    """Test TodoMetadata schema validation."""

    def test_minimal_valid_metadata(self):
        """Test minimal valid metadata (all fields optional)."""
        metadata = TodoMetadata()
        assert metadata is not None
        assert metadata.files is None
        assert metadata.custom is None

    def test_full_valid_metadata(self):
        """Test metadata with all fields populated."""
        metadata_data = {
            "files": ["src/test.py", "docs/readme.md"],
            "components": ["UserComponent", "AuthComponent"],
            "commit_hash": "abc123def456",
            "branch": "feature/test-branch",
            "phase": "implementation",
            "epic": "user-management",
            "tags": ["bug", "high-priority", "backend"],
            "current_state": "needs_testing",
            "target_state": "fully_tested",
            "blockers": ["uuid-1", "uuid-2"],
            "deliverables": ["test_file.py", "documentation.md"],
            "acceptance_criteria": [
                "All unit tests pass",
                "Code coverage > 90%",
                "Documentation updated"
            ],
            "complexity": "High",
            "confidence": 4,
            "custom": {"team": "backend", "reviewer": "john@example.com"},
            "completed_by": "test@example.com",
            "completion_comment": "Completed with minor issues resolved"
        }

        metadata = TodoMetadata(**metadata_data)

        # Verify all fields are set correctly
        assert metadata.files == ["src/test.py", "docs/readme.md"]
        assert metadata.components == ["UserComponent", "AuthComponent"]
        assert metadata.commit_hash == "abc123def456"
        assert metadata.branch == "feature/test-branch"
        assert metadata.phase == "implementation"
        assert metadata.epic == "user-management"
        assert metadata.tags == ["bug", "high-priority", "backend"]
        assert metadata.current_state == "needs_testing"
        assert metadata.target_state == "fully_tested"
        assert metadata.blockers == ["uuid-1", "uuid-2"]
        assert metadata.deliverables == ["test_file.py", "documentation.md"]
        assert metadata.acceptance_criteria == [
            "All unit tests pass",
            "Code coverage > 90%",
            "Documentation updated"
        ]
        assert metadata.complexity == ComplexityLevel.HIGH
        assert metadata.confidence == 4
        assert metadata.custom == {"team": "backend", "reviewer": "john@example.com"}
        assert metadata.completed_by == "test@example.com"
        assert metadata.completion_comment == "Completed with minor issues resolved"

    def test_array_validation_removes_empty_strings(self):
        """Test that array validators remove empty strings."""
        metadata = TodoMetadata(
            files=["valid_file.py", "", "  ", "another_file.py"],
            tags=["valid-tag", "", "  \t  ", "another-tag"],
            deliverables=["", "valid_deliverable.md", "   "],
            acceptance_criteria=["Valid criteria", "", "  ", "Another criteria"]
        )

        # Empty strings should be filtered out
        assert metadata.files == ["valid_file.py", "another_file.py"]
        assert metadata.tags == ["valid-tag", "another-tag"]
        assert metadata.deliverables == ["valid_deliverable.md"]
        assert metadata.acceptance_criteria == ["Valid criteria", "Another criteria"]

    def test_confidence_validation_valid_range(self):
        """Test confidence validation for valid values (1-5)."""
        for confidence in [1, 2, 3, 4, 5]:
            metadata = TodoMetadata(confidence=confidence)
            assert metadata.confidence == confidence

    def test_confidence_validation_invalid_range(self):
        """Test confidence validation rejects invalid values."""
        with pytest.raises(ValidationError, match="Input should be greater than or equal to 1"):
            TodoMetadata(confidence=0)

        with pytest.raises(ValidationError, match="Input should be less than or equal to 5"):
            TodoMetadata(confidence=6)

        with pytest.raises(ValidationError, match="Input should be greater than or equal to 1"):
            TodoMetadata(confidence=-1)

    def test_complexity_enum_validation(self):
        """Test complexity enum validation."""
        valid_complexities = ["Low", "Medium", "High", "Complex"]

        for complexity in valid_complexities:
            metadata = TodoMetadata(complexity=complexity)
            assert metadata.complexity == ComplexityLevel(complexity)

        # Test invalid complexity
        with pytest.raises(ValidationError):
            TodoMetadata(complexity="Invalid")


class TestTodoSchema:
    """Test TodoSchema validation."""

    def test_minimal_valid_todo(self):
        """Test minimal valid todo with required fields only."""
        todo_data = {
            "id": str(uuid4()),
            "description": "Test todo",
            "project": "test-project",
            "created_at": int(time.time())
        }

        todo = TodoSchema(**todo_data)

        assert todo.id == todo_data["id"]
        assert todo.description == "Test todo"
        assert todo.project == "test-project"
        assert todo.priority == PriorityLevel.MEDIUM  # default
        assert todo.status == StatusLevel.PENDING  # default
        assert todo.target_agent == "user"  # default
        assert todo.created_at == todo_data["created_at"]
        assert todo.metadata is not None  # default_factory=dict

    def test_full_valid_todo(self):
        """Test todo with all fields populated."""
        created_time = int(time.time())
        completed_time = created_time + 3600

        metadata = TodoMetadata(
            files=["test.py"],
            tags=["testing"],
            complexity="High",
            confidence=5
        )

        todo_data = {
            "id": str(uuid4()),
            "description": "Complete integration test",
            "project": "omnispindle",
            "priority": "High",
            "status": "completed",
            "target_agent": "claude",
            "created_at": created_time,
            "updated_at": completed_time,
            "completed_at": completed_time,
            "completed_by": "test@example.com",
            "completion_comment": "All tests passed",
            "duration_sec": 3600,
            "metadata": metadata
        }

        todo = TodoSchema(**todo_data)

        assert todo.id == todo_data["id"]
        assert todo.description == "Complete integration test"
        assert todo.project == "omnispindle"
        assert todo.priority == PriorityLevel.HIGH
        assert todo.status == StatusLevel.COMPLETED
        assert todo.target_agent == "claude"
        assert todo.created_at == created_time
        assert todo.updated_at == completed_time
        assert todo.completed_at == completed_time
        assert todo.completed_by == "test@example.com"
        assert todo.completion_comment == "All tests passed"
        assert todo.duration_sec == 3600
        assert todo.metadata == metadata

    def test_description_validation(self):
        """Test description validation."""
        base_todo = {
            "id": str(uuid4()),
            "project": "test-project",
            "created_at": int(time.time())
        }

        # Empty description should fail
        with pytest.raises(ValidationError, match="description cannot be empty"):
            TodoSchema(**{**base_todo, "description": ""})

        with pytest.raises(ValidationError, match="description cannot be empty"):
            TodoSchema(**{**base_todo, "description": "   "})

        # Valid description should work
        todo = TodoSchema(**{**base_todo, "description": "  Valid description  "})
        assert todo.description == "Valid description"  # stripped

    def test_project_validation(self):
        """Test project validation and normalization."""
        base_todo = {
            "id": str(uuid4()),
            "description": "Test todo",
            "created_at": int(time.time())
        }

        # Empty project should fail
        with pytest.raises(ValidationError, match="project cannot be empty"):
            TodoSchema(**{**base_todo, "project": ""})

        with pytest.raises(ValidationError, match="project cannot be empty"):
            TodoSchema(**{**base_todo, "project": "   "})

        # Project should be normalized to lowercase
        todo = TodoSchema(**{**base_todo, "project": "  TEST-PROJECT  "})
        assert todo.project == "test-project"

    def test_enum_validation(self):
        """Test enum field validation."""
        base_todo = {
            "id": str(uuid4()),
            "description": "Test todo",
            "project": "test-project",
            "created_at": int(time.time())
        }

        # Valid priority values
        valid_priorities = ["Critical", "High", "Medium", "Low"]
        for priority in valid_priorities:
            todo = TodoSchema(**{**base_todo, "priority": priority})
            assert todo.priority == PriorityLevel(priority)

        # Invalid priority should fail
        with pytest.raises(ValidationError):
            TodoSchema(**{**base_todo, "priority": "Invalid"})

        # Valid status values
        valid_statuses = ["pending", "in_progress", "completed", "blocked"]
        for status in valid_statuses:
            todo = TodoSchema(**{**base_todo, "status": status})
            assert todo.status == StatusLevel(status)

        # Invalid status should fail
        with pytest.raises(ValidationError):
            TodoSchema(**{**base_todo, "status": "invalid"})


class TestTodoCreateRequest:
    """Test TodoCreateRequest schema."""

    def test_minimal_create_request(self):
        """Test minimal create request."""
        request = TodoCreateRequest(
            description="New todo",
            project="test-project"
        )

        assert request.description == "New todo"
        assert request.project == "test-project"
        assert request.priority == PriorityLevel.MEDIUM  # default
        assert request.target_agent == "user"  # default
        assert request.metadata is None  # default

    def test_full_create_request(self):
        """Test create request with all fields."""
        metadata = TodoMetadata(tags=["feature"], complexity="Medium")

        request = TodoCreateRequest(
            description="Complex todo",
            project="omnispindle",
            priority="High",
            target_agent="claude",
            metadata=metadata
        )

        assert request.description == "Complex todo"
        assert request.project == "omnispindle"
        assert request.priority == PriorityLevel.HIGH
        assert request.target_agent == "claude"
        assert request.metadata == metadata


class TestTodoUpdateRequest:
    """Test TodoUpdateRequest schema."""

    def test_empty_update_request(self):
        """Test update request with no fields (all optional)."""
        request = TodoUpdateRequest()

        assert request.description is None
        assert request.project is None
        assert request.priority is None
        assert request.status is None
        assert request.target_agent is None
        assert request.metadata is None

    def test_partial_update_request(self):
        """Test update request with some fields."""
        metadata = TodoMetadata(files=["updated.py"])

        request = TodoUpdateRequest(
            description="Updated description",
            status="completed",
            metadata=metadata,
            completion_comment="Done!"
        )

        assert request.description == "Updated description"
        assert request.project is None  # not updated
        assert request.status == StatusLevel.COMPLETED
        assert request.metadata == metadata
        assert request.completion_comment == "Done!"


class TestValidationFunctions:
    """Test standalone validation functions."""

    def test_validate_todo_metadata_function(self):
        """Test validate_todo_metadata function."""
        # Valid metadata
        metadata_dict = {
            "files": ["test.py"],
            "tags": ["testing"],
            "complexity": "Medium",
            "confidence": 3
        }

        metadata = validate_todo_metadata(metadata_dict)
        assert isinstance(metadata, TodoMetadata)
        assert metadata.files == ["test.py"]
        assert metadata.tags == ["testing"]
        assert metadata.complexity == ComplexityLevel.MEDIUM
        assert metadata.confidence == 3

        # Invalid metadata should raise ValidationError
        with pytest.raises(ValidationError):
            validate_todo_metadata({"confidence": 10})  # invalid range

    def test_validate_todo_function(self):
        """Test validate_todo function."""
        # Valid todo
        todo_dict = {
            "id": str(uuid4()),
            "description": "Test todo",
            "project": "test-project",
            "created_at": int(time.time()),
            "metadata": {
                "tags": ["testing"],
                "complexity": "Low"
            }
        }

        todo = validate_todo(todo_dict)
        assert isinstance(todo, TodoSchema)
        assert todo.description == "Test todo"
        assert todo.project == "test-project"
        assert isinstance(todo.metadata, TodoMetadata)

        # Invalid todo should raise ValidationError
        with pytest.raises(ValidationError):
            validate_todo({"id": str(uuid4())})  # missing required fields


class TestBackwardCompatibility:
    """Test backward compatibility with legacy metadata formats."""

    def test_legacy_metadata_fields(self):
        """Test that legacy fields are still supported."""
        metadata = TodoMetadata(
            completed_by="legacy@example.com",
            completion_comment="Legacy completion"
        )

        assert metadata.completed_by == "legacy@example.com"
        assert metadata.completion_comment == "Legacy completion"

    def test_mixed_legacy_and_new_fields(self):
        """Test mixing legacy and new metadata fields."""
        metadata = TodoMetadata(
            # New standardized fields
            files=["new_file.py"],
            tags=["new-feature"],
            complexity="High",
            confidence=4,
            # Legacy fields
            completed_by="user@example.com",
            completion_comment="Mixed metadata test"
        )

        assert metadata.files == ["new_file.py"]
        assert metadata.tags == ["new-feature"]
        assert metadata.complexity == ComplexityLevel.HIGH
        assert metadata.confidence == 4
        assert metadata.completed_by == "user@example.com"
        assert metadata.completion_comment == "Mixed metadata test"

    def test_custom_fields_preserve_arbitrary_data(self):
        """Test that custom fields preserve arbitrary legacy data."""
        custom_data = {
            "legacy_field": "some_value",
            "nested_legacy": {
                "sub_field": "sub_value",
                "numbers": [1, 2, 3]
            },
            "random_metadata": True
        }

        metadata = TodoMetadata(custom=custom_data)
        assert metadata.custom == custom_data


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_maximum_description_length(self):
        """Test description length validation."""
        # Exactly 500 characters should work
        long_description = "a" * 500
        todo = TodoSchema(
            id=str(uuid4()),
            description=long_description,
            project="test",
            created_at=int(time.time())
        )
        assert len(todo.description) == 500

        # 501 characters should fail
        with pytest.raises(ValidationError):
            TodoSchema(
                id=str(uuid4()),
                description="a" * 501,
                project="test",
                created_at=int(time.time())
            )

    def test_unicode_support(self):
        """Test Unicode support in text fields."""
        unicode_description = "测试 Unicode 支持 🚀 émojis and special chars"

        todo = TodoSchema(
            id=str(uuid4()),
            description=unicode_description,
            project="unicode-test",
            created_at=int(time.time())
        )

        assert todo.description == unicode_description
        assert todo.project == "unicode-test"

    def test_very_large_metadata(self):
        """Test handling of large metadata objects."""
        large_files_list = [f"file_{i}.py" for i in range(100)]
        large_tags_list = [f"tag_{i}" for i in range(50)]
        large_criteria_list = [f"Criterion {i} must be satisfied" for i in range(20)]

        metadata = TodoMetadata(
            files=large_files_list,
            tags=large_tags_list,
            acceptance_criteria=large_criteria_list
        )

        assert len(metadata.files) == 100
        assert len(metadata.tags) == 50
        assert len(metadata.acceptance_criteria) == 20

    def test_none_vs_empty_arrays(self):
        """Test distinction between None and empty arrays."""
        # None should remain None
        metadata_none = TodoMetadata(files=None, tags=None)
        assert metadata_none.files is None
        assert metadata_none.tags is None

        # Empty arrays should remain empty arrays
        metadata_empty = TodoMetadata(files=[], tags=[])
        assert metadata_empty.files == []
        assert metadata_empty.tags == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])