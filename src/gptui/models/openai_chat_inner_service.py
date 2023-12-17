import copy
import logging
from typing import Iterable

from openai import OpenAI

from .context import OpenaiContext
from .openai_error import OpenaiErrorHandler
from .openai_tokens_truncate import trim_excess_tokens
from .utils.openai_api import OpenAIClient
from .utils.tokens_num import tokens_num_for_functions_call


gptui_logger = logging.getLogger("gptui_logger")


def chat_service_for_inner(
        messages_list: list, 
        context: OpenaiContext,
        openai_api_client: OpenAIClient,
        **kwargs,
    ) -> Iterable:
    
    inner_context = copy.deepcopy(context)
    
    for one_message in messages_list:
        inner_context.chat_context_append(message=one_message)
    
    # update parameters
    parameters = inner_context.parameters
    parameters.update({"stream": True})
    parameters.update(**kwargs)

    if tools_info := parameters.get("tools"):
        offset_tokens_num = -tokens_num_for_functions_call(tools_info, model=inner_context.parameters["model"])
    else:
        offset_tokens_num = 0
    trimmed_messages = trim_excess_tokens(inner_context, offset=offset_tokens_num)
    
    # Delete the tool reply messages at the beginning of the information list.
    # This is because if the information starts with a function reply message,
    # it indicates that the function call information has already been truncated.
    # The OpenAI API requires that function reply messages must be responses to function calls.
    # Therefore, if the function reply messages are not removed, it will result in an OpenAI API error.
    while trimmed_messages and trimmed_messages[0].get("role") == "tool":
        trimmed_messages.pop(0)

    try:
        response = openai_api_client.with_options(timeout=20.0).chat.completions.create(
            messages=trimmed_messages,
            **parameters,
            )
    except Exception as e:
        gptui_logger.debug('----trimmed_messages----in chat inner')
        gptui_logger.debug(trimmed_messages)
        # The OpenAI API interface is a time-consuming synchronous interface, so it should be called in a new thread, hence there is no event loop here.
        OpenaiErrorHandler().openai_error_handle(error=e, context=inner_context, event_loop=False)
        raise e
    return response
