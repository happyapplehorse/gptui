import bisect
import math

from ..utils.my_text import MyText as Text


class DashBoard:
    def __init__(self, app):
        self.app = app

    def dash_board_display(self, tokens_num_window: int, conversation_id: int | None = None):
        "Display the token's monitor in dashboard"
        
        def is_inside_segment(position: int, start_positions: list[int], end_positions:list[int]):
            # 使用 bisect 来找到 coord 应该插入的位置
            index = bisect.bisect_right(start_positions, position) - 1
            # 如果 index 为 -1，说明 coord 小于所有段的开始位置
            if index == -1:
                return False
            # 检查 coord 是否在找到的段内
            return start_positions[index] <= position <= end_positions[index]
        
        if conversation_id is None:
            conversation_id = self.app.openai.conversation_active
        conversation = self.app.openai.conversation_dict[conversation_id]
        display = self.app.query_one("#dash_board")
        height = display.content_size.height
        
        if tokens_num_window == 0:
            display.update(Text("ಠ_ಠ\n" * height, "yellow"))
            return
        
        tokens_num = conversation["openai_context"].tokens_num
        tokens_num_list = conversation["openai_context"].tokens_num_list
        bead_index_list = conversation["bead"]["positions"]
        bead_tokens_list = [sum(tokens_num_list[:index]) for index in bead_index_list]
        bead_length_list = conversation["bead"]["length"]

        tokens_proportion = tokens_num / tokens_num_window
        bead_positions_ratio_list_start = [num / tokens_num for num in bead_tokens_list]
        bead_length_ratio_list = [num / tokens_num for num in bead_length_list]
        bead_positions_ratio_list_end = [sum(i) for i in zip(bead_positions_ratio_list_start, bead_length_ratio_list)]
        indicator_content_left = []
        indicator_content_middle = []
        indicator_content_right = []
        # dashboard left
        if tokens_proportion < 1:
            indicator_tokens_num = math.floor(tokens_proportion * height)
            bead_positions_indicator_left_list_start = [math.ceil(height - indicator_tokens_num + i * indicator_tokens_num) for i in bead_positions_ratio_list_start]
            bead_positions_indicator_left_list_end = [math.ceil(height - indicator_tokens_num + i * indicator_tokens_num) for i in bead_positions_ratio_list_end]
            for position in range(height):
                if position <= height - indicator_tokens_num:
                    indicator_content_left.append(Text(" "))
                else:
                    status = is_inside_segment(position, start_positions=bead_positions_indicator_left_list_start, end_positions=bead_positions_indicator_left_list_end)
                    if status is True:
                        indicator_content_left.append(Text(u'\u00b7', "yellow"))
                    else:
                        indicator_content_left.append(Text("-", "green"))
        else:
            indicator_tokens_num = math.ceil(1 / tokens_proportion * height)
            bead_positions_indicator_left_list_start = [math.floor(i * indicator_tokens_num) for i in bead_positions_ratio_list_start]
            bead_positions_indicator_left_list_end = [math.floor(i * indicator_tokens_num) for i in bead_positions_ratio_list_end]
            for position in range(height):
                if position <= indicator_tokens_num:
                    status = is_inside_segment(position, start_positions=bead_positions_indicator_left_list_start, end_positions=bead_positions_indicator_left_list_end)
                    if status is True:
                        indicator_content_left.append(Text(u'\u00b7', "yellow"))
                    else:
                        indicator_content_left.append(Text("-", "green"))
                else:
                    indicator_content_left.append(Text(" "))
        
        # dashboard middle
        if tokens_proportion < 1:
            indicator_content_middle = indicator_content_left
        else:
            bead_positions_indicator_middle_list_start = [round(i * height) for i in bead_positions_ratio_list_start]
            bead_positions_indicator_middle_list_end = [round(i * height) for i in bead_positions_ratio_list_end]
            for position in range(height):
                status = is_inside_segment(position, start_positions=bead_positions_indicator_middle_list_start, end_positions=bead_positions_indicator_middle_list_end)
                if status is True:
                    indicator_content_middle.append(Text(u'\u00b7', "yellow"))
                else:
                    indicator_content_middle.append(Text("-", "green"))
        
        # dashboard right
        if tokens_proportion < 1:
            indicator_content_right = indicator_content_left
        else:
            bead_positions_indicator_right_list_start = [height - round((tokens_num - i) / tokens_num_window * height) for i in bead_tokens_list]
            bead_tokens_list_end = [sum(i) for i in zip(bead_tokens_list, bead_length_list)]
            bead_positions_indicator_right_list_end = [height - round((tokens_num - i) / tokens_num_window * height) for i in bead_tokens_list_end]
            for position in range(height):
                status = is_inside_segment(position, start_positions=bead_positions_indicator_right_list_start, end_positions=bead_positions_indicator_right_list_end)
                if status is True:
                    indicator_content_right.append(Text(u'\u00b7', "yellow"))
                else:
                    indicator_content_right.append(Text("-", "green"))
        indicator_content = Text('')

        for i in range(height):
            indicator_content = indicator_content + indicator_content_left[i] + indicator_content_middle[i] + indicator_content_middle[i] + Text('\n')
        display.update(indicator_content)
