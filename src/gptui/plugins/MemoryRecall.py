import json
import logging

from semantic_kernel.orchestration.sk_context import SKContext
from semantic_kernel.skill_definition import sk_function, sk_function_context_parameter

from gptui.gptui_kernel.manager import auto_init_params


gptui_logger = logging.getLogger("gptui_logger")


class MemoryRecall:
    def __init__(self, manager):
        self.manager = manager
    
    @auto_init_params("0")
    @classmethod
    def get_init_params(cls, manager) -> tuple:
        return (manager,)

    @sk_function(
        description="Recall the specified content from the memory store.",
        name="recall_memory",
    )
    @sk_function_context_parameter(
        name="query",
        description="Topics, questions, etc., that one needs to recall."
    )
    @sk_function_context_parameter(
        name="max_recallable_entries",
        description="Maximum number of recallable information entries.",
        default_value="1"
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
    async def recall_memory(self, context: SKContext) -> str:
        query = context["query"]
        max_recallable_entries = int(context["max_recallable_entries"])
        openai_context_dict = json.loads(str(context["openai_context"]))
        conversation_id = openai_context_dict["id"]
        semantic_memory = self.manager.services.sk_kernel.memory
        try:
            result = await semantic_memory.search_async(str(conversation_id), query, limit=max_recallable_entries, min_relevance_score=0.7)
        except Exception as e:
            gptui_logger.error(f"Error occurred when recall memory. Error: {e}")
            return "An error occurred during the query, please try again later."
        result_str = ""
        for memory in result:
            result_str += memory.id + "\n"
        if not result_str:
            result_str = "No relevant information was found"
        gptui_logger.info(f"Recall memory result:\nconversation_id: {conversation_id}\nResult: {result_str}")
        return result_str
