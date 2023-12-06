import logging

from openai.types.chat import ChatCompletionMessageParam

from .context import OpenaiContext
from .utils.tokens_num import tokens_num_from_string, tokens_num_from_chat_context


gptui_logger = logging.getLogger("gptui_logger")


def find_position(lst, num):
    """
    Finds the farthest left position in the list where the sum of all elements after that position is less than the given number 'num'.
    If you move one position backward, the sum of all elements after that new position will be greater than 'num'.
    
    Args:
        - lst {list}: The list of integers.
        - num {int}: The target number.
    
    Returns:
        int: The 1-based index of the position found, (index + 1)
        return 0 if the sum of all integers is less than num,
        return the length of lst if the last integers is greater than num.
    """
    prefix_sum = [0]
    for x in lst:
        prefix_sum.append(prefix_sum[-1] + x)

    left, right = 0, len(prefix_sum) - 1

    while left < right:
        mid = (left + right) // 2
        if prefix_sum[-1] - prefix_sum[mid] < num:
            right = mid
        else:
            left = mid + 1

    return left

def trim_excess_tokens(
    context: OpenaiContext,
    max_tokens_num: int | None = None,
    offset: int = 0
) -> list[ChatCompletionMessageParam]:
    """Truncate the given context according to max_tokens_num, only retaining the last part.

    It will return a new chat_context list and not change the original chat_context.

    Args:
        - context (OpenaiContext): the context need to be trimmed.
        - max_tokens_num (int): the max tokens number allowed.
        - offset (int): for positive value, increase max_tokens_num; for negative value, decrease max_tokens_num.

    Retruns:
        list[dict]: truncated chat_context of context.
    """
    tokens_num_list = context.tokens_num_list
    if max_tokens_num is None:
        max_tokens_num = context.max_sending_tokens_num
    assert max_tokens_num is not None
    assert context.chat_context is not None
    num_after_offset = max_tokens_num + offset
    if num_after_offset <= 0:
        gptui_logger.warning(
            "The valid token length is less than zero, only the last message is kept. "
            "This could likely lead to a token lenght exceeding the limit error."
        )
        return context.chat_context[-1:]
    position = find_position(lst=tokens_num_list, num=num_after_offset)
    if position >= len(tokens_num_list):
        model = context.parameters["model"]
        trim_status = True
        new_tokens_num = num_after_offset
        out_dict = context.chat_context[-1:][0] # Don't change the original context.
        while trim_status:
            new_tokens_num -= 5
            if new_tokens_num <= 0: # The number 5 is the assumed additional tokens count in message dict compared to message content
                out_dict["content"] = ""
                return [out_dict]
            out_dict_content = out_dict["content"]
            assert isinstance(out_dict_content, str)
            trim_string = trim_string_by_tokens(out_dict_content, max_tokens=new_tokens_num, model=model)
            out_dict["content"] = trim_string
            if tokens_num_from_chat_context([out_dict], model=model) < num_after_offset:
                trim_status = False
        return [out_dict]
    return context.chat_context[position:]

def trim_string_by_tokens(string: str, max_tokens: int, model: str) -> str:
    """trims the input string based on a specified maximum token count.
        - If the overall token count of the input string is less than or equal to the specified maximum token count, the function returns the original string as is.
        - If the token count of the input string exceeds the specified maximum, the function trims words from the beginning of the string progressively until the token count does not exceed the limit.

    Parameters:
        - string (str): The input string to be trimmed.
        - max_tokens (int): The allowable maximum token count.

    Returns:
        - str: The trimmed string where the token count does not surpass the specified maximum token count.
    """
    words = string.split()
    if tokens_num_from_string(string, model) <= max_tokens:
        return string

    left, right = 0, len(words)
    
    while left < right:
        mid = (left + right) // 2
        current_str = ' '.join(words[mid:])
        current_tokens = tokens_num_from_string(current_str, model)
        
        if current_tokens == max_tokens:
            return current_str
        elif current_tokens < max_tokens:
            right = mid
        else:
            left = mid + 1

    if right == len(words):
        return ""
    return ' '.join(words[right:])
