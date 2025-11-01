"""LLM client infrastructure."""

import json
import logging
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

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
    ) -> tuple[str, dict[str, float]]:
        """Generate chat completion with function calling support.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: List of tool definitions for function calling.
            tool_handlers: Dictionary mapping tool names to async handler functions.
            max_iterations: Maximum number of tool call iterations. Defaults to 5.

        Returns:
            Tuple of (final response content string, metadata dict with 'search_time').

        Raises:
            Exception: If the API call fails or max_iterations is exceeded.
        """
        current_messages = messages.copy()
        iterations = 0
        total_search_time = 0.0

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
                return message.content or "", {"search_time": total_search_time}

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

                    # Extract search_time from tool result if it's a JSON string
                    if isinstance(result, str):
                        try:
                            tool_result_data = json.loads(result)
                            if isinstance(tool_result_data, dict) and "search_time" in tool_result_data:
                                total_search_time += float(tool_result_data["search_time"])
                        except (json.JSONDecodeError, (KeyError, ValueError, TypeError)):
                            # Not JSON or doesn't have search_time, ignore
                            pass
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
        return current_messages[-1].get("content", "") or "", {"search_time": total_search_time}

    async def chat_completion_with_tools_streaming(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_handlers: dict[str, Callable[..., Awaitable[Any]]],
        max_iterations: int = 5,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[tuple[str, Optional[dict[str, float]]]]:
        """Generate chat completion with function calling support and streaming.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: List of tool definitions for function calling.
            tool_handlers: Dictionary mapping tool names to async handler functions.
            max_iterations: Maximum number of tool call iterations. Defaults to 5.
            status_callback: Optional callback for status updates (e.g., "searching", "analyzing").

        Yields:
            Tuples of (text_chunk, None) during streaming, and finally (full_response, metadata).
        """
        current_messages = messages.copy()
        iterations = 0
        total_search_time = 0.0

        while iterations < max_iterations:
            # First iteration: try streaming, but handle tool calls
            if status_callback:
                status_callback("Analyzing...")

            # Create streaming completion
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=current_messages,
                tools=tools,
                stream=True,
            )

            accumulated_content = ""
            tool_calls_to_execute = []
            message_role = "assistant"

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    
                    # Handle content streaming
                    if delta.content:
                        accumulated_content += delta.content
                        yield (delta.content, None)
                    
                    # Collect tool calls
                    if delta.tool_calls:
                        for tool_call_delta in delta.tool_calls:
                            if tool_call_delta.index is not None:
                                # Ensure we have enough slots
                                while len(tool_calls_to_execute) <= tool_call_delta.index:
                                    tool_calls_to_execute.append({
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""}
                                    })
                                
                                tc = tool_calls_to_execute[tool_call_delta.index]
                                if tool_call_delta.id:
                                    tc["id"] = tool_call_delta.id
                                if tool_call_delta.function:
                                    if tool_call_delta.function.name:
                                        tc["function"]["name"] = tool_call_delta.function.name
                                    if tool_call_delta.function.arguments:
                                        tc["function"]["arguments"] += tool_call_delta.function.arguments

            # Add accumulated message
            if accumulated_content or tool_calls_to_execute:
                message_dict = {
                    "role": message_role,
                    "content": accumulated_content,
                }
                if tool_calls_to_execute:
                    # Format tool calls properly
                    formatted_tool_calls = []
                    for tc in tool_calls_to_execute:
                        if tc["id"] and tc["function"]["name"]:
                            formatted_tool_calls.append({
                                "id": tc["id"],
                                "type": tc["type"],
                                "function": {
                                    "name": tc["function"]["name"],
                                    "arguments": tc["function"]["arguments"],
                                }
                            })
                    if formatted_tool_calls:
                        message_dict["tool_calls"] = formatted_tool_calls
                
                current_messages.append(message_dict)

            # If no tool calls, we're done (streamed the final response)
            if not tool_calls_to_execute or not any(tc.get("id") and tc["function"]["name"] for tc in tool_calls_to_execute):
                # Final response was streamed, return metadata
                yield ("", {"search_time": total_search_time})
                return
            
            # Clear accumulated content for next iteration (tool results will come next)
            accumulated_content = ""

            # Execute tool calls
            if status_callback:
                status_callback("Searching for evidence...")

            for tool_call_data in tool_calls_to_execute:
                if not tool_call_data.get("id") or not tool_call_data["function"]["name"]:
                    continue
                    
                function_name = tool_call_data["function"]["name"]
                function_args_str = tool_call_data["function"]["arguments"]

                if function_name not in tool_handlers:
                    logger.warning(
                        "Unknown tool function: %s. Skipping.", function_name
                    )
                    current_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_data["id"],
                            "content": f"Error: Unknown function {function_name}",
                        }
                    )
                    continue

                try:
                    # Parse arguments
                    args = json.loads(function_args_str)

                    # Call the async handler
                    handler = tool_handlers[function_name]
                    result = await handler(**args)

                    # Extract search_time from tool result
                    if isinstance(result, str):
                        try:
                            tool_result_data = json.loads(result)
                            if isinstance(tool_result_data, dict) and "search_time" in tool_result_data:
                                total_search_time += float(tool_result_data["search_time"])
                        except (json.JSONDecodeError, (KeyError, ValueError, TypeError)):
                            pass
                        result_content = result
                    else:
                        result_content = json.dumps(result, default=str)

                    current_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_data["id"],
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
                            "tool_call_id": tool_call_data["id"],
                            "content": f"Error: {str(e)}",
                        }
                    )

            iterations += 1
            
            # After tool calls, continue to next iteration to get final streamed response
            # (The next iteration will stream the final response with the tool results)

        # If we've exceeded max iterations, get final response (non-streaming)
        logger.warning(
            "Max tool call iterations (%d) reached", max_iterations
        )
        # Make one final non-streaming call to get the response
        final_completion = await self._client.chat.completions.create(
            model=self.model,
            messages=current_messages,
        )
        final_content = final_completion.choices[0].message.content or ""
        yield (final_content, {"search_time": total_search_time})

