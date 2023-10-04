from gptui.data.langchain.document_loaders import TextLoader, UnstructuredHTMLLoader, BSHTMLLoader


def test_text_loader():
    file_path = "./tests/unit_tests/data/langchain_tests_assets/text_load_test.txt"
    loader = TextLoader(file_path)
    document = loader.load()[0]
    assert document.page_content == "This is a txt file for testting text loader.\n"
    assert document.metadata["source"] == "./tests/unit_tests/data/langchain_tests_assets/text_load_test.txt"

def test_bs_html_loader():
    file_path = "./tests/unit_tests/data/langchain_tests_assets/html_load_test.html"
    loader = BSHTMLLoader(file_path)
    document = loader.load()[0]
    assert document.page_content == "\n\nPage Title\n\n\nMy First Heading\nMy first paragraph.\n\n\n"

def test_unstructured_html_loader():
    file_path = "./tests/unit_tests/data/langchain_tests_assets/html_load_test.html"
    loader = UnstructuredHTMLLoader(file_path)
    document = loader.load()[0]
    assert document.page_content == "My First Heading\n\nMy first paragraph."
