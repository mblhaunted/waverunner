# Custom Models Per Persona

Each persona can use a different LLM model/provider. This is **optional** - by default, all personas use Claude Code.

## How It Works

```python
from waverunner.personas import Persona, get_sprint_personas
from waverunner.providers import get_provider

# Get default personas (all use Claude Code)
personas = get_sprint_personas()

# Or create custom personas with different models
from waverunner.providers import LLMProvider

# Example: Senior Dev uses a different model
class GPT4Provider(LLMProvider):
    def run(self, prompt, system_prompt=None, **kwargs):
        # Your OpenAI GPT-4 integration here
        pass

personas = [
    Persona(
        name="Tech Lead",
        role="facilitator",
        color="cyan",
        system_prompt="...",
        provider=None  # Uses default Claude Code
    ),
    Persona(
        name="Senior Dev",
        role="pragmatist",
        color="green",
        system_prompt="...",
        provider=GPT4Provider()  # Uses GPT-4
    ),
    Persona(
        name="Maverick",
        role="provocateur",
        color="magenta",
        system_prompt="...",
        provider=get_provider("claude-opus")  # Could use Opus via API
    ),
]
```

## Provider Types

Currently implemented:
- `claude-code` (default) - Claude Code CLI
- `mock` - For testing

Easy to add:
- OpenAI API provider
- Anthropic API provider (Claude Opus, Sonnet, Haiku)
- Local models (Ollama, LM Studio)
- Any other LLM API

## Use Cases

**Cost Optimization:**
- Use Haiku for simple personas (Explorer, Skeptic)
- Use Opus for complex personas (Tech Lead, Senior Dev)

**Specialization:**
- Code-focused models for Senior Dev
- Fast models for Maverick (just needs to challenge, not implement)
- Research-focused models for Explorer

**Experimentation:**
- Mix Claude and GPT-4 to see different perspectives
- Compare performance across models
- A/B test different provider configurations

## Default Behavior

**Without custom providers:**
```python
# All personas use Claude Code (current default)
personas = get_sprint_personas()
```

**With custom providers:**
```python
# Only Maverick uses different model, rest use default
personas = get_sprint_personas()
personas[4].provider = CustomProvider()  # Maverick is index 4
```

## Backward Compatibility

✅ All existing code works unchanged
✅ No breaking changes
✅ Opt-in feature - only set `provider` if you want custom models
✅ `provider=None` means "use global default"
