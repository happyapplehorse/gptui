import json
import copy
from dataclasses import asdict
from gptui.models.context import OpenaiContext

def test_openai_context_serialization_deserialization():
    openai_context_original = OpenaiContext(chat_context = [{"role": "user", "content":"Hi!"}, {"role":"assistant", "content":"Hello, how can i assist you today?"}])
    openai_context_original.parameters = {"model": "gpt-4"}
    openai_context = copy.deepcopy(openai_context_original)
    openai_context_str = json.dumps(asdict(openai_context), ensure_ascii = False, sort_keys = True, indent = 4, separators = (',',':'))
    openai_context_build = json.loads(openai_context_str)
    openai_context_rebuild = OpenaiContext(**openai_context_build)
    assert openai_context_rebuild == openai_context_original

def test_openai_context_deepcopy():
    openai_context_original = OpenaiContext(chat_context = [{"role": "user", "content":"Hi!"}, {"role":"assistant", "content":"Hello, how can i assist you today?"}])
    openai_context_original.parameters = {"model": "gpt-4"}
    openai_context_original.plugins = [["mutable"], "plugin2"]
    openai_context_deepcopy = copy.deepcopy(openai_context_original)
    assert openai_context_deepcopy == openai_context_original
    assert id(openai_context_deepcopy.chat_context) != id(openai_context_original.chat_context)
    assert set(map(id, openai_context_original.plugins)) == set(map(id, openai_context_deepcopy.plugins))

