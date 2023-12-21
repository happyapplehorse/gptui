# Hotkeys

Press `ESC`, `ctrl+[`, or `ctrl+/` to bring up the hotkey menu.

Direct hotkeys:
- ctrl+q: exit the program
- ctrl+n: open a new conversation
- ctrl+s: save the current conversation
- ctrl+r: delete the current conversation
- ctrl+o: toggle the monochrome theme
- ctrl+t: switch to assistant tube
- ctrl+g: switch to file tube
- ctrl+p: switch to plugins panel

# Dynamic commands

## set_chat_parameters

Set the OpenAI chat parameters.
Arguments are specified in dictionary form.

Commonly used parameters are:
  - model
  - stream
  - temperature
  - frequency_penalty
  - presence_penalty
  - max_tokens

## set_max_sending_tokens_ratio

Set the ratio number of sent tokens to the total token window.
Argument is a float number between 0 and 1.
