from multiprocessing import Queue
from queue import Empty

import pyspacemouse
from pyspacemouse import SpaceNavigator

from arcor2.exceptions import Arcor2Exception


class MouseConnectionException(Arcor2Exception):
    """Custom exception type.

    This exception is raised when a connecting to mouse device fails.
    """

    pass


class MouseReadingException(Arcor2Exception):
    """Custom exception type.

    This exception is raised when a Queue reading data from mouse fails.
    """

    pass


class MouseReader:
    """Class that is used by process that reads mouse input from device."""

    def __init__(self) -> None:
        self._mouse_connect()

    def _mouse_connect(self) -> None:
        """Tries to open connection to the device.

        Raises:
            MouseConnectionException

        :return:
        """
        try:
            return pyspacemouse.open()
        except OSError:
            raise MouseConnectionException

    def mouse_read(self) -> SpaceNavigator:
        """Reads device input.

        :return: mouse input
        """
        return pyspacemouse.read()


class MouseFunc:
    """Class to support working with mouse.

    Class that stores methods that turn raw mouse input to user actions
    """

    def __init__(self, g_request_queue: Queue, g_receive_queue: Queue) -> None:
        """Init method.

        :param g_request_queue: queue used for writing request
        :param g_receive_queue: queue used for receiving readings from mouse
        :return:
        """
        self.request_queue: Queue = g_request_queue
        self.receive_queue: Queue = g_receive_queue
        self.lb_pressed: bool = False
        self.rb_pressed: bool = False
        self.r_dir_moved: bool = False
        self.l_dir_moved: bool = False
        self.t_dir_moved: bool = False
        self.mouse_menu_offset: float = 0.1

    def request_reading(self) -> SpaceNavigator:
        """Reads input from mouse.

            Uses request_queue(Queue) to request input, by writing any value
            to it. Then it waits for response from process. If waiting is
            longer than set timeout, it raises an exception.

        Raises:
            MouseReadingException

        :return: mouse input
        """
        try:
            self.request_queue.put(True)
            reading = self.receive_queue.get(timeout=1)
            return reading
        except Empty:
            raise MouseReadingException("Failed to read values from Queue")

    def mouse_button_left_pressed(self, g_mouse_reading: SpaceNavigator) -> bool:
        """Checks if user has pressed left mouse button.

        Returns True only if button was previously not pressed and is now.

        :param g_mouse_reading: mouse input

        :return: if button was pressed return True, else False
        """
        if g_mouse_reading.buttons[0] == 1:
            if self.lb_pressed:
                return False
            else:
                self.lb_pressed = True
                return True
        else:
            self.lb_pressed = False
            return False

    def mouse_button_right_pressed(self, g_mouse_reading: SpaceNavigator) -> bool:
        """Checks if user has pressed right mouse button.

        Returns True only if button was previously not pressed and is now.

        :param g_mouse_reading: mouse input

        :return: if button was pressed return True, else False
        """
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
        """Checks if user has moved mouse to the left.

        Returns True only if mouse is moved to the left and previously was not.
        This function is used for menu navigation.

        :param g_mouse_reading: mouse input

        :return: if mouse was moved to the left return True, else False
        """
        if g_mouse_reading.x + self.mouse_menu_offset < 0:
            if self.l_dir_moved:
                return False
            else:
                self.l_dir_moved = True
                return True
        else:
            self.l_dir_moved = False
            return False

    def menu_right_movement(self, g_mouse_reading: SpaceNavigator) -> bool:
        """Checks if user has moved mouse to the right.

        Returns True only if mouse is moved to the right and previously was not.
        This function is used for menu navigation.

        :param g_mouse_reading: mouse input

        :return: if mouse was moved to the right return True, else False
        """
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
        """Checks if user has moved mouse backward.

        Returns True only if mouse is moved backward and previously was not.
        This function is used for menu navigation.

        :param g_mouse_reading: mouse input

        :return: if mouse was moved to the top return True, else False
        """
        if g_mouse_reading.y - self.mouse_menu_offset > 0:
            if self.t_dir_moved:
                return False
            else:
                self.t_dir_moved = True
                return True
        else:
            self.t_dir_moved = False
            return False
