import copy
from dataclasses import dataclass, field
from typing import Literal

from .utils.tokens_num import tokens_num_from_chat_context


@dataclass
class Context:
    chat_context: list[dict] | None = None
    id: str | int | None = None

    @property
    def chat_context_copy(self) -> list:
        chat_context = self.chat_context
        if chat_context is None:
            raise ValueError("Field 'chat_context' have not been set.")
        return copy.deepcopy(chat_context)


@dataclass
class OpenaiContext(Context):
    parameters: dict = field(default_factory=dict)
    max_sending_tokens_num: int | None = None
    chat_context_saver: Literal["outer", "inner"] | None = None
    chat_context_saver_for_sending: Literal["outer", "inner"] | None = None
    plugins: list = field(default_factory=list)
    
    def __post_init__(self, *args, **kwargs):
        self._tokens_num_list = []
        self._tokens_num_model = self.parameters.get("model")

    @property
    def tokens_num_list(self) -> list:
        if self.chat_context is None:
            self._tokens_num_list = []
            return self._tokens_num_list
        model = self.parameters.get("model")
        if model is None:
            raise ValueError("Parameter 'model' have not been set.")
        if model != self._tokens_num_model:
            self._tokens_num_list = [tokens_num_from_chat_context([message], model=model) for message in self.chat_context]
            self._tokens_num_model = model
            return self._tokens_num_list
        if len(self.chat_context) == len(self._tokens_num_list):
            return self._tokens_num_list
        elif len(self.chat_context) < len(self._tokens_num_list):
            self._tokens_num_list = [tokens_num_from_chat_context([message], model=model) for message in self.chat_context]
            return self._tokens_num_list
        else:
            tokens_num_list = [tokens_num_from_chat_context([message], model=model) for message in self.chat_context[len(self._tokens_num_list):]]
            self._tokens_num_list.extend(tokens_num_list)
            return self._tokens_num_list
        
    @property
    def tokens_num(self) -> int | None:
        if self.chat_context is None:
            return None
        return sum(self.tokens_num_list)

    def chat_context_append(self, message: dict, tokens_num_update: bool = True) -> None:
        """
        Write chat message to the chat_context, automatically calculate and update the number of tokens.
        If the number of tokens is not needed or real-time calculation of tokens is not required,
        you can set tokens__num_update to False, or directly manipulate the 'chat_context' attribute.
        """
        if self.chat_context is None:
            self.chat_context = []
        self.chat_context.append(message)
        if tokens_num_update is True:
            model = self.parameters.get("model")
            if model is not None:
                tokens_num = tokens_num_from_chat_context([message], model=model)
                self._tokens_num_list.append(tokens_num)

    def chat_context_pop(self, pop_index: int = -1) -> dict:
        "Pop a message from chat context, and delete the correponding tokens num in _tokens_num_list."
        self._tokens_num_list.pop(pop_index)
        if self.chat_context is None:
            raise ValueError(f"Field 'chat_context' has not been set.")
        return self.chat_context.pop(pop_index)

    
    def __deepcopy__(self, memo):

        def dose_only_read(attr) -> bool:
            if attr is None:
                return False
            if getattr(attr, 'fset', None) is None:
                return True
            else:
                return False
        
        if id(self) in memo:
            return memo[id(self)]

        new_instance = self.__class__.__new__(self.__class__)
        
        for k in dir(self):
            attr = getattr(self, k)
            if not k.startswith("__") and not callable(attr) and not dose_only_read(getattr(self.__class__, k, None)) and k != "plugins":
                setattr(new_instance, k, copy.deepcopy(attr, memo))

        setattr(new_instance, "plugins", copy.copy(self.plugins))

        memo[id(self)] = new_instance

        return new_instance
