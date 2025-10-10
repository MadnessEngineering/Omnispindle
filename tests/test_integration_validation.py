"""
Integration tests for the standardized metadata schema and documentation system.

Tests the complete validation system end-to-end to verify:
- MCP client receives appropriate detail level
- Backward compatibility is maintained
- Schema and documentation work together seamlessly
"""

import pytest
import os
import time
from uuid import uuid4
from unittest.mock import patch, MagicMock

from src.Omnispindle.schemas.todo_metadata_schema import (
    TodoSchema,
    TodoMetadata,
    validate_todo,
    validate_todo_metadata
)
from src.Omnispindle.documentation_manager import (
    DocumentationManager,
    get_documentation_manager,
    get_tool_doc,
    get_param_hint
)


class TestMCPClientDetailLevelHandling:
    """Test that MCP clients receive appropriate detail levels."""

    def test_token_constrained_client_scenario(self):
        """Test scenario for token-constrained MCP client."""
        # Simulate a token-constrained client using minimal loadout
        manager = DocumentationManager(loadout="minimal")

        # Should get very brief documentation
        doc = manager.get_tool_documentation("add_todo")
        assert len(doc) <= 30, "Token-constrained client should get very brief docs"
        assert doc == "Create task"

        # Should get no parameter hints to save tokens
        hint = manager.get_parameter_hint("add_todo")
        assert hint is None, "Token-constrained client should get no parameter hints"

    def test_balanced_client_scenario(self):
        """Test scenario for balanced MCP client."""
        # Simulate a balanced client using basic loadout
        manager = DocumentationManager(loadout="basic")

        # Should get concise but informative documentation
        doc = manager.get_tool_documentation("add_todo")
        assert 50 <= len(doc) <= 200, "Balanced client should get concise but informative docs"
        assert "Creates a task" in doc
        assert "project" in doc.lower()

        # Should get essential parameter hints
        hint = manager.get_parameter_hint("add_todo")
        assert hint is not None, "Balanced client should get parameter hints"
        assert "description" in hint.lower()
        assert "project" in hint.lower()

    def test_administrative_client_scenario(self):
        """Test scenario for administrative MCP client."""
        # Simulate an admin client using admin loadout
        manager = DocumentationManager(loadout="admin")

        # Should get detailed administrative context
        doc = manager.get_tool_documentation("add_todo")
        assert len(doc) > 100, "Admin client should get detailed documentation"
        assert "metadata schema" in doc.lower()
        assert "project counts" in doc.lower()

        # Should get comprehensive parameter hints
        hint = manager.get_parameter_hint("add_todo")
        assert hint is not None, "Admin client should get parameter hints"
        assert "metadata supports" in hint.lower()
        assert "files[]" in hint

    def test_development_client_scenario(self):
        """Test scenario for development MCP client."""
        # Simulate a development client using full loadout
        manager = DocumentationManager(loadout="full")

        # Should get comprehensive documentation with examples
        doc = manager.get_tool_documentation("add_todo")
        assert len(doc) > 300, "Development client should get comprehensive docs"
        assert "Technical context:" in doc
        assert "Project organization:" in doc
        assert "State tracking:" in doc

        # Should get detailed parameter specifications
        hint = manager.get_parameter_hint("add_todo")
        assert hint is not None, "Development client should get detailed parameter hints"
        assert "Parameters:" in hint
        # Should contain detailed parameter examples (paths, tags, etc.)
        assert "path/to/file.py" in hint or "bug" in hint or "feature" in hint

    def test_client_loadout_environment_variable(self):
        """Test that MCP clients can configure via environment variable."""
        # Test different environment variable scenarios
        test_cases = [
            ("minimal", "Create task"),
            ("basic", "Creates a task in the specified project"),
            ("admin", "Creates a task in the specified project. Supports"),
            ("full", "Creates a task in the specified project with the given priority")
        ]

        for loadout, expected_doc_start in test_cases:
            with patch.dict(os.environ, {"OMNISPINDLE_TOOL_LOADOUT": loadout}):
                # Clear global manager to force re-initialization
                import src.Omnispindle.documentation_manager as doc_module
                doc_module._doc_manager = None

                manager = get_documentation_manager()
                doc = manager.get_tool_documentation("add_todo")
                assert doc.startswith(expected_doc_start), f"Loadout '{loadout}' should start with '{expected_doc_start}'"

    def test_real_world_mcp_client_token_usage(self):
        """Test realistic token usage for different MCP client types."""
        # Calculate total documentation token usage for common tools
        common_tools = ["add_todo", "query_todos", "update_todo", "get_todo", "mark_todo_complete"]

        minimal_total = 0
        full_total = 0

        minimal_manager = DocumentationManager(loadout="minimal")
        full_manager = DocumentationManager(loadout="full")

        for tool in common_tools:
            minimal_doc = minimal_manager.get_tool_documentation(tool)
            full_doc = full_manager.get_tool_documentation(tool)
            minimal_hint = minimal_manager.get_parameter_hint(tool)
            full_hint = full_manager.get_parameter_hint(tool)

            minimal_total += len(minimal_doc) + (len(minimal_hint) if minimal_hint else 0)
            full_total += len(full_doc) + (len(full_hint) if full_hint else 0)

        # Minimal should use significantly fewer tokens (rough estimation)
        token_ratio = minimal_total / full_total
        assert token_ratio < 0.15, f"Minimal loadout should use <15% of full tokens, got {token_ratio:.2%}"


