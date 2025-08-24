import os
import logfire

from dotenv import load_dotenv
from openai import AsyncOpenAI

def initialize_openai_client():
    """
    Initialize and return an AsyncOpenAI client configured for Synthetic.new.

    This will look for SYNTHETIC_API_KEY in the environment.
    """
    load_dotenv()
    api_key = os.getenv("SYNTHETIC_API_KEY")
    client = AsyncOpenAI(
        base_url="https://api.synthetic.new/v1",
        api_key=api_key
    )
    # Configure logfire (no-op if token not present)
    logfire.configure(send_to_logfire='if-token-present')
    try:
        logfire.instrument_openai(client)
    except Exception:
        # Instrumentation is best-effort; do not fail initialization if it errors.
        pass
    return client
