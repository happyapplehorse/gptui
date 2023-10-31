import logging
import math
import random
import textwrap

from rich.text import TextType

from .wink_wink import Happy, Apple
from .mywidgets import MyChatWindow
from ..utils.safe_iterate import safe_send
from ..utils.my_text import MyText as Text


gptui_logger = logging.getLogger("gptui_logger")


class FunZone(Happy):
    
    def __init__(self, displayer: MyChatWindow):
        self.displayer = displayer

    @property
    def canvas_width(self) -> int:
        return self.displayer.content_size.width
    
    @property
    def canvas_height(self) -> int:
        return self.displayer.content_size.height

    def refresh(self, content: str | Text, apple_width: int, apple_height: int):
        top_margin = (self.canvas_height - apple_height) // 2
        text = Text("\n" * top_margin)
        if isinstance(content, str):
            content = Text(content)
        content_lines = content.split()
        for line in content_lines:
            line.align("center", self.canvas_width)
        content_after_center = Text("\n").join(content_lines)
        text.append_text(content_after_center)
        self.displayer.update(text, scroll_to_end=False)


class JustBeing(Apple):
    def __init__(self):
        self.text = Text(
            """
            I am not your AI assistant.
            I talk when I want to.
            I do what I want to do.
            I am just a being, here and now.
            """,
            "italic",
        )
        
    def frame(self, inp) -> tuple[bool, tuple[float, TextType]]:
        return False, (0, self.text)

    @property
    def canvas_width(self) -> int:
        return 70
    
    @property
    def canvas_height(self) -> int:
        return 3


