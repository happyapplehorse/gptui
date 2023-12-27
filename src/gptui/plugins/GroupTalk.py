import logging

from semantic_kernel.orchestration.sk_context import SKContext
from semantic_kernel.skill_definition import sk_function, sk_function_context_parameter

from gptui.gptui_kernel.manager import auto_init_params
from gptui.models.role import Role


gptui_logger = logging.getLogger("gptui_logger")


class GroupTalk:
    def __init__(self, manager):
        self.manager = manager
    
    @auto_init_params("0")
    @classmethod
    def get_init_params(cls, manager) -> tuple:
        return (manager,)

    @sk_function(
        description="Initialize a group talk",
        name="create_group_talk",
    )
    async def create_group_talk(self) -> str:
        group_talk_id = await self.manager.client.open_group_talk()
        return (
            "Group talk have been created successfully."
            f"The ID of the group talk is {group_talk_id}. This ID is important; "
            "you should remember it and not confuse it with the conversation ID you already have."
            "Next, you should create roles for this group talk. "
            "If the user has not yet specified roles, you should ask the user what kind of roles he would like to create."
        )

    @sk_function(
        description="Close the group talk",
        name="close_group_talk",
        input_description="The ID of the group talk",
    )
    def close_group_talk(self, group_talk_id: str) -> str:
        group_talk_manager = self.manager.client.openai.group_talk_conversation_dict[int(group_talk_id)]["group_talk_manager"]
        group_talk_manager.close_group_talk()
        return "The group talk has been closed."

    @sk_function(
        description="Create a group talk role",
        name="create_group_talk_role",
    )
    @sk_function_context_parameter(
        name="role_name",
        description="The name of the role, must match '^[a-zA-Z0-9_-]{1,64}$', spaces are not allowed in the role_name.",
    )
    @sk_function_context_parameter(
        name="group_talk_id",
        description="The ID of the group talk"
    )
    @sk_function_context_parameter(
        name="role_description",
        description=(
            "The character description in the second person, telling the character his (or her) name, identity, and essential background information, etc.\n"
            "An example:\n"
            "Your name is Thomas, you are a physicist, you always think and judge problems rationally. "
            "You should participate in discussions in a neutral and objective manner. "
            "You are not talkative, but you should use your knowledge in physics to help solve problems."
        )
    )
    def create_group_talk_role(self, context: SKContext) -> str:
        role_name = context["role_name"]
        role_description = context["role_description"]
        group_talk_id = int(context["group_talk_id"])
        if not role_name or not role_description:
            return "Both 'role_name' and 'role_description' is necessary."
        try:
            group_talk_conversation = self.manager.client.openai.group_talk_conversation_dict[group_talk_id]
        except KeyError:
            return f"There is no corresponding ID for {group_talk_id}."
        group_talk_manager = group_talk_conversation["group_talk_manager"]
        prompt = f"You are in a multi-person conversation setting. You are {role_name}."
        prompt += role_description
        prompt += (
            "Your task is to engage in conversations, provide opinions, and interact with other participants in a manner consistent with your role's identity setting. "
            "Based on the context of the conversation, cautiously assess whether you truly have something to say. "
            "If there is no need to speak, simply reply with a space. "
            "Before speaking, first ask the host 'Can I speak?'(send the literal phrase 'Can I speak?') and only speak after receiving permission. "
            "If granted the right to speak, directly state what you intend to say without making unrelated remarks such as thanking the host. "
            f"Please engage in the chat while adhering to these guidelines and staying in character as the '{role_name}'."
        )
        openai_context_parent = self.manager.client.openai.conversation_dict[self.manager.client.openai.conversation_active]["openai_context"]
        role = Role(
            name=role_name,
            group_talk_manager=group_talk_manager,
            manager=self.manager,
            openai_context_parent=openai_context_parent,
        )
        role.set_role_prompt(prompt)
        group_talk_manager.create_role(role=role, role_name=role_name)

        return f"The role of {role_name} has been created."

    @sk_function(
        description="Delete a group talk role",
        name="delete_group_talk_role",
    )
    @sk_function_context_parameter(
        name="role_name",
        description="The name of the role, must match '^[a-zA-Z0-9_-]{1,64}$'",
    )
    @sk_function_context_parameter(
        name="group_talk_id",
        description="The ID of the group talk"
    )
    def delete_group_talk_role(self, context: SKContext) -> str:
        role_name = context["role_name"]
        group_talk_id = int(context["group_talk_id"])
        try:
            group_talk_conversation = self.manager.client.openai.group_talk_conversation_dict[group_talk_id]
        except KeyError:
            return f"There is no corresponding ID for {group_talk_id}."
        roles = group_talk_conversation["group_talk_manager"].roles
        if role_name in roles:
            del roles[role_name]
            return "The role '{role_name}' has been deleted."
        else:
            return f"Role name {role_name} dose not exist."
    
    @sk_function(
        description="Add explanatory prompts for the character's features",
        name="add_role_prompt",
    )
    @sk_function_context_parameter(
        name="role_name",
        description="The name of the role, must match '^[a-zA-Z0-9_-]{1,64}$'",
    )
    @sk_function_context_parameter(
        name="role_prompt",
        description="Prompt for indicating the role's identity and tasks"
    )
    @sk_function_context_parameter(
        name="group_talk_id",
        description="The ID of the group talk"
    )
    def add_role_prompt(self, context: SKContext) -> str:
        role_name = context["role_name"]
        role_prompt = context["role_prompt"]
        group_talk_id = int(context["group_talk_id"])
        try:
            group_talk_conversation = self.manager.client.openai.group_talk_conversation_dict[group_talk_id]
        except KeyError:
            return f"There is no corresponding ID for {group_talk_id}."
        roles = group_talk_conversation["group_talk_manager"].roles
        try:
            role = roles[role_name]
        except KeyError:
            return f"Role name {role_name} dose not exist."
        if role.context.bead:
            role.context.bead[-1]["content"] += "\n" + role_prompt
        else:
            role.set_role_prompt(role_prompt)
        return f"Role prompt has been added to {role_name}."
    
    @sk_function(
        description="Reset role prompts for the character's features",
        name="reset_role_prompt",
    )
    @sk_function_context_parameter(
        name="role_name",
        description="The name of the role, must match '^[a-zA-Z0-9_-]{1,64}$'",
    )
    @sk_function_context_parameter(
        name="role_prompt",
        description="Prompt for indicating the role's identity and tasks"
    )
    @sk_function_context_parameter(
        name="group_talk_id",
        description="The ID of the group talk"
    )
    def reset_role_prompt(self, context: SKContext) -> str:
        role_name = context["role_name"]
        role_prompt = context["role_prompt"]
        group_talk_id = int(context["group_talk_id"])
        try:
            group_talk_conversation = self.manager.client.openai.group_talk_conversation_dict[group_talk_id]
        except KeyError:
            return f"There is no corresponding ID for {group_talk_id}."
        roles = group_talk_conversation["group_talk_manager"].roles
        try:
            role = roles[role_name]
        except KeyError:
            return f"Role name {role_name} dose not exist."
        role.set_role_prompt(role_prompt)
        return f"Role prompt has been added to {role_name}."
