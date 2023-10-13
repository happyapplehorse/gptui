import importlib
import logging
import os
from abc import ABCMeta, abstractmethod

import semantic_kernel as sk
from semantic_kernel.template_engine.prompt_template_engine import PromptTemplateEngine

from .doc import Doc
from ..gptui_kernel.manager import Manager


gptui_logger = logging.getLogger("gptui_logger")


class UploadFileInterface(metaclass=ABCMeta):
    @abstractmethod
    async def import_file_to_context(self, *docs: Doc, input: str) -> str:
        ...


class Skills:
    def __init__(self, manager: Manager):
        self.manager = manager

    async def conversation_remember(self, conversation: str):
        to_string_function = self.manager.gk_kernel.sk_kernel.skills.get_function("conversation_service", "conversation_to_string")
        conversation_string = to_string_function(conversation)
        remember_function = self.manager.gk_kernel.sk_kernel.skills.get_function("conversation_service", "conversation_remember")
        summary = await remember_function.invoke_async(conversation_string)
        return str(summary)


class UploadFile(UploadFileInterface):
    
    UPLOAD_FILE_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "gptui_basic_services", "templates", "upload_file_prompt.txt")
    
    def __init__(self):
        self.prompt_template_engine = PromptTemplateEngine()
        self.kernel = sk.Kernel()
        try:
            with open(UploadFile.UPLOAD_FILE_PROMPT_PATH, "r") as import_prompt:
                self.template_text = import_prompt.read()
        except FileNotFoundError:
            gptui_logger.error("File not found")
            #self.app.query_one("#status_region").update(Text("File not found",'yellow'))
        except IsADirectoryError:
            gptui_logger.error("Specified path is a directory, not a file")
            #self.app.query_one("#status_region").update(Text("Specified path is a directory, not a file",'yellow'))
        except UnicodeDecodeError:
            gptui_logger.error("File is not encoded properly")
            #self.app.query_one("#status_region").update(Text("File is not encoded properly",'yellow'))
        except IOError as e:
            #self.app.query_one("#status_region").update(Text(f"An I/O error occurred: {e}",'yellow'))
            gptui_logger.error(f"An I/O error occurred: {e}")
        except Exception as e:
            #self.app.query_one("#status_region").update(Text('Have not sucessfully read memory.','yellow'))
            gptui_logger.error("Read file failed. An unexpected error occurred: {e}")

    async def import_file_to_context(self, *docs: Doc, input: str) -> str:
        if len(docs) >= 1:
            files_content = ''
            for index, doc in enumerate(docs[:-1]):
                file_title = f"===== Document #{index + 1} {doc.name + doc.ext} =====\n\n"
                files_content += file_title
                files_content += doc.content
                files_content += "\n\n" + "=" * (len(file_title) - 2) + "\n\n"
            file_title_last = f"===== Document #{len(docs)} {docs[-1].name + docs[-1].ext} =====\n\n"
            files_content += file_title_last
            files_content += docs[-1].content
            files_content += "\n\n" + "=" * (len(file_title_last) - 2)
        else:
            raise ValueError("There is no document!")
        context = self.kernel.create_new_context()
        context["input"] = input
        context["file_content"] = files_content
        result_prompt = await self.prompt_template_engine.render_async(template_text=self.template_text, context=context)
        return result_prompt
