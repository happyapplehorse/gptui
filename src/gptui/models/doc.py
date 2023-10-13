import os

from ..data.langchain.document_loaders import TextLoader
from ..data.langchain.schema import Document


class Doc:
    def __init__(self, doc_name: str, doc_ext: str, pointer, description: str | None = None):
        self.name = doc_name
        self.ext = doc_ext
        self.pointer = pointer
        self.description = description
        if isinstance(pointer, Document):
            self.content_type = "Document"
        elif isinstance(pointer, str):
            self.content_type = "str"
        else:
            self.content_type = "Unknown"

    @property
    def content(self):
        if isinstance(self.pointer, Document):
            return self.pointer.page_content
        else:
            return self.pointer
    
def document_loader(file_path: str) -> list[Document]:
    file_ext_name = os.path.splitext(file_path)[1]
    if file_ext_name in {".txt", ".md", ".json", ".py", ".cpp", ".yaml", ".yml", ".toml", ".log"}:
        loader = TextLoader(file_path)
    else:
        raise TypeError("Selected file type is not suppported.")
    document_list = loader.load()
    return document_list