class BombBoom(Apple):
    def __init__(self):
        self.frame_gen = self._frame()
        self.frame_gen.send(None)
        self.nums = [
            Text(textwrap.dedent(
                    """
                         999999999     
                       99:::::::::99   
                     99:::::::::::::99 
                    9::::::99999::::::9
                    9:::::9     9:::::9
                    9:::::9     9:::::9
                     9:::::99999::::::9
                      99::::::::::::::9
                        99999::::::::9 
                             9::::::9  
                            9::::::9   
                           9::::::9    
                          9::::::9     
                         9::::::9      
                        9::::::9       
                       99999999        
                    """
                ), "green"
            ),
            Text(textwrap.dedent(
                    """
                         888888888     
                       88:::::::::88   
                     88:::::::::::::88 
                    8::::::88888::::::8
                    8:::::8     8:::::8
                    8:::::8     8:::::8
                     8:::::88888:::::8 
                      8:::::::::::::8  
                     8:::::88888:::::8 
                    8:::::8     8:::::8
                    8:::::8     8:::::8
                    8:::::8     8:::::8
                    8::::::88888::::::8
                     88:::::::::::::88 
                       88:::::::::88   
                         888888888     
                    """
                ), "green"
            ),
            Text(textwrap.dedent(
                    """
                    77777777777777777777
                    7::::::::::::::::::7
                    7::::::::::::::::::7
                    777777777777:::::::7
                               7::::::7 
                              7::::::7  
                             7::::::7   
                            7::::::7    
                           7::::::7     
                          7::::::7      
                         7::::::7       
                        7::::::7        
                       7::::::7         
                      7::::::7          
                     7::::::7           
                    77777777            
                    """
                ), "green"
            ),
            Text(textwrap.dedent(
                    """
                            66666666   
                           6::::::6    
                          6::::::6     
                         6::::::6      
                        6::::::6       
                       6::::::6        
                      6::::::6         
                     6::::::::66666    
                    6::::::::::::::66  
                    6::::::66666:::::6 
                    6:::::6     6:::::6
                    6:::::6     6:::::6
                    6::::::66666::::::6
                     66:::::::::::::66 
                       66:::::::::66   
                         666666666     
                    """
                ), "yellow"
            ),
            Text(textwrap.dedent(
                    """
                    555555555555555555 
                    5::::::::::::::::5 
                    5::::::::::::::::5 
                    5:::::555555555555 
                    5:::::5            
                    5:::::5            
                    5:::::5555555555   
                    5:::::::::::::::5  
                    555555555555:::::5 
                                5:::::5
                                5:::::5
                    5555555     5:::::5
                    5::::::55555::::::5
                     55:::::::::::::55 
                       55:::::::::55   
                         555555555     
                    """
                ), "yellow"
            ),
            Text(textwrap.dedent(
                    """
                           444444444  
                          4::::::::4  
                         4:::::::::4  
                        4::::44::::4  
                       4::::4 4::::4  
                      4::::4  4::::4  
                     4::::4   4::::4  
                    4::::444444::::444
                    4::::::::::::::::4
                    4444444444:::::444
                              4::::4  
                              4::::4  
                              4::::4  
                            44::::::44
                            4::::::::4
                            4444444444
                    """
                ), "yellow"
            ),
            Text(textwrap.dedent(
                    """
                     333333333333333   
                    3:::::::::::::::33 
                    3::::::33333::::::3
                    3333333     3:::::3
                                3:::::3
                                3:::::3
                        33333333:::::3 
                        3:::::::::::3  
                        33333333:::::3 
                                3:::::3
                                3:::::3
                                3:::::3
                    3333333     3:::::3
                    3::::::33333::::::3
                    3:::::::::::::::33 
                     333333333333333   
                    """
                ), "red"
            ),
            Text(textwrap.dedent(
                    """
                     222222222222222    
                    2:::::::::::::::22  
                    2::::::222222:::::2 
                    2222222     2:::::2 
                                2:::::2 
                                2:::::2 
                             2222::::2  
                        22222::::::22   
                      22::::::::222     
                     2:::::22222        
                    2:::::2             
                    2:::::2             
                    2:::::2       222222
                    2::::::2222222:::::2
                    2::::::::::::::::::2
                    22222222222222222222
                    """
                ), "red"
            ),
            Text(textwrap.dedent(
                    """
                      1111111   
                     1::::::1   
                    1:::::::1   
                    111:::::1   
                       1::::1   
                       1::::1   
                       1::::1   
                       1::::l   
                       1::::l   
                       1::::l   
                       1::::l   
                       1::::l   
                    111::::::111
                    1::::::::::1
                    1::::::::::1
                    111111111111
                    """
                ), "red"
            ),
        ]
        self.boom = textwrap.dedent(
            """
            XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX 
            X X                           X X
            X   X                       X   X
            X     X                   X     X
            X       X               X       X
            X         X           X         X
            X           X       X           X
            X             x   X             X
            X               X               X
            X             X    X            X
            X           X        X          X
            X         X            X        X
            X       X                X      X
            X     X                    X    X
            X   X                        X  X
            X X                            XX
            XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
            """
        )


    def _frame(self):
        answer = random.randint(1, 3)
        inp = yield
        if inp != 0:
            if inp == answer:
                return (0.1, Text(""))
            else:
                for i in range(20):
                    if i % 2 == 0:
                        inp = yield (0.1, Text(self.boom))
                    else:
                        inp = yield (0.1, Text(self.boom, "reverse"))
                    if inp == answer:
                        return (0.1, Text(""))
        for i in self.nums:
            inp = yield (0.5, i)
            if inp != 0:
                if inp == answer:
                    return (0.1, Text(""))
                else:
                    break
        for i in range(20):
            if i % 2 == 0:
                inp = yield (0.1, Text(self.boom))
            else:
                inp = yield (0.1, Text(self.boom, "reverse"))

    def frame(self, inp) -> tuple[bool, tuple[float, TextType]]:
        if inp == "green":
            user_inp = 1
        elif inp == "yellow":
            user_inp = 2
        elif inp == "red":
            user_inp = 3
        else:
            user_inp = 0
        status, result = safe_send(self.frame_gen, user_inp)
        if status == "OK":
            return True, result
        else:
            return False, result

    @property
    def canvas_width(self) -> int:
        return 70
    
    @property
    def canvas_height(self) -> int:
        return 16


