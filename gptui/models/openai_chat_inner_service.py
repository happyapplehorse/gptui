import copy
import logging
from typing import Iterable

import openai

from .context import OpenaiContext
from .openai_error import OpenaiErrorHandler
from .openai_tokens_truncate import trim_excess_tokens
from .utils.tokens_num import tokens_num_for_functions_call
from ..utils.openai_settings_from_dot_env import openai_settings_from_dot_env


gptui_logger = logging.getLogger("gptui_logger")
openai_key, org_id = openai_settings_from_dot_env()
openai.api_key = openai_key


def chat_service_for_inner(
        messages_list: list, 
        context: OpenaiContext,
        **kwargs,
    ) -> Iterable:
    
    inner_context = copy.deepcopy(context)

    for one_message in messages_list:
        inner_context.chat_context_append(message=one_message)
    
    # update parameters
    parameters = inner_context.parameters
    parameters.update({"stream": True})
    parameters.update(**kwargs)

    offset_tokens_num = -tokens_num_for_functions_call(parameters["functions"], model=inner_context.parameters["model"])
    trim_messages = trim_excess_tokens(inner_context, offset=offset_tokens_num)
    
    try:
        response = openai.ChatCompletion.create(
            messages=trim_messages,
            **parameters,
            )
    except Exception as e:
        # The OpenAI API interface is a time-consuming synchronous interface, so it should be called in a new thread, hence there is no event loop here.
        OpenaiErrorHandler().openai_error_handle(error=e, context=inner_context, event_loop=False)
        raise e
    return response
