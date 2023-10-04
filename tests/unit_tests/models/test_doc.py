from gptui.models.doc import document_loader


def test_document_loader(tmp_path):
    file_content = "This is a test."
    file_path = tmp_path / "test.txt"
    with open(file_path, "w") as fp:
        fp.write(file_content)
    document = document_loader(file_path)
    assert document[0].page_content == "This is a test."
