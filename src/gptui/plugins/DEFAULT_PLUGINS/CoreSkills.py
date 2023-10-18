import datetime
import logging

import geocoder
from semantic_kernel.orchestration.sk_context import SKContext
from semantic_kernel.sk_pydantic import PydanticField
from semantic_kernel.skill_definition import sk_function, sk_function_context_parameter

from gptui.gptui_kernel.manager import auto_init_params


gptui_logger = logging.getLogger("gptui_logger")


class TimeSkill(PydanticField):

    @sk_function(description="Get the current date and time in the local time zone")
    def now(self) -> str:
        """
        Get the current date and time in the local time zone"

        Example:
            {{time.now}} => Sunday, January 12, 2031 9:15 PM
        """
        now = datetime.datetime.now()
        return now.strftime("%A, %B %d, %Y %I:%M %p")


class LocationSkill:
    def __init__(self, manager):
        self.manager = manager
    
    @auto_init_params("0")
    @classmethod
    def get_init_params(cls, manager) -> tuple:
        return (manager,)

    @sk_function(description="Get the user's city")
    def city(self) -> str:
        config = self.manager.client.config
        city = config.get("location_city")
        if not city:
            city = geocoder.ip('me').city
        return str(city)


class MathSkill(PydanticField):

    @sk_function(
        description="Calculate addition, subtraction, multiplication, and division",
        name="calculate",
    )
    @sk_function_context_parameter(
        name="first_number",
        description="The first number",
    )
    @sk_function_context_parameter(
        name="second_number",
        description="The second number",
    )
    @sk_function_context_parameter(
        name="operation",
        description="The operation to be performed. Options: ['addition', 'subtraction', 'multiplication', 'division']",
    )
    def calculate(self, context: SKContext) -> str:
        first_num = context["first_number"]
        second_num = context["second_number"]
        operation = context["operation"]

        try:
            first_num = float(first_num)
            second_num = float(second_num)
        except ValueError:
            return "The values provided is not in numeric format."
        
        if operation not in ['addition', 'subtraction', 'multiplication', 'division']:
            return "The provided operation name is incorrect. It must be one of 'addition', 'subtraction', 'multiplication', or 'division'"

        if operation == 'addition':
            result = first_num + second_num
        elif operation == 'subtraction':
            result = first_num - second_num
        elif operation == 'multiplication':
            result = first_num * second_num
        else:
            result = first_num / second_num
        
        return str(result)
