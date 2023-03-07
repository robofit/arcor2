import time
from queue import Empty, Queue
from typing import TypeVar

import websocket
from dataclasses_jsonschema import ValidationError

from arcor2 import json
from arcor2.data import events, rpc
from arcor2.data.rpc import get_id
from arcor2.exceptions import Arcor2Exception
from arcor2.logging import get_logger
from arcor2_arserver_data import rpc as srpc


from arcor2.data.rpc.common import RPC, IdArgs, RobotArg
from arcor2.data.common import Position, Orientation, Pose
import pandas as pd

from MouseClass import MouseClass
from ARServer import ARServer



import time
from gtts import gTTS
from playsound import playsound
import os
class MouseProgram:

#TODO exceptions here
    def __init__(self):
        self.a_s = ARServer()
        self.mouse = MouseClass()
        self.read_innit_message()

    def get_event(self):
        try:
            return self.a_s.get_event()
        except Exception:
            return "no event"
    
    def print_supported_rpcs(self):
        for a in self.a_s._supported_rpcs:
            print(a)

    def register_user(self,g_name):
        self.a_s.call_rpc(srpc.u.RegisterUser.Request(get_id(),srpc.u.RegisterUser.Request.Args(user_name=g_name)), srpc.u.RegisterUser.Response)

#Yeller
#TODO this version makes temporary save of audio
    def read_text(self,g_text):
        language = 'en'
        langObj = gTTS(text=g_text, lang=language, slow=False)
        langObj.save("speech.mp3")
        playsound("speech.mp3",True)
        os.remove("speech.mp3")




#Scene Communication
    def test_scene_create(self,g_name,g_desc):
        self.a_s.call_rpc(srpc.s.NewScene.Request(get_id(),srpc.s.NewScene.Request.Args(name=g_name,description=g_desc)), srpc.s.NewScene.Response)

    
    def test_scene_open(self,g_id):
        self.a_s.call_rpc(srpc.s.OpenScene.Request(get_id(),IdArgs(g_id)), srpc.s.OpenScene.Response)

    
    def test_scene_close(self):
        self.a_s.call_rpc(srpc.s.CloseScene.Request(get_id(),srpc.s.CloseScene.Request.Args(False)), srpc.s.CloseScene.Response)

    
    def test_scene_list(self):
        return self.a_s.call_rpc(srpc.s.ListScenes.Request(get_id()), srpc.s.ListScenes.Response).data

    def test_scene_save(self):
        self.a_s.call_rpc(srpc.s.SaveScene.Request(get_id()), srpc.s.SaveScene.Response)




#Project communication    
    def test_project_create(self,g_id,g_name,g_desc,g_logic):
        self.a_s.call_rpc(srpc.p.NewProject.Request(get_id(),srpc.p.NewProject.Request.Args(scene_id=g_id,name=g_name,description=g_desc, has_logic=g_logic)), srpc.p.NewProject.Response)
    
    
    def test_project_open(self,g_id):
        self.a_s.call_rpc(srpc.p.OpenProject.Request(get_id(),IdArgs(g_id)), srpc.p.OpenProject.Response)

    
    def test_project_list(self):
        return self.a_s.call_rpc(srpc.p.ListProjects.Request(get_id()), srpc.p.ListProjects.Response).data

    def test_project_save(self):
        self.a_s.call_rpc(srpc.p.SaveProject.Request(get_id()), srpc.p.SaveProject.Response)

    def test_project_close(self):
        self.a_s.call_rpc(srpc.p.CloseProject.Request(get_id(),srpc.p.CloseProject.Request.Args(False)), srpc.p.CloseProject.Response)




#Locker
    #? Je nutne updatovat lock ?Otestovat fail locku

    #UT
    def lock_read(self,g_id):
        self.a_s.call_rpc(srpc.lock.ReadLock.Request(get_id(),srpc.lock.ReadLock.Request.Args(g_id)),srpc.lock.ReadLock.Response)
    
    #UT
    def lock_write(self,g_id,g_lock_tree = None):
        if lock_tree == None:
            self.a_s.call_rpc(srpc.lock.WriteLock.Request(get_id(),srpc.lock.WriteLock.Request.Args(g_id)),srpc.lock.WriteLock.Response)
        else:
            self.a_s.call_rpc(srpc.lock.WriteLock.Request(get_id(),srpc.lock.WriteLock.Request.Args(g_id,g_lock_tree)),srpc.lock.WriteLock.Response)

    #UT
    def lock_read_unlock(self,g_id):
        self.a_s.call_rpc(srpc.lock.ReadUnlock.Request(get_id(),srpc.lock.ReadUnlock.Request.Args(g_id)),srpc.lock.ReadUnlock.Response)

    #UT
    def lock_write_unlock(self,g_id):
        self.a_s.call_rpc(srpc.lock.WriteUnlock.Request(get_id(),srpc.lock.WriteUnlock.Request.Args(g_id)),srpc.lock.WriteUnlock.Response)





