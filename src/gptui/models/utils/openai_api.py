import openai
from openai import OpenAI, AsyncOpenAI

from .openai_settings_from_dot_env import openai_settings_from_dot_env


OpenAIClient = OpenAI | AsyncOpenAI


def openai_api(dot_env_path: str | None):
    assert dot_env_path, "'dot_env_path' can not be None or empty."
    openai_key, org_id = openai_settings_from_dot_env(dot_env_path)
    openai.api_key = openai_key
    return openai

def openai_api_client(dot_env_path: str | None, async_client: bool = False, **kwargs) -> OpenAIClient:
    assert dot_env_path, "'dot_env_path' can not be None or empty."
    openai_key, org_id = openai_settings_from_dot_env(dot_env_path)
    if async_client is True:
        client = AsyncOpenAI(api_key=openai_key, organization=org_id, **kwargs)
    else:
        client = OpenAI(api_key=openai_key, organization=org_id, **kwargs)
    return client
