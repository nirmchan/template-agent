"""LLM factory for creating configured model instances.

This module provides the factory function for creating language model instances
with appropriate configuration. It supports both Google Gemini models (via
langchain_google_genai) and Anthropic Claude models (via Vertex AI), with
consistent settings and authentication across the application.

Why this exists:
    Different agents and subagents need LLM instances with proper credentials,
    temperature settings, and model selection. This factory centralizes model
    creation logic and ensures consistent configuration.

Functions:
    create_model: Create a configured LLM instance by model name
"""

from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai.model_garden import ChatAnthropicVertex

from deep_agent.src.error_handling import llm_retry
from deep_agent.src.exceptions import LLMError
from deep_agent.src.settings import settings
from deep_agent.utils.google_creds import get_service_account_credentials
from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger(log_level=settings.PYTHON_LOG_LEVEL)

_DEFAULT_MAX_OUTPUT_TOKENS: int = settings.MAX_OUTPUT_TOKENS

GEMINI_MODELS: list[str] = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-3.1-pro-preview",
]

CLAUDE_MODELS: list[str] = [
    "claude-sonnet-4",
]


@llm_retry
def create_model(
    model_name: str,
    temperature: float = 0.0,
    max_output_tokens: int | None = None,
) -> BaseChatModel:
    """Create a Vertex AI model (Gemini or Claude).

    Retries up to 3 times with exponential backoff on transient failures
    (credential refresh, network issues, rate limits).

    Args:
        model_name: Model name from GEMINI_MODELS or CLAUDE_MODELS.
        temperature: Model temperature (default: 0.0).
        max_output_tokens: Maximum tokens in model response (default: 8192).

    Returns:
        Configured model instance.

    Raises:
        ValueError: If model_name is empty or unsupported.
        LLMError: If model creation fails after retries.
    """
    if not model_name or not model_name.strip():
        raise ValueError("model_name cannot be empty")

    max_output_tokens = max_output_tokens or _DEFAULT_MAX_OUTPUT_TOKENS

    is_claude = model_name in CLAUDE_MODELS
    is_gemini = model_name in GEMINI_MODELS

    if not is_claude and not is_gemini:
        raise ValueError(
            f"Unknown model '{model_name}'. "
            f"Supported models: {GEMINI_MODELS + CLAUDE_MODELS}"
        )

    model_type = "Claude" if is_claude else "Gemini"

    try:
        credentials, project = get_service_account_credentials()

        logger.info(
            f"Creating {model_type} model via Vertex AI",
            model=model_name,
            model_type=model_type,
            project=project,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        if is_claude:
            return ChatAnthropicVertex(
                model=model_name,
                project=project,
                credentials=credentials,
                temperature=temperature,
                max_tokens=max_output_tokens,
                max_retries=2,
            )
        else:
            return ChatGoogleGenerativeAI(
                model=model_name,
                temperature=temperature,
                credentials=credentials,
                project=project,
                max_output_tokens=max_output_tokens,
                max_retries=2,
            )

    except (ValueError, LLMError):
        raise
    except Exception as e:
        logger.error(
            f"Failed to create {model_type} model '{model_name}'",
            error_type=type(e).__name__,
            model=model_name,
            model_type=model_type,
            error_message=str(e),
            exc_info=True,
        )
        raise LLMError(
            f"Failed to create {model_type} model '{model_name}': {e}"
        ) from e
