"""Tests for LLM provider abstraction."""

import pytest
from waverunner.providers import LLMProvider, MockLLMProvider, get_provider, ClaudeCodeProvider


def test_mock_provider_basic():
    """MockLLMProvider should return canned responses."""
    provider = MockLLMProvider(responses={
        "planning": "```yaml\ntasks: []\n```",
    })

    response = provider.run("This is a planning request")
    assert "yaml" in response
    assert provider.call_count == 1
    assert "planning" in provider.last_prompt


def test_mock_provider_default_response():
    """MockLLMProvider should return default if no match."""
    provider = MockLLMProvider()

    response = provider.run("Random prompt")
    assert "mock-task-1" in response
    assert provider.call_count == 1


def test_mock_provider_tracks_calls():
    """MockLLMProvider should track call history."""
    provider = MockLLMProvider()

    provider.run("First prompt", system_prompt="System 1")
    assert provider.call_count == 1
    assert provider.last_prompt == "First prompt"
    assert provider.last_system_prompt == "System 1"

    provider.run("Second prompt", system_prompt="System 2")
    assert provider.call_count == 2
    assert provider.last_prompt == "Second prompt"
    assert provider.last_system_prompt == "System 2"


def test_mock_provider_multiple_matches():
    """MockLLMProvider should match on substring."""
    provider = MockLLMProvider(responses={
        "sprint": "Sprint response",
        "kanban": "Kanban response",
    })

    assert "Sprint" in provider.run("Create a sprint plan")
    assert "Kanban" in provider.run("Create a kanban backlog")


def test_get_provider_mock():
    """get_provider should return MockLLMProvider for 'mock'."""
    provider = get_provider("mock")
    assert isinstance(provider, MockLLMProvider)


def test_get_provider_claude_code():
    """get_provider should return ClaudeCodeProvider for 'claude-code'."""
    provider = get_provider("claude-code")
    assert isinstance(provider, ClaudeCodeProvider)


def test_get_provider_invalid():
    """get_provider should raise error for unknown provider."""
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("nonexistent")


def test_provider_interface():
    """All providers should implement LLMProvider interface."""
    providers = [
        MockLLMProvider(),
        ClaudeCodeProvider(),
    ]

    for provider in providers:
        assert isinstance(provider, LLMProvider)
        assert hasattr(provider, "run")
        assert callable(provider.run)
