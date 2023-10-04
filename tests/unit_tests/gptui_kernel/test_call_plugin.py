import os

from textual.app import App

import pytest

from gptui.gptui_kernel.manager import Manager

@pytest.mark.asyncio
async def test_call_plugin():
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
