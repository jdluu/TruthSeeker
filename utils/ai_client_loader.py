import os
import logfire

from dotenv import load_dotenv
from openai import AsyncOpenAI

def initialize_openai_client():
    load_dotenv()
    client = AsyncOpenAI(
        base_url='https://glhf.chat/api/openai/v1',
        api_key=os.getenv('GLHF_API_KEY')
    )
    logfire.configure(send_to_logfire='if-token-present')
    logfire.instrument_openai(client)
    return client
