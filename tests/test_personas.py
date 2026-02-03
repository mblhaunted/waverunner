"""
Tests for the multi-agent persona system.
"""

import pytest
from waverunner.personas import get_personas, get_sprint_personas, get_kanban_personas, Persona
from waverunner.models import Mode


def test_get_sprint_personas():
    """Test that sprint personas are correctly defined."""
    personas = get_sprint_personas()

    assert len(personas) == 6
    names = [p.name for p in personas]
    assert "Tech Lead" in names
    assert "Senior Dev" in names
    assert "Explorer" in names
    assert "Skeptic" in names
    assert "Maverick" in names
    assert "The Reaper" in names

    # Check that each persona has required attributes
    for persona in personas:
        assert persona.name
        assert persona.role
        assert persona.system_prompt
        assert persona.color
        assert len(persona.system_prompt) > 100  # Should be substantial


def test_get_kanban_personas():
    """Test that kanban personas are correctly defined."""
    personas = get_kanban_personas()

    assert len(personas) == 6
    names = [p.name for p in personas]
    assert "Flow Master" in names
    assert "Kaizen Voice" in names
    assert "Quality Gate" in names
    assert "Value Stream" in names
    assert "Maverick" in names
    assert "The Reaper" in names

    for persona in personas:
        assert persona.name
        assert persona.role
        assert persona.system_prompt
        assert persona.color


def test_get_personas_sprint_mode():
    """Test that get_personas returns sprint personas for sprint mode."""
    personas = get_personas(Mode.SPRINT)
    assert len(personas) == 6
    assert personas[0].name == "Tech Lead"


def test_get_personas_kanban_mode():
    """Test that get_personas returns kanban personas for kanban mode."""
    personas = get_personas(Mode.KANBAN)
    assert len(personas) == 6
    assert personas[0].name == "Flow Master"


def test_persona_first_is_facilitator():
    """Test that the first persona is always the facilitator."""
    sprint_personas = get_sprint_personas()
    assert sprint_personas[0].role == "facilitator"

    kanban_personas = get_kanban_personas()
    assert kanban_personas[0].role == "facilitator"


def test_maverick_exists_in_both_modes():
    """Test that Maverick persona exists in both modes."""
    sprint_personas = get_sprint_personas()
    kanban_personas = get_kanban_personas()

    sprint_names = [p.name for p in sprint_personas]
    kanban_names = [p.name for p in kanban_personas]

    assert "Maverick" in sprint_names
    assert "Maverick" in kanban_names


def test_facilitator_synthesis_prompt():
    """Test that facilitator synthesis prompt is generated correctly."""
    from waverunner.personas import get_facilitator_synthesis_prompt

    conversation = """
    **Tech Lead**: Let's plan this feature.
    **Senior Dev**: Keep it simple.
    **Maverick**: How will it fail?
    """

    prompt = get_facilitator_synthesis_prompt(
        mode=Mode.SPRINT,
        conversation_history=conversation,
        goal="Add authentication",
        context="Web app needs login",
        mcps=None
    )

    assert "Add authentication" in prompt
    assert "Web app needs login" in prompt
    assert "Tech Lead" in prompt
    assert "Senior Dev" in prompt
    assert "Maverick" in prompt
    assert "yaml" in prompt.lower()


def test_facilitator_synthesis_with_mcps():
    """Test that MCP tools are included in synthesis prompt."""
    from waverunner.personas import get_facilitator_synthesis_prompt

    prompt = get_facilitator_synthesis_prompt(
        mode=Mode.SPRINT,
        conversation_history="Some discussion",
        goal="Test goal",
        context="Test context",
        mcps=["database.json", "api.json"]
    )

    assert "database.json" in prompt
    assert "api.json" in prompt
    assert "MCP" in prompt


def test_reaper_exists_in_both_modes():
    """Test that The Reaper exists in both sprint and kanban modes."""
    sprint_personas = get_sprint_personas()
    kanban_personas = get_kanban_personas()

    sprint_names = [p.name for p in sprint_personas]
    kanban_names = [p.name for p in kanban_personas]

    assert "The Reaper" in sprint_names
    assert "The Reaper" in kanban_names


def test_reaper_is_last():
    """Test that The Reaper speaks last (final authority on safety)."""
    sprint_personas = get_sprint_personas()
    kanban_personas = get_kanban_personas()

    assert sprint_personas[-1].name == "The Reaper"
    assert kanban_personas[-1].name == "The Reaper"


def test_reaper_has_guardian_role():
    """Test that The Reaper has the guardian role."""
    from waverunner.personas import get_reaper

    reaper = get_reaper()
    assert reaper.name == "The Reaper"
    assert reaper.role == "guardian"
    assert reaper.color == "bold white on red"


def test_reaper_system_prompt_includes_safety():
    """Test that The Reaper's prompt includes catastrophe prevention."""
    from waverunner.personas import get_reaper

    reaper = get_reaper()
    prompt = reaper.system_prompt

    # Check for key safety concepts
    assert "CATASTROPHIC" in prompt
    assert "KILL" in prompt or "kill" in prompt
    assert "VETO" in prompt
    assert "safety" in prompt.lower()
    assert "planning" in prompt.lower()  # Should participate in planning


