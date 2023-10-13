import os
from dotenv import dotenv_values


def openai_settings_from_dot_env() -> tuple[str, str | None]:
    """
    Reads the OpenAI API key and organization ID from the .env_gptui file.

    Returns:
        Tuple[str, str]: The OpenAI API key, the OpenAI organization ID
    """

    config = dotenv_values(os.path.expanduser("~/.gptui/.env_gptui"))
    api_key = config.get("OPENAI_API_KEY", None)
    org_id = config.get("OPENAI_ORG_ID", None)

    assert api_key, "OpenAI API key not found in ~/.gptui/.env_gptui file"

    # It's okay if the org ID is not found (not required)
    return api_key, org_id
