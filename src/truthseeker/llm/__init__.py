"""Legacy LLM imports - redirects to infrastructure layer."""

# Backward compatibility
from ..infrastructure.llm.parser import llm_system_prompt, parse_llm_json

__all__ = ["llm_system_prompt", "parse_llm_json"]

