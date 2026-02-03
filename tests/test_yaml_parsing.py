"""Tests for YAML response parsing."""

import pytest
from waverunner.agent import extract_yaml_from_response


def test_extract_yaml_from_code_block():
    """Should extract YAML from ```yaml code block."""
    response = """Here's the plan:

```yaml
tasks:
  - id: "task-1"
    title: "Test task"
```

That's the plan!"""

    result = extract_yaml_from_response(response)
    assert isinstance(result, dict)
    assert "tasks" in result
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["id"] == "task-1"


def test_extract_yaml_from_generic_code_block():
    """Should extract YAML from generic ``` code block."""
    response = """```
tasks:
  - id: "task-1"
    title: "Test"
```"""

    result = extract_yaml_from_response(response)
    assert isinstance(result, dict)
    assert "tasks" in result


def test_extract_yaml_from_plain_text():
    """Should parse plain YAML without code blocks."""
    response = """tasks:
  - id: "task-1"
    title: "Test"
"""

    result = extract_yaml_from_response(response)
    assert isinstance(result, dict)
    assert "tasks" in result


def test_authentication_error_detection():
    """Should detect and raise error for auth failures."""
    response = "Invalid API key · Please run /login"

    with pytest.raises(ValueError, match="authentication failed"):
        extract_yaml_from_response(response)


def test_non_dict_yaml_error():
    """Should raise error if YAML parses to non-dict."""
    response = "just a plain string"

    with pytest.raises(ValueError, match="Expected YAML dict"):
        extract_yaml_from_response(response)


def test_list_yaml_error():
    """Should raise error if YAML is a list."""
    response = """```yaml
- item1
- item2
```"""

    with pytest.raises(ValueError, match="Expected YAML dict"):
        extract_yaml_from_response(response)


def test_clarifications_needed():
    """Should parse clarifications_needed field."""
    response = """```yaml
clarifications_needed:
  - "Which codebase?"
  - "What's the scope?"
```"""

    result = extract_yaml_from_response(response)
    assert "clarifications_needed" in result
    assert len(result["clarifications_needed"]) == 2


def test_complete_plan_yaml():
    """Should parse a complete planning response."""
    response = """```yaml
risks:
  - "Unknown codebase"
assumptions:
  - "Python 3.10+"
out_of_scope:
  - "Performance optimization"
definition_of_done:
  - "All tests pass"
tasks:
  - id: "discover-1"
    title: "Explore codebase"
    description: "Read the code"
    complexity: small
    priority: high
    acceptance_criteria:
      - "Understand structure"
    dependencies: []
  - id: "implement-1"
    title: "Write code"
    description: "Implement feature"
    complexity: medium
    priority: medium
    acceptance_criteria:
      - "Feature works"
    dependencies:
      - "discover-1"
```"""

    result = extract_yaml_from_response(response)
    assert "risks" in result
    assert "assumptions" in result
    assert "tasks" in result
    assert len(result["tasks"]) == 2
    assert result["tasks"][1]["dependencies"] == ["discover-1"]
