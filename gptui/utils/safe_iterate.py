def safe_next(gen):
    """Avoiding conflicts between StopIteration of generators and StopIteration of coroutine functions in eventloop."""
    try:
        return ("OK", next(gen))
    except StopIteration as e:
        return ("DONE", e.value)

def safe_send(gen, value):
    """Avoiding conflicts between StopIteration of generators and StopIteration of coroutine functions in eventloop."""
    try:
        return ("OK", gen.send(value))
    except StopIteration as e:
        return ("DONE", e.value)
