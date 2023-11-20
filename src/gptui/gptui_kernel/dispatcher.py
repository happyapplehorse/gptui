import asyncio
from typing import Iterable, AsyncIterator

from agere.commander import Callback


async def async_iterable_from_gpt(response: Iterable, callback: Callback | None = None):
    """translate the response from gpt to async iterable"""
    is_first_time = True
    response_iter = iter(response)
    while True:
        chunk = await asyncio.to_thread(next, response_iter, None)
        if is_first_time is True:
            if callback is not None:
                assert callback._task_node is not None
                await callback._task_node.commander._callback_handle(callback=callback, which="at_receiving_start")
            is_first_time = False
        if chunk is None:  # End of the source string
            if callback is not None:
                assert callback._task_node is not None
                await callback._task_node.commander._callback_handle(callback=callback, which="at_receiving_end")
            break
        chunk_choice = chunk.choices[0]
        yield chunk_choice

async def async_dispatcher_tools_call_for_openai(source: AsyncIterator):
    """dispatch the message to user and tools call"""
    to_user_queue = asyncio.Queue()
    function_call_queue = asyncio.Queue()

    async def splitter():
        buffer: str = ''
        tool_call_info: str = ''
        before_to_user_content: str = ''
        after_to_user_content: str = ''
        to_user_start_active: bool = False
        to_user_end_active: bool = False
        
        to_user_key_start: int = 0
        to_user_content_start: int = 0
        find_to_user_content_start_position: int = 0
        tool_call_index_now: int = 0
        
        async def put_a_function():
            await function_call_queue.put(
                tool_call_info + before_to_user_content + after_to_user_content + "}"
            )

        async def do_check_to_user_end():
            nonlocal buffer
            nonlocal to_user_content_start
            if to_user_end_active is True:
                # to_user content finish
                # Put the last to_user content in user queue
                if (last_to_user := buffer[to_user_content_start + 1 : to_user_content_end]):
                    await to_user_queue.put(last_to_user)
                # drop the following ", and possible empty characters
                buffer = buffer[to_user_content_end + 2 :].lstrip()
            else:
                # to_user content dose not finish yet
                # Put the recent to_user content in user queue.
                await to_user_queue.put(buffer[to_user_content_start + 1 :])
                # Refresh to_user_content_start
                to_user_content_start = len(buffer) - 1
        
        async for chunk_choice in source:
            chunk_tool_calls = chunk_choice.delta.tool_calls
            if chunk_choice.finish_reason == "tool_calls":
                if to_user_end_active == to_user_start_active:
                    # Put the last function call.
                    after_to_user_content = buffer
                    await put_a_function()
                await to_user_queue.put(None)
                await function_call_queue.put(None)
                continue
            if chunk_choice.finish_reason is not None:
                await to_user_queue.put(None)
                await function_call_queue.put(None)
                continue

            # Content is not None means no tools call, then put the "content" to user quequ and continue.
            # If no tools call, every chunk will be handle here.
            # Every chunk when no tools call.
            content = chunk_choice.delta.content
            if content is not None:
                await to_user_queue.put(content)
                continue
            
            # This dispatcher only handle tool_calls and content, so other situation will be ignored.
            # Fisrt chunk when call tools.
            if chunk_tool_calls is None:
                # Here includs: 1. the first chunk when call tools; 2. function call; 3. others
                continue

            chunk_tool_call = chunk_tool_calls[0]
            # get the name of the function called
            # Second chunk when call tools.
            if chunk_tool_call.type == 'function':
                tool_call_index = chunk_tool_call.index
                if tool_call_index_now != tool_call_index:
                    # The second and subsequent function calls.
                    after_to_user_content = buffer
                    if to_user_end_active is True: # The content of 'to_user' exists and is complete.
                        # In cases where there is information for the user, messages from different functions are separated by a newline.
                        await to_user_queue.put("\n")
                    if to_user_end_active == to_user_start_active:
                        # Exclude the case where the parameter parsing is incomplete.
                        await put_a_function()
                    buffer = ''
                    to_user_start_active = False
                    to_user_end_active = False
                function_name = chunk_tool_call.function.name
                tool_call_info += f'{{"tool_call_index": {chunk_tool_call.index}, "tool_call_id": "{chunk_tool_call.id}", "name": "{function_name}", "arguments": '
                tool_call_index_now = tool_call_index
                continue

            # Split the message to user and the function call arguments
            arguments = chunk_tool_call.function.arguments
            buffer += arguments
            
            if to_user_end_active:
                # After to_user content
                continue

            if to_user_start_active is True:
                # In 'to_user' param:
                to_user_content_end = buffer.find('"', to_user_content_start + 1)
                if to_user_content_end != -1 and buffer[to_user_content_start - 1] != '\\':
                    to_user_end_active = True
                await do_check_to_user_end()
                continue

            # Before to_user start flag is found.
            to_user_key_start = buffer.find('"to_user":')
            if to_user_key_start == -1:
                continue # Did not find the "to_user" key, continue to receive the next chunk.
            # In 'to_user' param:
            before_to_user_content = buffer[: to_user_key_start]
            to_user_content_start = buffer.find('"', find_to_user_content_start_position or to_user_key_start + 10)
            if to_user_content_start != -1 and buffer[to_user_content_start - 1] != '\\':
                # In the dictionary, the double quotes representing key-value are regular double quotes '"',
                # while double quotes inside strings are escaped double quotes '\"'.
                # We can determine whether the double quotes are in a string or represent a key-value pari by
                # checking if the character before the double quotes is '\'.
                # In content of to_user.
                to_user_start_active = True
                to_user_content_end = buffer.find('"', to_user_content_start + 1)
                if to_user_content_end != -1 and buffer[to_user_content_end - 1] != '\\':
                    # Content of to_user finish.
                    to_user_end_active = True
                await do_check_to_user_end()
            elif to_user_content_start != -1:
                # Under normal circumstances, the code would not execute to this point.
                # This branch is used to handle the exceptional case
                # where the string content of the 'to_user' is not immediately followed after '"to_user":'
                find_to_user_content_start_position = to_user_content_start

    role_queue_dict = {"to_user":to_user_queue, "function_call":function_call_queue}
    
    def make_generator(role_name: str):
        async def generator():
            while True:
                value = await role_queue_dict[role_name].get()
                if value is None: # End of the queue
                    break
                yield value
        return generator()
    
    splitter_task = asyncio.create_task(splitter())
    
    return make_generator