class RotatingCube(Apple):

    def __init__(self, happy_width: int = 40, happy_height: int = 80):
        # The width and height of the apple canvas
        self.height = happy_height
        self.width = happy_width
        # A buffer to store the Z coordinate (depth) for each pixel on the canvas
        self.z_buffer = [0] * (self.width * self.height)
        # A buffer to store the character to be drawn for each pixel on the canvas
        self.buffer = [' '] * (self.width * self.height)
        # Horizontal offset for translating the cube's position along the X-axis
        self.horizontal_offset = 0
        # The speed by which the cube increments its position in each iteration
        # The density of points on the surface
        self.increment_speed = 0.6
        # The width of the cube in the 3D coordinate system
        self.cube_width = min(self.width, self.height) // 2
        # A constant to control the scaling factor for projecting 3D points onto the 2D screen
        self.K1 = self.cube_width * 2
        # Distance of the camera from the origin of the 3D coordinate system
        self.distance_from_cam = self.cube_width * 5

        self.frame_gen = self._frame()
        self.frame_gen.send(None)

    @property
    def canvas_width(self) -> int:
        return self.width
    
    @property
    def canvas_height(self) -> int:
        return self.height

    def frame(self, inp) -> tuple[bool, tuple[float, TextType]]:
        status, result = safe_send(self.frame_gen, inp)
        if status == "OK":
            return True, result
        else:
            return False, result
    
    def _frame(self):
        a = random.uniform(0, 2 * math.pi)
        b = random.uniform(0, 2 * math.pi)
        c = random.uniform(0, 2 * math.pi)
        while True:
            yield (0.1, self._draw_cube(a, b, c))
            a += 0.01
            b += 0.02
            c += 0.03

    def _float_range(self, start, stop, step):
        while start < stop:
            yield start
            start += step
    
    def _calculate_x(self, i, j, k, A, B, C):
        return j * math.sin(A) * math.sin(B) * math.cos(C) - k * math.cos(A) * math.sin(B) * math.cos(C) + j * math.cos(A) * math.sin(C) + k * math.sin(A) * math.sin(C) + i * math.cos(B) * math.cos(C)

    def _calculate_y(self, i, j, k, A, B, C):
        return j * math.cos(A) * math.cos(C) + k * math.sin(A) * math.cos(C) - j * math.sin(A) * math.sin(B) * math.sin(C) + k * math.cos(A) * math.sin(B) * math.sin(C) - i * math.cos(B) * math.sin(C)

    def _calculate_z(self, i, j, k, A, B):
        return k * math.cos(A) * math.cos(B) - j * math.sin(A) * math.cos(B) + i * math.sin(B)

    def _calculate_for_surface(self, cube_x, cube_y, cube_z, ch, A, B, C):
        x = self._calculate_x(cube_x, cube_y, cube_z, A, B, C)
        y = self._calculate_y(cube_x, cube_y, cube_z, A, B, C)
        z = self._calculate_z(cube_x, cube_y, cube_z, A, B) + self.distance_from_cam

        # One Over Z
        ooz = 1 / z
        width = self.width
        height = self.height
        K1 = self.K1

        xp = int(width / 2 + self.horizontal_offset + K1 * ooz * x * 2)
        yp = int(height / 2 + K1 * ooz * y)

        idx = xp + yp * width

        if 0 <= idx < width * height:
            if ooz > self.z_buffer[idx]:
                self.z_buffer[idx] = ooz
                self.buffer[idx] = ch

    def _draw_cube(self, A, B, C):

        for i in range(len(self.buffer)):
            self.buffer[i] = ' '
            self.z_buffer[i] = 0
        
        cube_width = self.cube_width
        increment_speed = self.increment_speed

        for cube_x in self._float_range(-cube_width, cube_width, increment_speed):
            for cube_y in self._float_range(-cube_width, cube_width, increment_speed):
                self._calculate_for_surface(cube_x, cube_y, -cube_width, '?', A, B, C)
                self._calculate_for_surface(cube_width, cube_y, cube_x, '*', A, B, C)
                self._calculate_for_surface(-cube_width, cube_y, -cube_x, '=', A, B, C)
                self._calculate_for_surface(-cube_x, cube_y, cube_width, '#', A, B, C)
                self._calculate_for_surface(cube_x, -cube_width, -cube_y, '!', A, B, C)
                self._calculate_for_surface(cube_x, cube_width, cube_y, '+', A, B, C)

        lines = []
        for i in range(self.height):
            line = ''.join(self.buffer[i * self.width : (i + 1) * self.width])
            lines.append(line)
        buffer_str = '\n'.join(lines)
        return buffer_str

