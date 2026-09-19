"""Model Token Pricing & Cost Accounting Catalog.

Maintains normalized per-token pricing across vendors to accurately
track operational expenses per session, task, and agent execution.
"""

from typing import NamedTuple


class ModelPrice(NamedTuple):
    input_per_million: float
    output_per_million: float


# Catalog: Pricing in USD per 1,000,000 tokens
MODEL_PRICING_CATALOG: dict[str, ModelPrice] = {
    # OpenAI Models
    "gpt-4o": ModelPrice(input_per_million=2.50, output_per_million=10.00),
    "gpt-4o-mini": ModelPrice(input_per_million=0.15, output_per_million=0.60),
    "gpt-4-turbo": ModelPrice(input_per_million=10.00, output_per_million=30.00),
    "gpt-3.5-turbo": ModelPrice(input_per_million=0.50, output_per_million=1.50),
    "text-embedding-3-small": ModelPrice(input_per_million=0.02, output_per_million=0.00),
    "text-embedding-3-large": ModelPrice(input_per_million=0.13, output_per_million=0.00),
    # Anthropic Models
    "claude-3-5-sonnet": ModelPrice(input_per_million=3.00, output_per_million=15.00),
    "claude-3-5-sonnet-20241022": ModelPrice(input_per_million=3.00, output_per_million=15.00),
    "claude-3-opus": ModelPrice(input_per_million=15.00, output_per_million=75.00),
    "claude-3-haiku": ModelPrice(input_per_million=0.25, output_per_million=1.25),
    # Google Gemini Models
    "gemini-1.5-pro": ModelPrice(input_per_million=3.50, output_per_million=10.50),
    "gemini-1.5-flash": ModelPrice(input_per_million=0.075, output_per_million=0.30),
    # Local & Mock Models (Zero direct API charge)
    "mock-model": ModelPrice(input_per_million=0.00, output_per_million=0.00),
    "llama3": ModelPrice(input_per_million=0.00, output_per_million=0.00),
    "mistral": ModelPrice(input_per_million=0.00, output_per_million=0.00),
    "nomic-embed-text": ModelPrice(input_per_million=0.00, output_per_million=0.00),
}

DEFAULT_FALLBACK_PRICE = ModelPrice(input_per_million=0.50, output_per_million=1.50)


def get_model_pricing(model: str) -> ModelPrice:
    """Get the ModelPrice entry for a model name with fallback."""
    clean_name = model.lower().strip()
    return MODEL_PRICING_CATALOG.get(clean_name, DEFAULT_FALLBACK_PRICE)


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate the estimated USD cost for a model execution based on token count.

    Args:
        model: Identifier of the model.
        prompt_tokens: Number of prompt/input tokens.
        completion_tokens: Number of completion/output tokens.

    Returns:
        Estimated cost in USD rounded to 6 decimal places.
    """
    cleaned_model = model.lower().strip()
    price = MODEL_PRICING_CATALOG.get(cleaned_model)

    if not price:
        # Partial prefix matching (e.g., 'gpt-4o-2024-08-06' -> 'gpt-4o')
        for key, catalog_price in MODEL_PRICING_CATALOG.items():
            if cleaned_model.startswith(key):
                price = catalog_price
                break

    if not price:
        price = DEFAULT_FALLBACK_PRICE

    input_cost = (prompt_tokens / 1_000_000.0) * price.input_per_million
    output_cost = (completion_tokens / 1_000_000.0) * price.output_per_million
    total_cost = input_cost + output_cost

    return round(total_cost, 6)