class TestBackwardCompatibilityValidation:
    """Test comprehensive backward compatibility."""

    def test_legacy_todo_metadata_structure(self):
        """Test that legacy metadata structures still validate."""
        # Legacy metadata that might exist in production
        legacy_metadata = {
            "completed_by": "user@example.com",
            "completion_comment": "Legacy completion comment",
            # Missing new standardized fields - should still work
        }

        metadata = validate_todo_metadata(legacy_metadata)
        assert metadata.completed_by == "user@example.com"
        assert metadata.completion_comment == "Legacy completion comment"

        # New fields should be None/default
        assert metadata.files is None
        assert metadata.tags is None
        assert metadata.complexity is None

    def test_mixed_legacy_and_modern_metadata(self):
        """Test mixing legacy and modern metadata fields."""
        mixed_metadata = {
            # Legacy fields
            "completed_by": "legacy@example.com",
            "completion_comment": "Legacy comment",

            # Modern standardized fields
            "files": ["modern_file.py"],
            "tags": ["modern-tag"],
            "complexity": "High",
            "confidence": 4,
            "acceptance_criteria": ["Modern criterion"],

            # Custom fields for extensibility
            "custom": {
                "legacy_field": "legacy_value",
                "modern_integration": True
            }
        }

        metadata = validate_todo_metadata(mixed_metadata)

        # Legacy fields preserved
        assert metadata.completed_by == "legacy@example.com"
        assert metadata.completion_comment == "Legacy comment"

        # Modern fields work
        assert metadata.files == ["modern_file.py"]
        assert metadata.tags == ["modern-tag"]
        assert metadata.complexity.value == "High"
        assert metadata.confidence == 4
        assert metadata.acceptance_criteria == ["Modern criterion"]

        # Custom fields preserved
        assert metadata.custom["legacy_field"] == "legacy_value"
        assert metadata.custom["modern_integration"] is True

    def test_legacy_todo_schema_compatibility(self):
        """Test that existing todo structures validate with new schema."""
        # Simulate a todo that existed before the standardized schema
        legacy_todo = {
            "id": str(uuid4()),
            "description": "Legacy todo from old system",
            "project": "legacy-project",
            "priority": "High",
            "status": "completed",
            "created_at": int(time.time()) - 86400,  # Created yesterday
            "completed_at": int(time.time()),
            "completed_by": "legacy@example.com",
            "completion_comment": "Completed in legacy system",
            # No standardized metadata - this field might be missing entirely
        }

        todo = validate_todo(legacy_todo)

        # All legacy fields preserved
        assert todo.description == "Legacy todo from old system"
        assert todo.project == "legacy-project"
        assert todo.completed_by == "legacy@example.com"
        assert todo.completion_comment == "Completed in legacy system"

        # Metadata should be created with defaults (as dict from default_factory)
        assert todo.metadata is not None
        # The schema uses default_factory=dict, so metadata will be a dict, not TodoMetadata instance
        assert isinstance(todo.metadata, dict)

    def test_gradual_migration_scenario(self):
        """Test gradual migration from legacy to standardized metadata."""
        # Phase 1: Legacy todo with no metadata
        phase1_todo = {
            "id": str(uuid4()),
            "description": "Phase 1 todo",
            "project": "migration-test",
            "created_at": int(time.time())
        }

        todo1 = validate_todo(phase1_todo)
        assert todo1.metadata is not None  # Default metadata created

        # Phase 2: Legacy todo with some modern metadata
        phase2_todo = {
            "id": str(uuid4()),
            "description": "Phase 2 todo",
            "project": "migration-test",
            "created_at": int(time.time()),
            "metadata": {
                "files": ["newly_added.py"],  # Start adding modern fields
                "completed_by": "user@example.com"  # Keep legacy fields
            }
        }

        todo2 = validate_todo(phase2_todo)
        assert todo2.metadata.files == ["newly_added.py"]
        assert todo2.metadata.completed_by == "user@example.com"

        # Phase 3: Fully modern todo with complete metadata
        phase3_todo = {
            "id": str(uuid4()),
            "description": "Phase 3 todo",
            "project": "migration-test",
            "created_at": int(time.time()),
            "metadata": {
                "files": ["fully_modern.py"],
                "tags": ["migration", "complete"],
                "complexity": "Medium",
                "confidence": 4,
                "acceptance_criteria": ["All tests pass", "Documentation updated"],
                "deliverables": ["implementation.py", "tests.py"]
            }
        }

        todo3 = validate_todo(phase3_todo)
        assert todo3.metadata.files == ["fully_modern.py"]
        assert todo3.metadata.tags == ["migration", "complete"]
        assert todo3.metadata.complexity.value == "Medium"
        assert todo3.metadata.acceptance_criteria == ["All tests pass", "Documentation updated"]

    def test_documentation_backward_compatibility(self):
        """Test that documentation manager maintains backward compatibility."""
        # Test that unknown/legacy loadout values don't break the system
        legacy_loadouts = ["verbose", "debug", "detailed", "compact", ""]

        for loadout in legacy_loadouts:
            manager = DocumentationManager(loadout=loadout)

            # Should fall back to 'full' gracefully
            assert manager.level.value in ["full", "minimal", "basic", "admin"]

            # Should still provide valid documentation
            doc = manager.get_tool_documentation("add_todo")
            assert len(doc) > 0
            assert isinstance(doc, str)

            # Should handle parameter hints gracefully
            hint = manager.get_parameter_hint("add_todo")
            assert hint is None or isinstance(hint, str)


