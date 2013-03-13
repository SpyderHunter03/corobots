#!/usr/bin/env python
import roslib; roslib.load_manifest('corobot_comm')
import rospy
import socket

from geometry_msgs.msg import Point
from corobot_msgs.srv import GetLocation
from corobot_msgs.msg import Pose,Goal
from collections import deque
import time

#Robot's current position.  Defaults to a test position.
myPose = Pose(x=26.3712,y=-7.7408,theta=0) # NE Atrium

goalQueue = deque()

def pose_callback(pose):
    '''
    Pose subscription callback
    '''
    global myPose
    myPose = pose

def goals_reached_callback(reached):
    '''
    Goals Reached subscription callback
    '''
    if goalQueue[0] == reached.name:
        goalQueue.popleft()

def clientComm(socket,addr):
    '''
    Begin client API communication

    Arguments:
    socket -- Active socket to a connected client
    addr -- Client's IP address
    '''
    rospy.init_node('corobot_client_comm')
    clIn = socket.makefile('r')
    clOut = socket.makefile('w')
    
    #Publisher to obstacle_avoidance, for GOTO* commands
    pointPub = rospy.Publisher('waypoints',Point)
    #Publisher to robot_nav, for NAVTO* commands
    goalPub = rospy.Publisher('goals',Goal)

    rospy.Subscriber('goals_reached',Goal,goals_reached_callback)
    rospy.Subscriber('pose',Pose,pose_callback)
    
    while True:
        cmd = clIn.readline()
        #Communication terminated?
        if len(cmd) == 0:
            clIn.close()
            clOut.close()
            break

        cmd = cmd.strip().split(' ')
        rospy.logdebug("Command recieved from client %s: %s", addr, cmd)

        #Command processing
        if cmd[0] == 'GETPOS':
            clOut.write("POS {} {} {}\n".format(str(myPose.x),str(myPose.y),str(myPose.theta)))
            clOut.flush()
        elif cmd[0] == 'GOTOXY':
            #Add dest point!
            pointPub.publish(x=float(cmd[1]),y=float(cmd[2]))
        elif cmd[0] == 'GOTOLOC':
            #Goto location, no navigation
            rospy.wait_for_service('get_location')
            dest = cmd[1].upper()
            try:
                getLoc = rospy.ServiceProxy('get_location',GetLocation)
                #returns Waypoint
                resp = getLoc(dest)
                pointPub.publish(x=resp.wp.x,y=resp.wp.y)
                goalQueue.append(dest)
            except rospy.ServiceException as e:
                rospy.logerr("Service call failed: {}".format(e))
        elif cmd[0] == 'NAVTOLOC':
                goalPub.publish(dest)
                goalQueue.append(dest)
        elif cmd[0] == 'QUERY_ARRIVE':
            if cmd[1] in goalQueue:
                while cmd[1] in goalQueue:
                    time.sleep(1)
                clOut.write("ARRIVED {}\n".format(cmd[1]))


def main():
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.bind((socket.gethostname(),15001))
    serversocket.listen(1)

    while True:
        (client, clAddr) = serversocket.accept()
        #On connection accept, go into ROS node method
        clientComm(client,clAddr)

if __name__ == '__main__':
    main()