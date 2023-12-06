import logging
import tiktoken


gptui_logger = logging.getLogger("gptui_logger")


def tokens_num_from_string(string: str, model: str) -> int:
    """
    caculate the tokens num of given string
    """
    encoding = tiktoken.encoding_for_model(model)
    tokens_num = len(encoding.encode(string))
    return tokens_num

def tokens_num_from_chat_context(chat_context: list, model: str) -> int:
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        gptui_logger.warning("Warning when caculate tokens num: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo":
        gptui_logger.warning("Warning when caculate tokens num: gpt-3.5-turbo may change over time. Returning num tokens assuming gpt-3.5-turbo-1106.")
        return tokens_num_from_chat_context(chat_context, model="gpt-3.5-turbo-1106")
    elif model == "gpt-4":
        gptui_logger.warning("Warning when caculate tokens num: gpt-4 may change over time. Returning tokens num assuming gpt-4-0613.")
        return tokens_num_from_chat_context(chat_context, model="gpt-4-0613")
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        "gpt-3.5-turbo-1106",  # Unverified.
        "gpt-4-1106-preview",  # Unverified.
    }:
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        gptui_logger.error(f"""tokens_num_from_chat_context() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")
        raise NotImplementedError(f"""tokens_num_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")
    tokens_num = 0
    for message in chat_context:
        tokens_num += tokens_per_message
        for key, value in message.items():
            tokens_num += len(encoding.encode(str(value)) if value else [])
            if key == "name":
                tokens_num += tokens_per_name
    tokens_num += 3  # every reply is primed with <|start|>assistant<|message|>
    return tokens_num

def tokens_num_for_functions_call(functions_info: list[dict], model: str) -> int:
    return tokens_num_from_string(repr(functions_info), model=model)
