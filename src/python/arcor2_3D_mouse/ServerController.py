# from arcor2_arserver_data.client import ARServer
from ARServer import ARServer

# from arcor2.data import events
from arcor2.data.rpc import get_id
from arcor2.data.rpc.common import IdArgs
# from arcor2.data.rpc.common import RPC, RobotArg, TypeArgs
from arcor2_arserver_data import rpc as srpc


class TestServerController:
    def __init__(self, connection_string: str = "ws://0.0.0.0:6789"):
        self.a_s = ARServer(ws_connection_str=connection_string)

    # Scene Communication
    def test_scene_create(self, g_name: str, g_desc: str) -> None:
        self.a_s.call_rpc(
            srpc.s.NewScene.Request(get_id(), srpc.s.NewScene.Request.Args(name=g_name, description=g_desc)),
            srpc.s.NewScene.Response,
        )

    def test_scene_open(self, g_id: str) -> None:
        self.a_s.call_rpc(srpc.s.OpenScene.Request(get_id(), IdArgs(g_id)), srpc.s.OpenScene.Response)

    def test_scene_close(self) -> None:
        self.a_s.call_rpc(
            srpc.s.CloseScene.Request(get_id(), srpc.s.CloseScene.Request.Args(False)), srpc.s.CloseScene.Response
        )

    def test_scene_list(self) -> dict:
        return self.a_s.call_rpc(srpc.s.ListScenes.Request(get_id()), srpc.s.ListScenes.Response)

    def test_scene_save(self) -> None:
        self.a_s.call_rpc(srpc.s.SaveScene.Request(get_id()), srpc.s.SaveScene.Response)

    def test_scene_start(self) -> None:
        print(self.a_s.call_rpc(srpc.s.StartScene.Request(get_id()), srpc.s.StartScene.Response))

    def test_scene_stop(self) -> None:
        print(self.a_s.call_rpc(srpc.s.StopScene.Request(get_id()), srpc.s.StopScene.Response))

    # Project communication
    def test_project_create(self, g_id: str, g_name: str, g_desc: str, g_logic: str) -> None:
        self.a_s.call_rpc(
            srpc.p.NewProject.Request(
                get_id(),
                srpc.p.NewProject.Request.Args(scene_id=g_id, name=g_name, description=g_desc, has_logic=g_logic),
            ),
            srpc.p.NewProject.Response,
        )

    def test_project_open(self, g_id: str) -> None:
        self.a_s.call_rpc(srpc.p.OpenProject.Request(get_id(), IdArgs(g_id)), srpc.p.OpenProject.Response)

    def test_project_list(self) -> dict:
        return self.a_s.call_rpc(srpc.p.ListProjects.Request(get_id()), srpc.p.ListProjects.Response)

    def test_project_save(self) -> None:
        self.a_s.call_rpc(srpc.p.SaveProject.Request(get_id()), srpc.p.SaveProject.Response)

    def test_project_close(self) -> None:
        self.a_s.call_rpc(
            srpc.p.CloseProject.Request(get_id(), srpc.p.CloseProject.Request.Args(False)), srpc.p.CloseProject.Response
        )

    def test_print_event(self) -> None:
        try:
            print(self.a_s.get_event())
        except Exception:
            return "no event"
