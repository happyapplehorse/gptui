import logging
import sys
import time
import traceback
import types

import litellm
import tokentrim as tt
from rich import print
from rich.markdown import Markdown


class FakeReadlineContext:
    """
    When used in wezterm, invoking open-interpreter with its import readline causes the TUI to freeze and display anomalies.
    Since readline in open-interpreter is not useful for this project,
    it is temporarily replaced here to prevent it from importing readline.
    """
    
    def __enter__(self):
        self.original_readline = sys.modules.get("readline")
        fake_readline_module = types.ModuleType("f_readline")
        def add_history(*args, **kwargs):
            """Only this function was used in open-interpreter, so only a replacement for this function is provided."""
            pass
        fake_readline_module.add_history = add_history
        sys.modules["readline"] = fake_readline_module
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        if self.original_readline:
            sys.modules["readline"] = self.original_readline
        else:
            del sys.modules["readline"]


with FakeReadlineContext():
    import readline
    from interpreter.code_block import CodeBlock
    from interpreter.code_interpreter import CodeInterpreter
    from interpreter.get_hf_llm import get_hf_llm
    from interpreter.interpreter import Interpreter, function_schema, confirm_mode_message
    from interpreter.message_block import MessageBlock
    from interpreter.utils import merge_deltas, parse_partial_json


gptui_logger = logging.getLogger("gptui_logger")


