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


def test_asterisk_alias_in_unquoted_value():
    """Should handle *word at start of unquoted value (YAML alias error)."""
    response = """```yaml
tasks:
  - id: "impl-1"
    title: Core engine
    description: *numpy based waveform generator
    complexity: large
    acceptance_criteria:
      - Works
    dependencies: []
```"""

    result = extract_yaml_from_response(response)
    assert "tasks" in result
    assert result["tasks"][0]["id"] == "impl-1"
    assert "numpy" in result["tasks"][0]["description"]


def test_asterisk_alias_in_list_item():
    """Should handle *word at start of an unquoted list item."""
    response = """```yaml
risks:
  - *critical risk: latency on low-end hardware
assumptions:
  - Python 3.10+
tasks: []
```"""

    result = extract_yaml_from_response(response)
    assert "risks" in result
    assert "assumptions" in result


def test_markdown_bold_in_unquoted_description():
    """Should handle **bold** markdown in unquoted YAML values without crashing."""
    response = """```yaml
tasks:
  - id: "impl-1"
    title: Build the synthesizer
    description: Use **numpy** arrays and **sounddevice** for real audio output
    complexity: medium
    acceptance_criteria:
      - Produces audio
    dependencies: []
```"""

    result = extract_yaml_from_response(response)
    assert "tasks" in result
    assert "numpy" in result["tasks"][0]["description"]


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
