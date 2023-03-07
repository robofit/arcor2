import signal

from arcor2_3d_mouse.mouse_program import MouseProgram


def main() -> None:
    mouse = MouseProgram(connection_string="ws://192.168.104.100:6789")
    signal.signal(signal.SIGINT, mouse.close_program)
    signal.signal(signal.SIGTERM, mouse.close_program)
    mouse.register_user("mouse_user")
    mouse.program_loop()


if __name__ == "__main__":
    main()