async def async_dispatcher_custom_protocol(source: AsyncIterator, roles: list):
    """
    generate a async generator for each role
    roles is a list like [(role_start_tag, role_end_tag),]
    """
    role_queue_dict = {}
    buffer_length = 0
    for role in roles:
        role_queue_dict[role[0]] = asyncio.Queue()
        length = max(len(role[0]), len(role[1]))
        if length > buffer_length:
            buffer_length = length
    buffer_length += 1

    async def splitter():
        status = None
        count = 0
        buffer = ' ' * buffer_length
        async for chunk in source:
            # skip the last empty chunk
            if not chunk:
                continue
            # skip the first possibly empty content or no content key
            chunk_content = chunk.get("content")
            if not chunk_content:
                continue
            
            # ensure char enter buffer one by one
            # function 1: make functionality easier to implement
            # function 2: avoid missing tag if the chunk is too long, such as when the network freezes
            for char in chunk_content:
                buffer = buffer[1:] + char
                if count:
                    count -= 1
                    continue
                if status == None:
                    for role in roles:
                        if role[0] in buffer:
                            status = role[0]
                            count = len(role[0])
                            break
                    continue
                if status != None:
                    for role in roles:
                        if status == role[0]:
                            if role[1] in buffer:
                                status = None
                                break
                            else:
                                await role_queue_dict[role[0]].put(buffer[-len(role[1])])
                                break
                    continue
        # Signal the end of the queues
        for queue in role_queue_dict.values():
            await queue.put(None)
    
    def make_generator(role_name: str):
        async def generator():
            while True:
                value = await role_queue_dict[role_name].get()
                if value is None: # End of the queue
                    break
                yield value
        return generator()
    
    splitter_task = asyncio.create_task(splitter())
    return make_generator
