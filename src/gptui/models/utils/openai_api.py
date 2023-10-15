import openai

from .openai_settings_from_dot_env import openai_settings_from_dot_env


def openai_api(dot_env_path: str | None):
    assert dot_env_path, "'dot_env_path' can not be None or empty."
    openai_key, org_id = openai_settings_from_dot_env(dot_env_path)
    openai.api_key = openai_key
    return openai
