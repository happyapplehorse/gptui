import textwrap
from gptui.controllers.decorate_display_control import extract_files_from_string
from rich import print


def test_extract_files_from_string():
    input_string = textwrap.dedent(
    """\
    before
    ******************** FILE CONTENT BEGIN ********************
    ===== Document #1 text.txt =====

    This is the content of the document #1.


    ==========================

    ===== Document #2 test.md =====

    This is the content of the the file #2.


    ===========================
    ******************** FILE CONTENT FINISH *******************
    after"""
    )

    expected_output = ["before\n", ("text.txt", "test.md"), "\nafter"]
    out = extract_files_from_string(input_string)
    assert out == expected_output

'''
def test_pre_wrap():
    input_string = """before
    ******************** FILE CONTENT BEGIN ********************
    ===== Document #1 text.txt =====

    This is the content of the document #1.


    ==========================

    ===== Document #2 test.txt =====

    This is the content of the the file #2.


    ===========================
    ******************** FILE CONTENT FINISH *******************
    after"""

    #out_wrap = pre_decorate(input_string, wrap=True)
    #out_no_wrap = pre_decorate(input_string, wrap=False)
    
    input_string2 = "abcd"
    #out = pre_wrap(input_string2, wrap=False)
    #assert out == '\x1b[39mabcd\x1b[0m'

def test_wrap_files_in_string():
    input = ["before", ("text.txt", "test.txt", "test_long_title.txt", "abc.json", "abcdef.abc"), "middle", ("test.txt"), "after"]
    out = wrap_files_in_string(input)
    print(out)
'''
