import logging

import aiofiles

from ..models.doc import Doc
from ..models.skills import UploadFile
from ..utils.my_text import MyText as Text
from ..views.theme import theme_color as tc


gptui_logger = logging.getLogger("gptui_logger")


class TubeFiles:
    def __init__(self, displayer):
        self.displayer = displayer

    async def insert_files(self, *docs: Doc, input: str) -> str:
        if not docs:
            return input
        upload_file = UploadFile()
        return await upload_file.import_file_to_context(*docs, input=input)

    async def read_file_async(self, path: str, encoding="UTF-8") -> None | str:
        """
        Read a file
        Args:
            path -- The path to the file to read
        Returns:
            The contents of the file
        """
        try:
            async with aiofiles.open(path, "r", encoding=encoding) as fp:
                content = await fp.read()
        except FileNotFoundError:
            gptui_logger.error("File or directory not found")
            self.displayer.update(Text("File or directory not found", tc("yellow") or "yellow"))
            return
        except IsADirectoryError:
            gptui_logger.error("Specified path is a directory, not a file")
            self.displayer.update(Text("Specified path is a directory, not a file", tc("yellow") or "yellow"))
            return
        except UnicodeDecodeError:
            gptui_logger.error("File is not encoded properly")
            self.displayer.update(Text("File is not encoded properly", tc("yellow") or "yellow"))
            return
        except IOError as e:
            gptui_logger.error(f"An I/O error occurred: {e}")
            self.displayer.update(Text("An I/O error occurred", tc("yellow") or "yellow"))
            return
        except Exception as e:
            gptui_logger.error(f"Read file failed. An unexpected error occurred: {e}")
            self.displayer.update(Text(f"Read file failed. An unexpected error occurred: {e}", tc("yellow") or "yellow"))
            return
        else:
            return content

    async def write_file_async(self, file_path: str, file_content) -> bool:
        """
        Write a file
        """
        assert file_content is not None, "Content is required and should not be empty"
        assert file_path is not None, "Path is required and should not be empty"
        try:
            async with aiofiles.open(file_path, "w") as fp:
                await fp.write(file_content)
        except FileNotFoundError:
            gptui_logger.error("File or directory not found")
            self.displayer.update(Text("File or directory not found", tc("yellow") or "yellow"))
            return False
        except IsADirectoryError:
            gptui_logger.error("Specified path is a directory, not a file")
            self.displayer.update(Text("Specified path is a directory, not a file", tc("yellow") or "yellow"))
            return False
        except IOError as e:
            gptui_logger.error(f"An I/O error occurred: {e}")
            self.displayer.update(Text("An I/O error occurred", tc("yellow") or "yellow"))
            return False
        except Exception as e:
            gptui_logger.error(f"Read file failed. An unexpected error occurred: {e}")
            self.displayer.update(Text(f"Read file failed. An unexpected error occurred: {e}", tc("yellow") or "yellow"))
            return False
        else:
            return True
