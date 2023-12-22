import datetime


def time_now() -> str:
    """
    Get the current date and time in the local time zone"

    Example:
        {{time.now}} => Sunday, January 12, 2031 9:15 PM
    """
    now = datetime.datetime.now()
    return now.strftime("%A, %B %d, %Y %I:%M %p")

