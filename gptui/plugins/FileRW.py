import logging
import os

from semantic_kernel.orchestration.sk_context import SKContext
from semantic_kernel.skill_definition import sk_function, sk_function_context_parameter

from gptui.gptui_kernel.manager import auto_init_params
from gptui.models.doc import Doc
from gptui.views.common_message import CommonMessage


gptui_logger = logging.getLogger("gptui_logger")


class WriteFile:
    def __init__(self, manager):
        self.manager = manager
    
    @auto_init_params("0")
    @classmethod
    def get_init_params(cls, manager) -> tuple:
        return (manager,)

    @sk_function(
        description="Write a file.",
        name="write_file",
    )
    @sk_function_context_parameter(
        name="file_name",
        description="The name of the file, including the extension.",
    )
    @sk_function_context_parameter(
        name="file_content",
        description="The content to be written into the file."
    )
    def write_file(self, context: SKContext) -> str:
        file_name = context["file_name"]
        file_content = context["file_content"]
        self.manager.client.common_resources["temp_files_from_tube"] = {file_name: file_content}
        name, ext = os.path.splitext(file_name)
        document = Doc(doc_name=name, doc_ext=ext, pointer=self.manager.client.common_resources["temp_files_from_tube"][file_name], description="")
        # Only main thread can handle UI event correctly
        self.manager.client.post_message(CommonMessage(message_name="write_file", message_content=document))
        return "Write file sucessfully!" 
