import argparse
import importlib
import logging
import os
import shutil
import sys
import yaml

from .__init__ import __version__ as gptui_version
from .views.tui import MainApp

APP_VERSION = gptui_version


class ConfigManager:
    
    @staticmethod
    def get_config_path_from_args():
        parser = argparse.ArgumentParser(description="gptui cli")
        parser.add_argument('--config', type=str, help='Path to the configuration file.')
        args = parser.parse_args()
        return os.path.expanduser(args.config) if args.config else None

    @staticmethod
    def copy_default_config_to_user_home():
        default_config_path = importlib.resources.files("gptui") / "config.yml"
        user_config_path = os.path.expanduser('~/.gptui/.config.yml')
        
        if not os.path.exists(user_config_path):
            target_dir = os.path.dirname(user_config_path)
            os.makedirs(target_dir, exist_ok=True)
            shutil.copy(default_config_path, user_config_path)
        return user_config_path

    @staticmethod
    def get_config_path():
        config_path = ConfigManager.get_config_path_from_args()

        if config_path:
            if os.path.exists(config_path):
                return config_path
            else:
                print(f"Config file '{config_path}' dose not exist.")
                sys.exit(1)

        user_config_path = os.path.expanduser('~/.gptui/.config.yml')
        if os.path.exists(user_config_path):
            return user_config_path

        return ConfigManager.copy_default_config_to_user_home()

def gptui():
    config_path = ConfigManager.get_config_path()
    gptui_run(config_path=config_path)
   
def gptui_run(config_path: str) -> None:
    # Retrieve config from config path.
    try:
        with open(os.path.join(os.path.dirname(__file__), '.default_config.yml'), "r") as default_config_file:
            config = yaml.safe_load(default_config_file)
    except FileNotFoundError:
        print(f"Default config file '.default_config.yml' is not found.")
        sys.exit(1)
    try:
        with open(config_path, "r") as config_file:
            user_config = yaml.safe_load(config_file)
    except FileNotFoundError:
        pass
    else:
        config.update(user_config)
    
    log_path = os.path.expanduser(config["log_path"])
    log_level_dict = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    log_dir = os.path.dirname(log_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logging.basicConfig(
            filename=log_path,
            filemode='w',
            level=log_level_dict.get(config["log_level"], logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s -[%(funcName)s] - %(message)s",
            )
    gptui_logger = logging.getLogger('gptui_logger')

    app = MainApp(config_path, app_version=APP_VERSION)
    reply = app.run()
    if reply:
        print(reply)


if __name__ == "__main__":

    config_path = os.path.join(os.path.dirname(__file__), "config.yml")
    gptui_run(config_path=config_path)
