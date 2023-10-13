import os
from dotenv import dotenv_values


def config_from_dot_env() -> dict:
    """
    Reads the configs from the .env_gptui file.
    """

    config = dotenv_values(os.path.expanduser("~/.gptui/.env_gptui"))

    return config
