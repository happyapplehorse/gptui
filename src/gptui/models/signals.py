import textwrap
from blinker import signal


response_to_user_message_stream_signal = signal("response_to_user_message_stream",
    doc=textwrap.dedent(
        """
        Send the to_user part of response message, which usually should be displayed.
        position arg: sender
        kwargs:
            message {dict}:
                content: message from LLM to user in stream
                flag {Literal['content','end']}: 'content' means in stream, while 'end' means stream finished
        It should end with a signal to finish the stream as below:
            signal('response_to_user_message_stream').send(sender, message={'content':'', 'flag':'end'})
        """
    )
)
response_to_user_message_sentence_stream_signal = signal("response_to_user_message_sentence_stream",
    doc=textwrap.dedent(
        """
        Send the to_user part of response message in sentence, which is useful when outputting speech.
        position arg: sender
        kwargs:
            message {dict}:
                content: message from LLM to user in sentence stream
                flag {Literal['content','end']}: 'content' means in stream, while 'end' means stream finished
        It should end with a signal to finish the stream as below:
            signal('response_to_user_message_sentence_stream').send(sender, message={'content':'', 'flag':'end'})
        """
    )
)
notification_signal = signal("notification",
    doc=textwrap.dedent(
        """
        Sending notification-type information, such as status information, error messages, warning, etc.
        position arg: sender
        kwargs:
            message {dict}:
                content: notification
                flag {str}: type of notification, such as 'info', 'warning', 'error', etc.
        """
    )
)
response_auxiliary_message_signal = signal("response_auxiliary_message",
    doc=textwrap.dedent(
        """
        Sending auxiliary information, such as function call information, other internel messages, etc.
        position arg: sender
        kwargs:
            message {dict}:
                content: auxiliary message
                flag {str}: type of auxiliary message
        """
    )
)
chat_context_extend_signal = signal("chat_context_extend",
    doc=textwrap.dedent(
        """
        Sending a notification to save the chat context.
        position arg: sender
        kwargs:
            message {dict}:
                content {dict}: chat context information
                    {
                        "messages" {list}: messages
                        "context": context which is extended to
                    }
                flag:""
        """
    )
)
chat_context_extend_for_sending_signal = signal("chat_context_extend_for_sending",
    doc=textwrap.dedent(
        """
        Sending a notification to append or extend the chat context for sending.
        position arg: sender
        kwargs:
            message {dict}:
                content: dict, chat context information
                    {
                        "messages" {list}: messages
                        "context": context which is extended to
                    }
                flag:""
        """
    )
)
common_message_signal = signal("common_message",
    doc=textwrap.dedent(
        """
        Designed to send general messages.
        Different message structures can be achieved through flexible use of 'content' and 'flag'.
        position arg: sender
        kwargs:
            message {dict}:
                content: message content
                flag {str}: type of the common message
        """
    )
)
