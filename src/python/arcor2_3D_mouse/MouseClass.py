import pyspacemouse


class MouseClass:
    # Mouse commands

    # TODO OOOOOOOOOOOOOOOOOOOOO sem treba dat detekciu long clicku -> mozno by sa to hodilo na nejake upravy
    # TODO   #Add raise exepction here
    def __init__(self) -> None:
        self.mouse_connect()

    def mouse_connect(self) -> None:
        return pyspacemouse.open()

    # [t,x,y,z,roll,pitch,yaw,button]
    def mouse_read(self) -> pyspacemouse.pyspacemouse.SpaceNavigator:
        return pyspacemouse.read()

    lb_pressed: bool = False
    rb_pressed: bool = False
    r_dir_moved: bool = False
    l_dir_moved: bool = False
    t_dir_moved: bool = False
    mouse_menu_offset: float = 0.1

    # Hmmmm, tu by mohol byt problem ak by som potom nedaval ten read, ale to nie je pravdepodobne
    # UT
    def mouse_button_left_pressed(self, g_mouse_reading: pyspacemouse.pyspacemouse.SpaceNavigator) -> bool:
        if g_mouse_reading.buttons[0] == 1:
            if self.lb_pressed:
                return False
            else:
                self.lb_pressed = True
                return True
        else:
            self.lb_pressed = False
            return False

    # UT
    def mouse_button_rigth_pressed(self, g_mouse_reading: pyspacemouse.pyspacemouse.SpaceNavigator) -> bool:
        if g_mouse_reading.buttons[1] == 1:
            if self.rb_pressed:
                return False
            else:
                self.rb_pressed = True
                return True
        else:
            self.rb_pressed = False
            return False

    # UT
    # Tu to mozno prepisat na rotation
    def menu_left_movement(self, g_mouse_reading: pyspacemouse.pyspacemouse.SpaceNavigator) -> bool:
        if g_mouse_reading.x + self.mouse_menu_offset < 0:
            if self.l_dir_moved:
                return False
            else:
                self.l_dir_moved = True
                return True
        else:
            self.l_dir_moved = False
            return False

    def menu_rigth_movement(self, g_mouse_reading: pyspacemouse.pyspacemouse.SpaceNavigator) -> bool:
        if g_mouse_reading.x - self.mouse_menu_offset > 0:
            if self.r_dir_moved:
                return False
            else:
                self.r_dir_moved = True
                return True
        else:
            self.r_dir_moved = False
            return False

    def menu_top_movement(self, g_mouse_reading: pyspacemouse.pyspacemouse.SpaceNavigator) -> bool:
        if g_mouse_reading.y - self.mouse_menu_offset > 0:
            if self.t_dir_moved:
                return False
            else:
                self.t_dir_moved = True
                return True
        else:
            self.t_dir_moved = False
            return False
