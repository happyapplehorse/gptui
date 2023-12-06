import os
from unittest.mock import patch

from textual.app import App

from gptui.gptui_kernel.manager import Manager


mocked_dotenv_values = {
    "OPENAI_API_KEY": "fake_api_key",
    "OPENAI_ORG_ID": "fake_org_id",
}

async def test_call_plugin():
    with patch('gptui.gptui_kernel.kernel.dotenv_values', return_value=mocked_dotenv_values):
        app = App()
        manager = Manager(app, dot_env_config_path=os.path.expanduser("~/.gptui/.env_gptui"))
        _, native_plugins = manager.scan_plugins("./tests/unit_tests/gptui_kernel/plugins_test_data")
        for plugin in native_plugins:
            plugin_info = plugin.plugin_info
            manager.add_plugins(plugin_info)
        
        add = manager.available_functions_link["add"]
        args = {
            "input": 1,
            "number2": 2,
        }
        context = manager.gk_kernel.context_render(args, add)
        result = await add.invoke_async(context=context)
        assert int(float(str(result))) == 3