class MyInterpreter(Interpreter):
    
    # Override the 'chat' method, replacing call respond to yield from respond.
    def chat(self, message=None, return_messages=False):
        # Connect to an LLM (an large language model)
        if not self.local:
            # gpt-4
            self.verify_api_key()

        # ^ verify_api_key may set self.local to True, so we run this as an 'if', not 'elif':
        if self.local:

            # Code-Llama
            if self.llama_instance == None:

                # Find or install Code-Llama
                try:
                    self.llama_instance = get_hf_llm(self.model, self.debug_mode, self.context_window)
                    if self.llama_instance == None:
                        # They cancelled.
                        return
                except:
                    traceback.print_exc()
                    # If it didn't work, apologize and switch to GPT-4

                    print(Markdown("".join([
                        f"> Failed to install `{self.model}`.",
                        f"\n\n**Common Fixes:** You can follow our simple setup docs at the link below to resolve common errors.\n\n```\nhttps://github.com/KillianLucas/open-interpreter/tree/main/docs\n```",
                        f"\n\n**If you've tried that and you're still getting an error, we have likely not built the proper `{self.model}` support for your system.**",
                        "\n\n*( Running language models locally is a difficult task!* If you have insight into the best way to implement this across platforms/architectures, please join the Open Interpreter community Discord and consider contributing the project's development. )",
                        "\n\nPress enter to switch to `GPT-4` (recommended)."
                    ])))
                    input()

                    # Switch to GPT-4
                    self.local = False
                    self.model = "gpt-4"
                    self.verify_api_key()

        # Display welcome message
        welcome_message = ""

        if self.debug_mode:
            welcome_message += "> Entered debug mode"

        # If self.local, we actually don't use self.model
        # (self.auto_run is like advanced usage, we display no messages)
        if not self.local and not self.auto_run:

            if self.use_azure:
                notice_model = f"{self.azure_deployment_name} (Azure)"
            else:
                notice_model = f"{self.model.upper()}"
            welcome_message += f"\n> Model set to `{notice_model}`\n\n**Tip:** To run locally, use `interpreter --local`"

        if self.local:
            welcome_message += f"\n> Model set to `{self.model}`"

        # If not auto_run, tell the user we'll ask permission to run code
        # We also tell them here how to exit Open Interpreter
        if not self.auto_run:
            welcome_message += "\n\n" + confirm_mode_message

        welcome_message = welcome_message.strip()


        # Modified by happyapplehorse ##########################################
        # Original:
        # Print welcome message with newlines on either side (aesthetic choice)
        # unless we're starting with a blockquote (aesthetic choice)
        #if welcome_message != "":
        #    if welcome_message.startswith(">"):
        #        print(Markdown(welcome_message), '')
        #    else:
        #        print('', Markdown(welcome_message), '')
        # Changed to:

        ########################################################################


        # Check if `message` was passed in by user
        if message:
            # If it was, we respond non-interactivley
            self.messages.append({"role": "user", "content": message})
            # Modified by happyapplehorse ##########################################
            # Original:
            #self.respond()
            # Changed to:
            out = yield from self.respond()
            return out
            ########################################################################

        else:
            # If it wasn't, we start an interactive chat
            while True:
                try:
                    user_input = input("> ").strip()
                except EOFError:
                    break
                except KeyboardInterrupt:
                    print()  # Aesthetic choice
                    break

                # Use `readline` to let users up-arrow to previous user messages,
                # which is a common behavior in terminals.
                readline.add_history(user_input)

                # If the user input starts with a `%` or `/`, it's a command
                if user_input.startswith("%") or user_input.startswith("/"):
                    self.handle_command(user_input)
                    continue

                # Add the user message to self.messages
                self.messages.append({"role": "user", "content": user_input})

                # Respond, but gracefully handle CTRL-C / KeyboardInterrupt
                try:
                    self.respond()
                except KeyboardInterrupt:
                    pass
                finally:
                    # Always end the active block. Multiple Live displays = issues
                    self.end_active_block()

        if return_messages:
            return self.messages
    
    # Override the 'respond' method, replacing interactions with the terminal with 'yield'.
    def respond(self):
        # Add relevant info to system_message
        # (e.g. current working directory, username, os, etc.)
        info = self.get_info_for_system_message()

        # This is hacky, as we should have a different (minified) prompt for CodeLLama,
        # but for now, to make the prompt shorter and remove "run_code" references, just get the first 2 lines:
        if self.local:
            self.system_message = "\n".join(self.system_message.split("\n")[:2])
            self.system_message += "\nOnly do what the user asks you to do, then ask what they'd like to do next."

        system_message = self.system_message + "\n\n" + info

        if self.local:
            messages = tt.trim(self.messages, max_tokens=(self.context_window - self.max_tokens - 25),
                               system_message=system_message)
        else:
            messages = tt.trim(self.messages, self.model, system_message=system_message)

        if self.debug_mode:
            print("\n", "Sending `messages` to LLM:", "\n")
            print(messages)
            print()

        # Make LLM call
        if not self.local:
            # GPT

            error = ""

            for _ in range(3):  # 3 retries
                try:

                    if self.use_azure:
                        response = litellm.completion(
                            f"azure/{self.azure_deployment_name}",
                            messages=messages,
                            functions=[function_schema],
                            temperature=self.temperature,
                            stream=True,
                        )
                    else:
                        if self.api_base:
                            # The user set the api_base. litellm needs this to be "custom/{model}"
                            response = litellm.completion(
                                api_base=self.api_base,
                                model="custom/" + self.model,
                                messages=messages,
                                functions=[function_schema],
                                stream=True,
                                temperature=self.temperature,
                            )
                        else:
                            # Normal OpenAI call
                            response = litellm.completion(
                                model=self.model,
                                messages=messages,
                                functions=[function_schema],
                                stream=True,
                                temperature=self.temperature,
                            )

                    break
                except:
                    if self.debug_mode:
                        traceback.print_exc()
                    error = traceback.format_exc()
                    time.sleep(3)
            else:
                raise Exception(error)

        elif self.local:
            # Code-Llama

            # Convert messages to prompt
            # (This only works if the first message is the only system message)

            def messages_to_prompt(messages):

                for message in messages:
                    # Happens if it immediatly writes code
                    if "role" not in message:
                        message["role"] = "assistant"

                # Falcon prompt template
                if "falcon" in self.model.lower():

                    formatted_messages = ""
                    for message in messages:
                        formatted_messages += f"{message['role'].capitalize()}: {message['content']}\n"
                    formatted_messages = formatted_messages.strip()

                else:
                    # Llama prompt template

                    # Extracting the system prompt and initializing the formatted string with it.
                    system_prompt = messages[0]['content']
                    formatted_messages = f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n"

                    # Loop starting from the first user message
                    for index, item in enumerate(messages[1:]):
                        role = item['role']
                        content = item['content']

                        if role == 'user':
                            formatted_messages += f"{content} [/INST] "
                        elif role == 'function':
                            formatted_messages += f"Output: {content} [/INST] "
                        elif role == 'assistant':
                            formatted_messages += f"{content} </s><s>[INST] "

                    # Remove the trailing '<s>[INST] ' from the final output
                    if formatted_messages.endswith("<s>[INST] "):
                        formatted_messages = formatted_messages[:-10]

                return formatted_messages

            prompt = messages_to_prompt(messages)
            # Lmao i can't believe this works (it does need this btw)
            if messages[-1]["role"] != "function":
                prompt += "Let's explore this. By the way, I can run code on your machine by writing the code in a markdown code block. This works for shell, javascript, python, R, and applescript. I'm going to try to do this for your task. Anyway, "
            elif messages[-1]["role"] == "function" and messages[-1]["content"] != "No output":
                prompt += "Given the output of the code I just ran, "
            elif messages[-1]["role"] == "function" and messages[-1]["content"] == "No output":
                prompt += "Given the fact that the code I just ran produced no output, "

            if self.debug_mode:
                # we have to use builtins bizarrely! because rich.print interprets "[INST]" as something meaningful
                import builtins
                builtins.print("TEXT PROMPT SEND TO LLM:\n", prompt)

            # Run Code-Llama

            response = self.llama_instance(
                prompt,
                stream=True,
                temperature=self.temperature,
                stop=["</s>"],
                max_tokens=750  # context window is set to 1800, messages are trimmed to 1000... 700 seems nice
            )

        # Initialize message, function call trackers, and active block
        self.messages.append({})
        in_function_call = False
        llama_function_call_finished = False
        self.active_block = None

        for chunk in response:
            if self.use_azure and ('choices' not in chunk or len(chunk['choices']) == 0):
                # Azure OpenAI Service may return empty chunk
                continue

            if self.local:
                if "content" not in messages[-1]:
                    # This is the first chunk. We'll need to capitalize it, because our prompt ends in a ", "
                    chunk["choices"][0]["text"] = chunk["choices"][0]["text"].capitalize()
                    # We'll also need to add "role: assistant", CodeLlama will not generate this
                    messages[-1]["role"] = "assistant"
                delta = {"content": chunk["choices"][0]["text"]}
            else:
                delta = chunk["choices"][0]["delta"]

            # Accumulate deltas into the last message in messages
            self.messages[-1] = merge_deltas(self.messages[-1], delta)

            # Check if we're in a function call
            if not self.local:
                condition = "function_call" in self.messages[-1]
            elif self.local:
                # Since Code-Llama can't call functions, we just check if we're in a code block.
                # This simply returns true if the number of "```" in the message is odd.
                if "content" in self.messages[-1]:
                    condition = self.messages[-1]["content"].count("```") % 2 == 1
                else:
                    # If it hasn't made "content" yet, we're certainly not in a function call.
                    condition = False
            
            if condition:
                # We are in a function call.

                # Check if we just entered a function call
                if in_function_call == False:

                    # If so, end the last block,
                    self.end_active_block()

                    # Print newline if it was just a code block or user message
                    # (this just looks nice)
                    last_role = self.messages[-2]["role"]
                    if last_role == "user" or last_role == "function":
                        # Modified by happyapplehorse ##########################################
                        # Original:
                        #print()
                        # Changed to:
                        pass
                        ########################################################################

                    # then create a new code block
                    # Modified by happyapplehorse ##########################################
                    # Original:
                    #self.active_block = CodeBlock()
                    # Changed to:
                    self.active_block = MyCodeBlock()
                    ########################################################################

                # Remember we're in a function_call
                in_function_call = True

                # Now let's parse the function's arguments:

                if not self.local:
                    # gpt-4
                    # Parse arguments and save to parsed_arguments, under function_call
                    if "arguments" in self.messages[-1]["function_call"]:
                        arguments = self.messages[-1]["function_call"]["arguments"]
                        new_parsed_arguments = parse_partial_json(arguments)
                        if new_parsed_arguments:
                            # Only overwrite what we have if it's not None (which means it failed to parse)
                            self.messages[-1]["function_call"][
                                "parsed_arguments"] = new_parsed_arguments

                elif self.local:
                    # Code-Llama
                    # Parse current code block and save to parsed_arguments, under function_call
                    if "content" in self.messages[-1]:

                        content = self.messages[-1]["content"]

                        if "```" in content:
                            # Split by "```" to get the last open code block
                            blocks = content.split("```")

                            current_code_block = blocks[-1]

                            lines = current_code_block.split("\n")

                            if content.strip() == "```":  # Hasn't outputted a language yet
                                language = None
                            else:
                                if lines[0] != "":
                                    language = lines[0].strip()
                                else:
                                    language = "python"
                                    # In anticipation of its dumbassery let's check if "pip" is in there
                                    if len(lines) > 1:
                                        if lines[1].startswith("pip"):
                                            language = "shell"

                            # Join all lines except for the language line
                            code = '\n'.join(lines[1:]).strip("` \n")

                            arguments = {"code": code}
                            if language:  # We only add this if we have it-- the second we have it, an interpreter gets fired up (I think? maybe I'm wrong)
                                if language == "bash":
                                    language = "shell"
                                arguments["language"] = language

                        # Code-Llama won't make a "function_call" property for us to store this under, so:
                        if "function_call" not in self.messages[-1]:
                            self.messages[-1]["function_call"] = {}

                        self.messages[-1]["function_call"]["parsed_arguments"] = arguments

            else:
                # We are not in a function call.

                # Check if we just left a function call
                if in_function_call == True:

                    if self.local:
                        # This is the same as when gpt-4 gives finish_reason as function_call.
                        # We have just finished a code block, so now we should run it.
                        llama_function_call_finished = True

                # Remember we're not in a function_call
                in_function_call = False

                # If there's no active block,
                if self.active_block == None:
                    # Create a message block
                    # Modified by happyapplehorse ##########################################
                    # Original:
                    #self.active_block = MessageBlock()
                    # Changed to:
                    self.active_block = MyMessageBlock()
                    ########################################################################

            # Update active_block
            self.active_block.update_from_message(self.messages[-1])

            # Check if we're finished
            if chunk["choices"][0]["finish_reason"] or llama_function_call_finished:
                if chunk["choices"][
                    0]["finish_reason"] == "function_call" or llama_function_call_finished:
                    # Time to call the function!
                    # (Because this is Open Interpreter, we only have one function.)

                    if self.debug_mode:
                        print("Running function:")
                        print(self.messages[-1])
                        print("---")

                    # Ask for user confirmation to run code
                    if self.auto_run == False:

                        # End the active block so you can run input() below it
                        # Save language and code so we can create a new block in a moment
                        self.active_block.end()
                        language = self.active_block.language
                        code = self.active_block.code

                        # Modified by happyapplehorse ##########################################
                        
                        # Original:
                        # Prompt user
                        #response = input("  Would you like to run this code? (y/n)\n\n  ")
                        #print("")  # <- Aesthetic choice

                        # Changed to:
                        response = yield self.messages[-1]

                        ########################################################################

                        if response.strip().lower() == "y":
                            # Create a new, identical block where the code will actually be run
                            # Modified by happyapplehorse ##########################################
                            # Original:
                            #self.active_block = CodeBlock()
                            # Changed to:
                            self.active_block = MyCodeBlock()
                            ########################################################################
                            self.active_block.language = language
                            self.active_block.code = code

                        else:
                            # User declined to run code.
                            self.active_block.end()
                            self.messages.append({
                                "role":
                                    "function",
                                "name":
                                    "run_code",
                                "content":
                                    "User decided not to run this code."
                            })
                            return self.messages[-1]

                    # If we couldn't parse its arguments, we need to try again.
                    if not self.local and "parsed_arguments" not in self.messages[-1]["function_call"]:
                        # After collecting some data via the below instruction to users,
                        # This is the most common failure pattern: https://github.com/KillianLucas/open-interpreter/issues/41

                        # print("> Function call could not be parsed.\n\nPlease open an issue on Github (openinterpreter.com, click Github) and paste the following:")
                        # print("\n", self.messages[-1]["function_call"], "\n")
                        # time.sleep(2)
                        # print("Informing the language model and continuing...")

                        # Since it can't really be fixed without something complex,
                        # let's just berate the LLM then go around again.

                        self.messages.append({
                            "role": "function",
                            "name": "run_code",
                            "content": """Your function call could not be parsed. Please use ONLY the `run_code` function, which takes two parameters: `code` and `language`. Your response should be formatted as a JSON."""
                        })

                        self.respond()
                        return self.messages[-1]

                    # Create or retrieve a Code Interpreter for this language
                    language = self.messages[-1]["function_call"]["parsed_arguments"][
                        "language"]
                    if language not in self.code_interpreters:
                        self.code_interpreters[language] = CodeInterpreter(language, self.debug_mode)
                    code_interpreter = self.code_interpreters[language]

                    # Let this Code Interpreter control the active_block
                    code_interpreter.active_block = self.active_block
                    code_interpreter.run()

                    # End the active_block
                    self.active_block.end()

                    # Append the output to messages
                    # Explicitly tell it if there was no output (sometimes "" = hallucinates output)
                    self.messages.append({
                        "role": "function",
                        "name": "run_code",
                        "content": self.active_block.output if self.active_block.output else "No output"
                    })

                    # Go around again
                    # Modified by happyapplehorse ##########################################
                    # Original:
                    #self.respond()
                    # Changed to:
                    out = yield from self.respond()
                    return out
                    ########################################################################

                if chunk["choices"][0]["finish_reason"] != "function_call":
                    # Done!

                    # Code Llama likes to output "###" at the end of every message for some reason
                    if self.local and "content" in self.messages[-1]:
                        self.messages[-1]["content"] = self.messages[-1]["content"].strip().rstrip("#")
                        self.active_block.update_from_message(self.messages[-1])
                        time.sleep(0.1)

                    self.active_block.end()
                    print("5555")
                    print(self.messages)
                    return self.messages[-1]

        # Modified by happyapplehorse ##########################################
        # Original:

        # Changed to:
        return self.messages[-1]
        ########################################################################


class MyMessageBlock(MessageBlock):
    def update_from_message(self, message: dict) -> None:
        pass


class MyCodeBlock(CodeBlock):
    def update_from_message(self, message: dict) -> None:
        if "function_call" in message and "parsed_arguments" in message["function_call"]:

            parsed_arguments = message["function_call"]["parsed_arguments"]

            if parsed_arguments != None:
                self.language = parsed_arguments.get("language")
                self.code = parsed_arguments.get("code")


def response_render(message: dict):
    if message is None:
        return "null"
    out = message.get("content") or ""
    out += "\n\n"
    command = message.get("function_call", {}).get("parsed_arguments", None)
    code = language = None
    if command is not None:
        language = command.get("language")
        code = command.get("code")
    if language and code:
        out += (
            f"I will execute \"{code}\" in \"{language}\""
            "\n\nWould you like to run this code? (y/n)\n"
            "You should inform the user about the code I intend to run, "
            "ask for his/her consent, and then precisely reply to me with either 'y' or 'n'."
        )
    return out

