"""LLM client infrastructure."""

import json
import logging
from typing import Any, Awaitable, Callable, Optional

import logfire
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessage

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for interacting with LLM APIs (OpenAI-compatible)."""

    def __init__(
        self,
        api_key: Optional[str],
        model: str,
        base_url: str = "https://api.deepseek.com",
    ) -> None:
        """Initialize LLM client.

        Args:
            api_key: API key for the LLM service.
            model: Model identifier.
            base_url: Base URL for the API. Defaults to DeepSeek API.
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

    async def chat_completion_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_handlers: dict[str, Callable[..., Awaitable[Any]]],
        max_iterations: int = 5,
    ) -> str:
        """Generate chat completion with function calling support.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: List of tool definitions for function calling.
            tool_handlers: Dictionary mapping tool names to async handler functions.
            max_iterations: Maximum number of tool call iterations. Defaults to 5.

        Returns:
            Final response content string.

        Raises:
            Exception: If the API call fails or max_iterations is exceeded.
        """
        current_messages = messages.copy()
        iterations = 0

        while iterations < max_iterations:
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=current_messages,
                tools=tools,
            )

            message: ChatCompletionMessage = completion.choices[0].message
            current_messages.append(
                {
                    "role": message.role,
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in (message.tool_calls or [])
                    ],
                }
            )

            # If no tool calls, return the final response
            if not message.tool_calls:
                return message.content or ""

            # Execute tool calls
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments

                if function_name not in tool_handlers:
                    logger.warning(
                        "Unknown tool function: %s. Skipping.", function_name
                    )
                    current_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"Error: Unknown function {function_name}",
                        }
                    )
                    continue

                try:
                    # Parse arguments
                    if isinstance(function_args, str):
                        args = json.loads(function_args)
                    else:
                        args = function_args

                    # Call the async handler
                    handler = tool_handlers[function_name]
                    result = await handler(**args)

                    # Format result as string
                    if isinstance(result, str):
                        result_content = result
                    else:
                        result_content = json.dumps(result, default=str)

                    current_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_content,
                        }
                    )
                except Exception as e:
                    logger.exception(
                        "Error executing tool function %s", function_name
                    )
                    current_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"Error: {str(e)}",
                        }
                    )

            iterations += 1

        # If we've exceeded max iterations, return the last message content
        logger.warning(
            "Max tool call iterations (%d) reached", max_iterations
        )
        return current_messages[-1].get("content", "") or ""

