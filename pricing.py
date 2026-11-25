"""Model price table — USD per 1M tokens.

Update these numbers when providers change prices. Every row is
(prompt_price_per_1M, completion_price_per_1M).
"""

PRICING = {
    # OpenAI
    "gpt-4o-mini":      (0.15, 0.60),
    "gpt-4o":           (2.50, 10.00),
    "gpt-4.1-mini":     (0.40, 1.60),
    # Google
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    # Anthropic
    "claude-haiku":     (0.80, 4.00),
    "claude-sonnet":    (3.00, 15.00),
    # local / mock
    "mock-1":           (0.00, 0.00),
}

DEFAULT_MODEL = "mock-1"


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Cost of a single call in USD."""
    p_in, p_out = PRICING.get(model, PRICING[DEFAULT_MODEL])
    return (prompt_tokens / 1_000_000) * p_in + (completion_tokens / 1_000_000) * p_out


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return max(1, round(len(text) / 4))
