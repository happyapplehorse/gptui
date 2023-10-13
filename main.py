import os
import sys

from src.gptui.__main__ import gptui_run

   
if __name__ == "__main__":

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
    gptui_run(config_path='src/gptui/config.yml')
