import json
import logging

from semantic_kernel.skill_definition import sk_function

from ....gptui_kernel import Kernel
from ....gptui_kernel.manager import auto_init_params


gptui_logger = logging.getLogger("gptui_logger")


class ConversationService:
    def __init__(self, manager):
        self.gk_kernel = Kernel(manager.dot_env_config_path)

    @auto_init_params("0")
    @classmethod
    def get_init_params(cls, manager) -> tuple:
        return (manager,)

    @sk_function(
        description="Generate a title for given conversation context. The conversation context is a json string converted from a conversation dict with openai gpt.",
        name="conversation_title",
        input_description="The json string of conversation which need a title.",
    )
    async def conversation_title(self, chat_context_json_str: str) -> str:
        def chat_context_to_string(chat_context_json_str: str) -> str:
            chat_context_json = json.loads(chat_context_json_str)
            chat_context = ''
            assert isinstance(chat_context_json, list)
            for piece in chat_context_json:
                chat_context += piece["role"] + ": " + str(piece["content"] or piece.get("tool_calls") or "") + "\n\n"
            return chat_context[:1000]
        
        sk_prompt = (
            "Generate a concise and clear title for the following chat record. "
            "The title should be as brief as possible, not exceeding ten English words or twenty Chinese characters, " 
            "and the language of the title should be consistent with the content of the chat. "
            "Do not have line breaks '\\n'. "
            "chat record: {{$INPUT}}\n"
            "title:"
        )
        
        chat_context = chat_context_to_string(chat_context_json_str)
        make_title_function = self.gk_kernel.sk_kernel.create_semantic_function(sk_prompt, max_tokens=50)
        name = await make_title_function.invoke_async(chat_context)
        name = str(name)
        if name.startswith('"'):
            name = name[1:]
            if name.endswith('"'):
                name = name[:-1]
        return name
