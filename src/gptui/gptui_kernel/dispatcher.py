import asyncio
from typing import Iterable, AsyncIterator, Callable

from .kernel import Callback


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
        chunk_delta = chunk["choices"][0]["delta"]
        yield chunk_delta


async def async_dispatcher_function_call(source: AsyncIterator, task_keeper: Callable):
    """
    dispatch the message to user and function call
    """
    to_user_queue = asyncio.Queue()
    function_call_queue = asyncio.Queue()

    async def splitter():
        buffer = ''
        before_to_user_content = ''
        to_user_start_active = False
        to_user_end_active = False
        no_function_call = None
        
        first_time = None
        async for chunk in source:
            # skip the last empty chunk
            if not chunk:
                continue

            # if no function call, put the "content" to quequ and continue
            content = chunk.get("content")
            if content is not None:
                await to_user_queue.put(content)
                continue
            
            # get the name of the function called
            function_call = chunk["function_call"]
            if first_time is None:
                first_time = False
                no_function_call = False
                function_name = function_call["name"]
                await function_call_queue.put(f'{{"name":"{function_name}","arguments":')
                continue

            # split the message to user and the function call arguments
            arguments = function_call.get("arguments")

            if arguments is None:
                continue

            buffer += arguments
            if to_user_end_active:
                continue

            if to_user_start_active:
                to_user_content_end = buffer.find('"', to_user_content_start+1)
                if to_user_content_end != -1:
                    if buffer[to_user_content_end-1] != '\\':
                        to_user_end_active = True
                if to_user_end_active:
                    if (last_to_user := buffer[to_user_content_start+1:to_user_content_end]):
                        await to_user_queue.put(last_to_user)
                    await to_user_queue.put(None)
                    # drop the following ", and possible empty characters
                    buffer = buffer[to_user_content_end+2:].lstrip()
                else:
                    await to_user_queue.put(buffer[to_user_content_start+1:])
                    to_user_content_start = len(buffer) - 1
                continue

            to_user_key_start = buffer.find('"to_user":')
            if to_user_key_start != -1:
                before_to_user_content = buffer[:to_user_key_start]
                to_user_content_start = buffer.find('"', to_user_key_start+10)
                if to_user_content_start != -1:
                    if buffer[to_user_content_start-1] != '\\':
                        to_user_start_active = True
                        to_user_content_end = buffer.find('"', to_user_content_start+1)
                        if to_user_content_end != -1:
                            if buffer[to_user_content_end-1] != '\\':
                                to_user_end_active = True
                    if to_user_start_active:
                        if to_user_end_active:
                            if (last_to_user := buffer[to_user_content_start+1:to_user_content_end]):
                                await to_user_queue.put(last_to_user)
                            await to_user_queue.put(None)
                            # drop the following ", and possible empty characters
                            buffer = buffer[to_user_content_end+2:].lstrip()
                        else:
                            await to_user_queue.put(buffer[to_user_content_start+1:])
                            to_user_content_start = len(buffer) - 1

        if no_function_call is None:
            await to_user_queue.put(None)
        else:
            if to_user_key_start == -1:
                # no message to user
                await function_call_queue.put(buffer)
                await to_user_queue.put(None)
            else:
                # there is message to user
                if to_user_end_active:
                    # have put None in to_user_queue
                    await function_call_queue.put(before_to_user_content+buffer)
                else:
                    # message is not complete or parse error, do not do function call
                    await to_user_queue.put(None)

        if first_time is False:
            await function_call_queue.put("}")
        await function_call_queue.put(None)

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
    task_keeper(splitter_task)
    
    return make_generator

async def async_dispatcher_custom_protocol(source: AsyncIterator, roles: list, task_keeper: Callable):
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
    task_keeper(splitter_task)
    return make_generator
