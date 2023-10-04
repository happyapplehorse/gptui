import asyncio


def sync_wrapper(func):
    """
    Wrap a sync receiver to a async receiver.

    Usage example:
        result = await signal.send_async("sender", _sync_wrapper=sync_wrapper, message="message")
    """
    async def inner(*args, **kwargs):
        func(*args, **kwargs)
    return inner

def async_wrapper_with_loop(func):
    """
    Wrap a coroutine function receiver to a sync receiver.
    Suitable for cases where signals are sent within an event loop.
    It is recommended to directly use: result = await signal.send_async("sender", _sync_wrapper=sync_wrapper, message="message")

    Return: Task
    
    Example of await task:
        # Retrieve the Task objects returned by coroutine receivers and wait for their completion
        result = signal.send(sender, _async_wrapper=async_wrapper_with_loop, message="message")
        signal_tasks = [item[1] for item in result if getattr(item[0], "_async_inner_", False)]
        await asyncio.gather(*signal_tasks)
    """

    def inner(*args, **kwargs):
        task = asyncio.create_task(func(*args, **kwargs))
        return task
    # Add a coroutine marker to facilitate the identification of its Task object and wait for its completion.
    inner._async_inner_ = True
    return inner

def async_wrapper_without_loop(func):
    """
    Wrap a coroutine function receiver to a sync receiver.
    Suitable for cases where signals are sent without an event loop.

    Return: return the value returned from coroutine.
    
    Usage example:
        result = signal.send("sender", _async_wrapper=async_wrapper_without_loop, message="message")
    """
    def inner(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return inner
