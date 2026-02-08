"""Tests for robust YAML parsing and error handling."""

import pytest
from waverunner.agent import extract_yaml_from_response


def test_malformed_yaml_with_extra_fields():
    """Should handle LLM responses with invalid extra fields gracefully."""
    # This is what caused the user's error - LLM added an ASK field
    response = """
Here's the plan:

```yaml
tasks:
  - id: "user-decision-blocker"
    title: "Wait for user decision"
    ASK: "What would you like to prioritize next?"
    complexity: trivial
```
"""
    # Should either skip the malformed task or raise clear error
    with pytest.raises(Exception) as exc_info:
        extract_yaml_from_response(response)

    assert "YAML" in str(exc_info.value) or "parse" in str(exc_info.value).lower()


def test_yaml_with_unbalanced_quotes():
    """Should handle YAML with quote issues."""
    response = """
```yaml
tasks:
  - id: test-task
    title: "Task with unbalanced quote
    complexity: small
```
"""
    with pytest.raises(Exception):
        extract_yaml_from_response(response)


def test_yaml_with_clarifications_in_wrong_place():
    """Should handle clarifications that break task structure."""
    response = """
```yaml
tasks:
  - id: task-1
    title: "Do something"
    complexity: small

clarifications_needed:
  - "What database should we use?"

risks:
  - "Unknown requirements"
```
"""
    # This should parse successfully - clarifications_needed is valid at root level
    result = extract_yaml_from_response(response)
    assert "clarifications_needed" in result
    assert isinstance(result["clarifications_needed"], list)


def test_empty_yaml_response():
    """Should handle LLM responses with no YAML."""
    response = "I don't have enough information to create a plan."

    with pytest.raises(ValueError, match="No YAML"):
        extract_yaml_from_response(response)


def test_yaml_parsing_gives_helpful_error():
    """YAML parsing errors should include context about what failed."""
    response = """
```yaml
tasks:
  - id: task-1
    title: "Test"
    this_is_invalid_indentation
      complexity: small
```
"""
    with pytest.raises(Exception) as exc_info:
        extract_yaml_from_response(response)

    error_msg = str(exc_info.value)
    # Should mention YAML and ideally give line number
    assert "YAML" in error_msg or "parse" in error_msg.lower()
