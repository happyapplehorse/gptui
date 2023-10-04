import pytest

from gptui.models.doc import Doc
from gptui.models.skills import UploadFile


@pytest.mark.asyncio
async def test_upload_file():
    uf = UploadFile()
    input = "Summarize the following documents' content."
    doc1 = Doc(doc_name="test_doc1", doc_ext=".txt", pointer="This is a txt document.")
    doc2 = Doc(doc_name="test_doc2", doc_ext=".txt", pointer="This is another txt document.")
    prompt1 = await uf.import_file_to_context(doc1, input=input)
    prompt2 = await uf.import_file_to_context(doc1, doc2, input=input)
    assert prompt1 == (
        "Summarize the following documents' content.\n\n"
        "******************** FILE CONTENT BEGIN ********************\n"
        "===== Document #1 test_doc1.txt =====\n\n"
        "This is a txt document.\n\n"
        "=====================================\n"
        "******************** FILE CONTENT FINISH *******************\n"
    )
    assert prompt2 == (
        "Summarize the following documents' content.\n\n"
        "******************** FILE CONTENT BEGIN ********************\n"
        "===== Document #1 test_doc1.txt =====\n\n"
        "This is a txt document.\n\n"
        "=====================================\n\n"
        "===== Document #2 test_doc2.txt =====\n\n"
        "This is another txt document.\n\n"
        "=====================================\n"
        "******************** FILE CONTENT FINISH *******************\n"
    )