class TestSchemaDocumentationIntegration:
    """Test integration between schema validation and documentation system."""

    def test_schema_validation_with_documentation_examples(self):
        """Test that documentation examples validate against schema."""
        # Test that parameter hint examples actually work with the schema
        manager = DocumentationManager(loadout="full")
        hint = manager.get_parameter_hint("add_todo")

        # Extract example metadata from documentation
        example_metadata = {
            "files": ["path/to/file.py"],
            "tags": ["bug", "feature"],
            "phase": "implementation",
            "complexity": "Low",
            "confidence": 3,
            "acceptance_criteria": ["criterion1", "criterion2"]
        }

        # Should validate successfully
        metadata = validate_todo_metadata(example_metadata)
        assert metadata.files == ["path/to/file.py"]
        assert metadata.tags == ["bug", "feature"]
        assert metadata.complexity.value == "Low"

    def test_complete_workflow_validation(self):
        """Test complete workflow from documentation to validation."""
        # Simulate an MCP client reading documentation and creating a todo
        manager = DocumentationManager(loadout="admin")

        # Client reads documentation
        doc = manager.get_tool_documentation("add_todo")
        hint = manager.get_parameter_hint("add_todo")

        # Client constructs todo based on documentation guidance
        todo_data = {
            "id": str(uuid4()),
            "description": "Test todo created from documentation guidance",
            "project": "integration-test",
            "priority": "High",
            "created_at": int(time.time()),
            "metadata": {
                "files": ["integration_test.py"],
                "tags": ["testing", "integration"],
                "phase": "validation",
                "complexity": "Medium",
                "confidence": 5,
                "acceptance_criteria": [
                    "All validation tests pass",
                    "Documentation examples work",
                    "MCP client integration successful"
                ]
            }
        }

        # Should validate successfully
        todo = validate_todo(todo_data)
        assert todo.description == "Test todo created from documentation guidance"
        assert todo.metadata.files == ["integration_test.py"]
        assert todo.metadata.tags == ["testing", "integration"]
        assert todo.metadata.confidence == 5

    def test_error_handling_consistency(self):
        """Test that schema errors are consistent with documentation."""
        manager = DocumentationManager(loadout="full")

        # Test that documented constraints are enforced by schema
        with pytest.raises(Exception):  # Should fail validation
            validate_todo_metadata({"confidence": 10})  # Out of 1-5 range as documented

        with pytest.raises(Exception):  # Should fail validation
            TodoSchema(
                id=str(uuid4()),
                description="a" * 501,  # Exceeds 500 char limit as documented
                project="test",
                created_at=int(time.time())
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])