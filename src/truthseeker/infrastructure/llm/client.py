"""LLM client infrastructure."""

import logging
from typing import Optional

import logfire
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for interacting with LLM APIs (OpenAI-compatible)."""

    def __init__(
        self,
        api_key: Optional[str],
        model: str,
        base_url: str = "https://api.synthetic.new/v1",
    ) -> None:
        """Initialize LLM client.

        Args:
            api_key: API key for the LLM service.
            model: Model identifier.
            base_url: Base URL for the API. Defaults to Synthetic.new.
        """
        self.model = model
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        # Configure logfire (best-effort, no-op if token not present)
        try:
            logfire.configure(send_to_logfire="if-token-present")
            logfire.instrument_openai(self._client)
        except Exception:
            logger.debug("Logfire instrumentation failed; continuing without it.")

    async def chat_completion(
        self, messages: list[dict[str, str]], **kwargs
    ) -> str:
        """Generate chat completion from LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            **kwargs: Additional arguments to pass to the API.

        Returns:
            Response content string.

        Raises:
            Exception: If the API call fails.
        """
        completion = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )
        return completion.choices[0].message.content or ""