#Robot Mover

    #UT
    def robot_end_effector_pose(self,g_robot_id,g_end_effector_id,g_arm_id = None):
        if g_arm_id == None:
            return self.a_s.call_rpc(srpc.r.GetEndEffectorPose.Request(get_id(),srpc.r.GetEndEffectorPose.Request.Args(g_robot_id,g_end_effector_id)), srpc.r.GetEndEffectorPose.Response).data
        else:
            return self.a_s.call_rpc(srpc.r.GetEndEffectorPose.Request(get_id(),srpc.r.GetEndEffectorPose.Request.Args(g_robot_id,g_end_effector_id,g_arm_id)), srpc.r.GetEndEffectorPose.Response).data

    #UT
    def robot_end_effectors_get(self,g_robot_id,g_arm_id = None):
        if g_arm_id == None:
            return self.a_s.call_rpc(srpc.r.GetEndEffectors.Request(get_id(),srpc.r.GetEndEffectors.Request.Args(g_robot_id)), srpc.r.GetEndEffectors.Response).data
        else:
            return self.a_s.call_rpc(srpc.r.GetEndEffectors.Request(get_id(),srpc.r.GetEndEffectors.Request.Args(g_robot_id,g_arm_id)), srpc.r.GetEndEffectors.Response).data

    #UT
    def robot_arms_get(self,g_robot_id):
         return self.a_s.call_rpc(srpc.r.GetRobotArms.Request(get_id(),srpc.r.GetRobotArms.Request.Args(g_robot_id)), srpc.r.GetRobotArms.Response).data

    #UT ?linear ?Move to action point vypada rovnako
    def robot_move_to_pose(self,g_robot_id,g_end_effector_id,g_speed,g_position,g_orientation,g_arm_id = None):
        if(g_arm_id == None):
            s_data = srpc.r.MoveToPose.Request.Args(g_robot_id,g_end_effector_id,g_speed,g_position,g_orientation)
        else:
            s_data = srpc.r.MoveToPose.Request.Args(g_robot_id,g_end_effector_id,g_speed,g_position,g_orientation,g_arm_id)
        self.a_s.call_rpc(srpc.r.MoveToPose.Request(get_id(),s_data), srpc.r.MoveToPose.Response)





#Action points
    def action_point_add(self,g_name,g_position):
        self.a_s.call_rpc(srpc.p.AddActionPoint.Request(get_id(),srpc.p.AddActionPoint.Request.Args(g_name,g_position)),srpc.p.AddActionPoint.Response)




#Random tests, skusanie ktore spravy mi pomozu a ktore nie

    #Nope - this writas all objects loaded in server that are recognized
    def test_get_object_types(self):
        return self.a_s.call_rpc(srpc.o.GetObjectTypes.Request(get_id()),srpc.o.GetObjectTypes.Response).data

    #Nope - this is probably only for checking which scenes have certain object
    def test_scene_object_usage(self,g_id):
        return self.a_s.call_rpc(srpc.s.SceneObjectUsage.Request(get_id(),IdArgs(g_id)),srpc.s.SceneObjectUsage.Response).data
    
    #NW ???
    def test_scene_object_add(self,g_name,g_type):
        self.a_s.call_rpc(srpc.s.AddObjectToScene.Request(get_id(),srpc.s.AddObjectToScene.Request.Args(g_name,g_type)),srpc.s.AddObjectToScene.Response)




#Special functions

    def read_innit_message(self):
        received_event = self.get_event()
        if not received_event["event"][0] == "OpenProject":
#TODO raise exepction here
            return False
        self.cur_proj = received_event["data"]["project"]
        self.cur_scene = received_event["data"]["scene"]
        
