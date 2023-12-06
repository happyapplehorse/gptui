import os
from unittest.mock import patch

from textual.app import App

from gptui.gptui_kernel.manager import Manager


mocked_dotenv_values = {
    "OPENAI_API_KEY": "fake_api_key",
    "OPENAI_ORG_ID": "fake_org_id",
}

def test_scan_plugin():
    with patch('gptui.gptui_kernel.kernel.dotenv_values', return_value=mocked_dotenv_values):
        app = App()
        manager = Manager(app, dot_env_config_path=os.path.expanduser("~/.gptui/.env_gptui"))
        semantic_plugins, native_plugins = manager.scan_plugins("./tests/unit_tests/gptui_kernel/plugins_test_data")
        semantic_plugins_name_list = [plugin_meta.name for plugin_meta in semantic_plugins]
        native_plugins_name_list = [plugin_meta.name for plugin_meta in native_plugins]
        assert set(semantic_plugins_name_list) == {"FunSkill"}
        assert set(native_plugins_name_list) == {"WebServe", "MathPlugin", "WriteFile"}
