from dotenv import dotenv_values


def config_from_dot_env(dot_env_path: str) -> dict:
    """
    Reads the configs from the dot_env_path.
    """

    config = dotenv_values(dot_env_path)

    return config
