"""
Cost tracking and token usage estimation for waverunner.

Estimates API costs based on token usage (Sonnet 4.5 pricing).
"""

from typing import Dict, Optional


# Sonnet 4.5 pricing (as of Feb 2026)
# Source: https://www.anthropic.com/pricing
SONNET_45_INPUT_PRICE_PER_M = 3.00   # $3 per million input tokens
SONNET_45_OUTPUT_PRICE_PER_M = 15.00  # $15 per million output tokens


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.

    Uses rough heuristic: ~4 characters per token for English text.
    This is approximate but good enough for cost estimation.

    Args:
        text: Input text

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    # Rough estimate: 4 chars/token
    # More accurate would use tiktoken, but adds dependency
    return len(text) // 4


class CostTracker:
    """Tracks token usage and costs across a sprint."""

    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.task_costs: Dict[str, Dict] = {}

    def add_task_usage(self, task_id: str, prompt: str, response: str):
        """
        Record token usage for a task.

        Args:
            task_id: Task identifier
            prompt: Input prompt sent to LLM
            response: Output response from LLM
        """
        input_tokens = estimate_tokens(prompt)
        output_tokens = estimate_tokens(response)

        # Calculate cost for this task
        input_cost = (input_tokens / 1_000_000) * SONNET_45_INPUT_PRICE_PER_M
        output_cost = (output_tokens / 1_000_000) * SONNET_45_OUTPUT_PRICE_PER_M
        task_cost = input_cost + output_cost

        # Store task-level data
        self.task_costs[task_id] = {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost': task_cost
        }

        # Update totals
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += task_cost

    def _calculate_cost(self):
        """Recalculate total cost from token counts (for testing)."""
        input_cost = (self.total_input_tokens / 1_000_000) * SONNET_45_INPUT_PRICE_PER_M
        output_cost = (self.total_output_tokens / 1_000_000) * SONNET_45_OUTPUT_PRICE_PER_M
        self.total_cost = input_cost + output_cost

    def get_task_cost(self, task_id: str) -> float:
        """Get cost for a specific task."""
        return self.task_costs.get(task_id, {}).get('cost', 0.0)

    def format_summary(self) -> str:
        """Format a human-readable cost summary."""
        return (
            f"Token Usage: {self.total_input_tokens:,} input + {self.total_output_tokens:,} output\n"
            f"Total cost: ${self.total_cost:.4f}"
        )

    def to_dict(self) -> dict:
        """Serialize to dict for board persistence."""
        return {
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_cost': self.total_cost,
            'task_costs': self.task_costs
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CostTracker':
        """Deserialize from dict."""
        tracker = cls()
        tracker.total_input_tokens = data.get('total_input_tokens', 0)
        tracker.total_output_tokens = data.get('total_output_tokens', 0)
        tracker.total_cost = data.get('total_cost', 0.0)
        tracker.task_costs = data.get('task_costs', {})
        return tracker
