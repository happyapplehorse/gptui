from gptui.models.openai_tokens_truncate import find_position


def test_find_position():
    lst = [1, 2, 3, 4, 5]
    num = 8
    result = find_position(lst, num)
    assert result == 4
    lst = [2, 0, 5, 1, 3, 2, 1, 0, 4]
    num = 9
    result = find_position(lst, num)
    assert result == 5
    result = find_position(lst, 2)
    assert result == 9
    result = find_position(lst, 20)
    assert result == 0
