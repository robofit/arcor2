import pyspacemouse
from pyspacemouse import SpaceNavigator

from arcor2.exceptions import Arcor2Exception


class MouseConnectionException(Arcor2Exception):
    pass


class MouseReader:
    def __init__(self) -> None:
        self.mouse_connect()

    def mouse_connect(self) -> None:
        try:
            return pyspacemouse.open()
        except Exception:
            raise MouseConnectionException

    # [t,x,y,z,roll,pitch,yaw,button]
    def mouse_read(self) -> SpaceNavigator:
        return pyspacemouse.read()


class MouseFunc:
    lb_pressed: bool = False
    rb_pressed: bool = False
    r_dir_moved: bool = False
    l_dir_moved: bool = False
    t_dir_moved: bool = False
    mouse_menu_offset: float = 0.1

    def turn_format(self, g_list) -> SpaceNavigator:
        return SpaceNavigator(
            0,
            g_list[0].value,
            g_list[1].value,
            g_list[2].value,
            g_list[3].value,
            g_list[4].value,
            g_list[5].value,
            [g_list[6].value, g_list[7].value],
        )

    def mouse_button_left_pressed(self, g_mouse_reading: SpaceNavigator) -> bool:
        if g_mouse_reading.buttons[0] == 1:
            if self.lb_pressed:
                return False
            else:
                self.lb_pressed = True
                return True
        else:
            self.lb_pressed = False
            return False

    def mouse_button_rigth_pressed(self, g_mouse_reading: SpaceNavigator) -> bool:
        if g_mouse_reading.buttons[1] == 1:
            if self.rb_pressed:
                return False
            else:
                self.rb_pressed = True
                return True
        else:
            self.rb_pressed = False
            return False

    def menu_left_movement(self, g_mouse_reading: SpaceNavigator) -> bool:
        if g_mouse_reading.x + self.mouse_menu_offset < 0:
            if self.l_dir_moved:
                return False
            else:
                self.l_dir_moved = True
                return True
        else:
            self.l_dir_moved = False
            return False

    def menu_rigth_movement(self, g_mouse_reading: SpaceNavigator) -> bool:
        if g_mouse_reading.x - self.mouse_menu_offset > 0:
            if self.r_dir_moved:
                return False
            else:
                self.r_dir_moved = True
                return True
        else:
            self.r_dir_moved = False
            return False

    def menu_top_movement(self, g_mouse_reading: SpaceNavigator) -> bool:
        if g_mouse_reading.y - self.mouse_menu_offset > 0:
            if self.t_dir_moved:
                return False
            else:
                self.t_dir_moved = True
                return True
        else:
            self.t_dir_moved = False
            return False
