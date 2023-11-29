import json
import logging

from semantic_kernel.orchestration.sk_context import SKContext
from semantic_kernel.skill_definition import sk_function, sk_function_context_parameter

from gptui.gptui_kernel.manager import auto_init_params


gptui_logger = logging.getLogger("gptui_logger")


class Memo:
    def __init__(self, app):
        self.app = app

    @auto_init_params("0")
    @classmethod
    def get_init_params(cls, manager) -> tuple:
        return (manager.client,)
    
    @sk_function(
        description="Record important information; the content should be significant and concise.",
        name="write_memo",
    )
    @sk_function_context_parameter(
        name="content",
        description="Information to be written into the memo.",
    )
    @sk_function_context_parameter(
        name="openai_context",
        description=(
            "The dictionary string version of the OpenaiContext instance. "
            "This is a special parameter that typically doesn't require manual intervention, as it is usually automatically managed."
            "Unless there's a clear intention, please keep its default value."
        ),
        default_value="AUTO"
    )
    def write_memo(self, context: SKContext) -> str:
        content = context["content"]
        try:
            openai_context_dict = json.loads(str(context["openai_context"]))
        except json.JSONDecodeError:
            return ("An error occurred while parsing the openai_context content. "
                "You should not provide the 'openai_context' parameter as the system automatically supplies it."
            )
        conversation_id = int(openai_context_dict["id"])
        try:
            conversation = self.app.openai.conversation_dict[conversation_id]
        except KeyError:
            return f"Write memo faild. Conversation id {conversation_id} is not correct."
        openai_context = conversation["openai_context"]
        bead_content = openai_context.bead
        bead_content[-1]["content"] += "\n" + content
        openai_context.insert_bead()
        return f"'{content}' have been written into the memo!" 
