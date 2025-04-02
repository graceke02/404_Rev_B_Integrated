
import cv2
import numpy as np
import time
from smbus2 import SMBus
import datetime
import serial
import csv
import RPi.GPIO as GPIO
import signal
import multiprocessing
from flask import Flask
import os
import schedule
import os, shutil
import datetime

from variables import ser
from variables import record, prop_lines

from variables import cam_event
from variables import output_name_que

from variables import frame_queue
from variables import ai_video_queue

from variables import command_queue, response_queues

def image_capture_and_processing(cam_properties, shared_array, lock):#output_name, cam_event):
    global cam_event
    #global record 

    s = time.time()
    rows = []

    file_name = r'/home/camcs/server/uploads/xypixelcolor/PropertyLineSetupXYPixelColorFile.csv'

    with open(file_name, newline = '') as f:
        fread = csv.reader(f)
        for row in fread:
            rows.append(row)              

    p = []
    #print(len(rows), len(row))
    #print(rows[0][0])
    for i in range(1,len(rows)):
        #####FOR NOW ONLY TESTING, SO 
        #CHECK HEADERS TO GET CORRECT DATA
        if rows[0][0] == 'X Values' and rows[0][1] == 'Y Values':
            p.append(rows[i])
    
    #print(rows)
    
    points = np.array(p, dtype = np.int32)
    points = points.reshape((-1,1,2)) #reshape format
    print("time to get points", s-time.time())


    map1, map2 = cv2.initUndistortRectifyMap(cam_properties["camera_matrix"], cam_properties["dist_coeffs"], None, cam_properties["new_camera_matrix"], (1920, 1080), cv2.CV_32FC1)
    
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2) #initialize camera

    # Set MJPEG first to reduce CPU load
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE,1)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = 30
    width = 640
    height = 480

    if not(cap.isOpened()): #check if opened 
        print("Could not open video device") #let user know
        return
    
    record_name = output_name_que.get()
    print("I cap proc output name", record_name)
    
    out = cv2.VideoWriter(record_name, fourcc, fps, (width, height))

    mask = np.zeros((height,width), dtype=np.uint8) #set up so cv2 can use
    cv2.fillPoly(mask, [points], (255,255,255)) #make a filled polygon

    maskbigly = cv2.resize(mask, (cam_properties["panwidth"],480), interpolation = cv2.INTER_NEAREST)
    maskbigly = cv2.copyMakeBorder(maskbigly, 0,0,500,500,cv2.BORDER_CONSTANT, value=[0,0,0])

    pos = []
    print("time to set things up", s-time.time())
    
    while cam_event.is_set():

        ret, frame = cap.read() #read frame from camera

        # if frame is read correctly ret is True
        if not(ret): #not recording properly 
            print("Can't receive frame (stream end?). Exiting ...") #let user know
            break #leave loop


        undistorted = cv2.remap(frame, map1, map2, interpolation=cv2.INTER_LINEAR)

        x, y, w, h = cam_properties["roi"]
        undistorted = undistorted[y:y+h, x:x+w]
        u = undistorted[:480,:640]
        u = cv2.flip(u, -1)


        command_queue.put(('img_blocking', f"CR0000\n"))
        while response_queues["img_blocking"].empty():
            time.sleep(0.001)


        hexpos = response_queues["img_blocking"].get()


        if len(pos) < 5:
            pos.append(hexpos)
        else:
            pos.pop(0)
            pos.append(hexpos)
        

        ma = max(pos)
        mi = min(pos)
        if (ma-mi) > 50:
            print("last 5 positions", pos)


        if (hexpos > 0xc00):
            hexpos -= 4096
        centerAngle = 360*float(hexpos) / 4096

        startCol = int(((centerAngle-cam_properties["mingle"])/cam_properties["panfov"])*cam_properties["panwidth"] -320 + 0.5)+500
        endCol = startCol + 640


        maskslice = maskbigly[:,startCol:endCol]

        maskslice = cv2.cvtColor(maskslice, cv2.COLOR_GRAY2BGR)
        inverted = cv2.bitwise_and(u, maskslice)

        with lock:
            # Create a NumPy view over the shared memory buffer and reshape it to the frame dimensions.
            np_frame = np.frombuffer(shared_array, dtype=np.uint8).reshape((480, 640, 3))
            np.copyto(np_frame, inverted)  # Copy the entire frame at once
        #cv2.imshow('frame', inverted) #show in window the frame
        out.write(inverted) #write to file
        #cv2.waitKey(34)
        cv2.waitKey(1) #cV2 wait, allows for frame to be shown
            #await asyncio.sleep(0.1)
    
    ai_video_queue.put(record_name)
    cap.release() #realease camera
    out.release() #release video writer
    cv2.destroyAllWindows() #close camera vindow
