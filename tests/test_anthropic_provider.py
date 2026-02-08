"""Tests for Anthropic API provider."""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from waverunner.providers import get_provider


def test_anthropic_provider_requires_api_key():
    """AnthropicAPIProvider should fail gracefully if no API key."""
    # Clear env var if set
    original_key = os.environ.get("ANTHROPIC_API_KEY")
    if "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]

    try:
        # Should raise error during initialization if no API key
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            provider = get_provider("anthropic-api")
    finally:
        # Restore original key
        if original_key:
            os.environ["ANTHROPIC_API_KEY"] = original_key


def test_anthropic_provider_uses_env_api_key():
    """AnthropicAPIProvider should read API key from environment."""
    # Mock the anthropic SDK
    with patch("anthropic.Anthropic") as mock_anthropic_class:
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock response
        mock_message = Mock()
        mock_message.content = [Mock(text="Test response")]
        mock_client.messages.create.return_value = mock_message

        # Set fake API key
        os.environ["ANTHROPIC_API_KEY"] = "sk-test-fake-key-12345"

        try:
            provider = get_provider("anthropic-api")
            response = provider.run("Test prompt")

            # Should have called Anthropic() constructor (reads env var)
            mock_anthropic_class.assert_called_once()

            # Should have called messages.create
            assert mock_client.messages.create.called
            assert response == "Test response"
        finally:
            # Clean up
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]


def test_anthropic_provider_sends_structured_messages():
    """AnthropicAPIProvider should send messages as structured array."""
    with patch("anthropic.Anthropic") as mock_anthropic_class:
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = [Mock(text="Response")]
        mock_client.messages.create.return_value = mock_message

        os.environ["ANTHROPIC_API_KEY"] = "sk-test-key"

        try:
            provider = get_provider("anthropic-api")
            provider.run(
                prompt="User prompt here",
                system_prompt="System prompt here"
            )

            # Check that messages.create was called with structured messages
            call_kwargs = mock_client.messages.create.call_args[1]

            # Should have system parameter (list with cache_control)
            assert "system" in call_kwargs
            assert isinstance(call_kwargs["system"], list)
            system_block = call_kwargs["system"][0]
            assert system_block["type"] == "text"
            assert system_block["text"] == "System prompt here"
            assert "cache_control" in system_block

            # Should have messages parameter (list of message dicts)
            assert "messages" in call_kwargs
            assert isinstance(call_kwargs["messages"], list)
            assert len(call_kwargs["messages"]) > 0
            user_msg = call_kwargs["messages"][0]
            assert user_msg["role"] == "user"
            assert user_msg["content"] == "User prompt here"

        finally:
            del os.environ["ANTHROPIC_API_KEY"]


def test_anthropic_provider_supports_timeout():
    """AnthropicAPIProvider should respect timeout parameter."""
    with patch("anthropic.Anthropic") as mock_anthropic_class:
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = [Mock(text="Response")]
        mock_client.messages.create.return_value = mock_message

        os.environ["ANTHROPIC_API_KEY"] = "sk-test-key"

        try:
            provider = get_provider("anthropic-api")
            provider.run("Test", timeout=120)

            # Should pass timeout to API call
            call_kwargs = mock_client.messages.create.call_args[1]
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == 120

        finally:
            del os.environ["ANTHROPIC_API_KEY"]


def test_anthropic_provider_handles_api_errors():
    """AnthropicAPIProvider should handle API errors gracefully."""
    with patch("anthropic.Anthropic") as mock_anthropic_class:
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Simulate API error
        mock_client.messages.create.side_effect = Exception("API rate limit exceeded")

        os.environ["ANTHROPIC_API_KEY"] = "sk-test-key"

        try:
            provider = get_provider("anthropic-api")

            with pytest.raises(Exception, match="API rate limit"):
                provider.run("Test prompt")

        finally:
            del os.environ["ANTHROPIC_API_KEY"]


def test_anthropic_provider_in_provider_list():
    """get_provider should return AnthropicAPIProvider for 'anthropic-api'."""
    with patch("anthropic.Anthropic"):
        os.environ["ANTHROPIC_API_KEY"] = "sk-test-key"
        try:
            provider = get_provider("anthropic-api")
            from waverunner.providers import AnthropicAPIProvider
            assert isinstance(provider, AnthropicAPIProvider)
        finally:
            del os.environ["ANTHROPIC_API_KEY"]


def test_anthropic_provider_no_mcps_warning():
    """AnthropicAPIProvider should warn if MCPs are requested (not yet supported)."""
    with patch("anthropic.Anthropic") as mock_anthropic_class:
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = [Mock(text="Response")]
        mock_client.messages.create.return_value = mock_message

        os.environ["ANTHROPIC_API_KEY"] = "sk-test-key"

        try:
            provider = get_provider("anthropic-api")

            # Should handle mcps parameter gracefully (even if not implemented yet)
            response = provider.run("Test", mcps=["config.json"])
            assert response == "Response"

        finally:
            del os.environ["ANTHROPIC_API_KEY"]