#TODO For now just empties
        scene_state = self.get_event()


    #Tu mozno treba inu senzitivitu na rotation a inu na position
    #Okrem toho sem mozno treba dodat tu minimalnu barieru nech to necita nahodne udaje
    def move_robot_with_mouse(self,g_robot_id,g_end_effector_id,g_mouse_reading,g_sensitivity,g_arm_id = None):
        def_pos = self.robot_end_effector_pose(g_robot_id,g_end_effector_id,g_arm_id)
        def_pos.position.x = def_pos.position.x + g_mouse_reading.x * g_sensitivity
        def_pos.position.y = def_pos.position.y + g_mouse_reading.y * g_sensitivity
        def_pos.position.z = def_pos.position.z + g_mouse_reading.z * g_sensitivity
        def_pos.orientation.__mul__(Orientation().from_rotation_vector(g_mouse_reading.roll*g_sensitivity,g_mouse_reading.pitch*g_sensitivity,g_mouse_reading.yaw*g_sensitivity))
        self.robot_move_to_pose(g_robot_id,g_end_effector_id,g_speed,def_pos.position,def_pos.orientation,g_arm_id)

    #NT
#TODO redefine offset base on testing, if needed
    #Niektore roboty nemusia mat pohyblivost na vsetkych osach -> viz. ten dopravnik -> bod ma zakruzit okolo povodnej pozicie a otocit sa na vsetkych osach o offset uhol
    #Rotacia ma spravit aby sa to trochu pokyvalo,nwm ci je to vobec nutne
    def highligth_robot_mechanic(self,g_robot_id,g_end_effector_id,g_arm_id = None):
        #Pose
        def_pos = self.robot_end_effector_pose(g_robot_id,g_end_effector_id,g_arm_id)
        pos_offset = 1
        rot_offset = 45

        #pose 1
        pos1 = Pose()
        pos1.position = Position(def_pos.position.x, def_pos.position.y-pos_offset,def_pos.position.z - pos_offset)
        pos1.orientation = Orientation().from_rotation_vector(0,0,0)

        #pose 2
        pos2 = Pose()
        pos2.position = Position(def_pos.position.x - pos_offset, def_pos.position.y,def_pos.position.z)
        pos2.orientation = Orientation().from_rotation_vector(-rot_offset,-rot_offset,-rot_offset)

        #pose 3
        pos3 = Pose()
        pos3.position = Position(def_pos.position.x, def_pos.position.y+pos_offset,def_pos.position.z + pos_offset)
        pos3.orientation = Orientation().from_rotation_vector(0,0,0)

        #pose 4
        pos4 = Pose()
        pos4.position = Position(def_pos.position.x + pos_offset, def_pos.position.y,def_pos.position.z)
        pos4.orientation = Orientation().from_rotation_vector(rot_offset,rot_offset,rot_offset)

        self.robot_move_to_pose(g_robot_id,g_end_effector_id,g_speed,pos1.position,pos1.orientation,g_arm_id)
        self.robot_move_to_pose(g_robot_id,g_end_effector_id,g_speed,pos2.position,pos2.orientation,g_arm_id)
        self.robot_move_to_pose(g_robot_id,g_end_effector_id,g_speed,pos3.position,pos3.orientation,g_arm_id)
        self.robot_move_to_pose(g_robot_id,g_end_effector_id,g_speed,pos4.position,pos4.orientation,g_arm_id)
        self.robot_move_to_pose(g_robot_id,g_end_effector_id,g_speed,def_pos.position,def_pos.orientation,g_arm_id)

    #def highligth_robot(self,g_robot_id,g_end_effector_id,g_arm_id):
        

mouse = MouseProgram()
print(mouse.cur_proj)
print(mouse.cur_scene)
mouse.register_user("Namae")

while True:
    reading = mouse.mouse.mouse_read()
    if mouse.mouse.mouse_button_left_pressed(reading):
        print("LMB")
    if mouse.mouse.mouse_button_rigth_pressed(reading):
        print("RMB")
    if mouse.mouse.menu_left_movement(reading):
        print("Left")
    if mouse.mouse.menu_rigth_movement(reading):
        print("Rigth")

#mouse.test_project_open("pro_ff2a1f9119554ba597226ac6e00ad155")
#mouse.test_project_create("scn_916222d8a8094d84b4e3d5ba96d71757","P1","P1desc",True)
#mouse.action_point_add("AP1",Position(0,0,0))
#print(mouse.get_event())
#mouse.test_project_save()
#mouse.test_project_close()
#print(mouse.test_project_list())

#print(mouse.test_get_object_types())

#mouse.test_scene_open("scn_916222d8a8094d84b4e3d5ba96d71757")
#mouse.test_scene_object_add("Bobot","DobotM1")
#mouse.test_scene_save()
#mouse.test_scene_close()

#print(mouse.test_scene_list())
#print(mouse.test_scene_object_usage("scn_916222d8a8094d84b4e3d5ba96d71757"))

#mouse.test_scene_save()
#mouse.test_scene_create("S1","S1_desc")
#print(mouse.get_event())