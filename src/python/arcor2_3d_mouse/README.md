# arcor2_3D_mouse

## Structure 
##### mouse_controller.py
- contains classes necessary to read inputs from the 3D mouse
##### mouse_program.py
- contains main body of the program

## Usage

### For users

The application is used for fast and intuitive programming with arcor2 system.

Upon opening the application it goes to the waiting mode. In waiting mode it reads messages from the server, waiting for a project to be opened and started. In this state, the user can exit the application by pressing the right mouse button. 

If a project has been opened and the scene started, the app is in a robot-choosing state, in this state user chooses which robot should be doing new action. User can move through a list of robots by moving the mouse to the left and to the right. To select a robot the user has to press the left mouse button. To exit the app the user has to press the right mouse button.

When a robot has been selected, the app goes to the action-choosing state. In this state, the user chooses which action should be added. User can move through a list of actions by moving the mouse to the left and to the right. To select an action the user has to press the left mouse button. To choose a different robot the user has to press the right mouse button.

When action has been selected, the app goes to the movement state. In this state, all movements done by the mouse are directly sent to the chosen robot. To select a place, where new action has to be added, the user has to press the left mouse button. To choose different action, the user has to press the right mouse button.

When the place for new action is chosen, new action is added and the program goes back to the action-choosing state. Previously selected robot stays selected.

### For developers
The program is prepared by making an instance of mouse_program.MouseProgram class. Optional parameters are connecton_string and timeout. The Connection string is in the following format "ws://ip:port". Ip and port are of active arcor2 server running on a connected network. Timeout chooses the time, in which the app expects a response from the server. It is recommended to keep it under 1 sec.

After init user is expected to call class method register_user, with a chosen user name. If a username, that is already used is picked, the program will raise an exception.

The program itself starts after calling class method program_loop.

Because the program uses multiple threads, it is recommended to set interrupt and termination signals to class method close_program.
