
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


from pir_functions import *
from accel_functions import *
from setup import *
from gimbal import *
from variables import ser, bus_pir, bus_accel, a, prop_lines, pir_flags, record, set_and_status #,frame_streaming#, pir_int_pin, accel_int_pin
from share_videos import *

from queue import Queue

#frame_queue = Queue(maxsize=5)

#recording_name_queue = Queue(maxsize=5)

ai_loop_event = multiprocessing.Event()

#cam_img_event = multiprocessing.Event()
from variables import cam_event
from variables import output_name_que





def cam(s_move_time,lock):#ouput_name, cam_event):#, accelerometer, prop_lines): #pass cap (the camera) to function
    global a, prop_lines, pir_flags, record, set_and_status 
    global ser, bus_pir, bus_accel

    global cam_event

    if not(set_and_status.camera_on): #if camera is supposed to be off - just leave function
        return

    t = time.time()
    record.check_flags(pir_flags.motion_flag, pir_flags.motion_time) #initial checking of recording flags 

    print("time to check flags", time.time()-t)
    print("HELLO TWINKS")
    print(record.output_name)

    
    while True: #start loop, only break out when done recording  
        #first thing is to check accelerometer. 
        #if moving the acceleration will be out of bounds -> need to wait 
        s = s_move_time.value #time of serial movement 
        if ((s+2) < time.time()):# and ((pir_flags.motion_time + 2) < time.time()): #if its been 2 seconds from last serial move commnand
            #first thing - check accelerometer
            check_accel(a, bus_accel, set_and_status, 5)
        else:
            #serial motion has occured in last 2 seconds - widen bounds 
            check_accel(a, bus_accel, set_and_status, 10) #this bound is not definite - just a guess
            """ elif a.accel_flag:
                cam_event.clear()
                accel_flag_write(True)
                break #if accel motion (unauthorized motion) stop recording """
            
        #check if accel motion has occured
        if a.accel_flag: # and record.record_flag: #if recording, and unauthorized motion detected:
                #need to release everything 
                cam_event.clear()
                accel_flag_write(a.accel_flag) #write that motion has occurred 
                break #break out - go back to main
        
        
        
        
        if pir_flags.motion_flag and set_and_status.camera_movement and not(record.in_setup): #if motion flag is active get pan position. Don't activate pan if camera motion is turned off
            pan_to_value = pan_to_sensor(pir_flags) 
            print("send move command", time.time()-t)
        
        
        #check if just started recording -> at that point need to send recording name to video process 
        if record.recording_just_started:
            output_name_que.put(record.output_name) #send name
            cam_event.set() #start video process
            print("set event", time.time()-t)
        elif record.done_videoing: #at end of recording video 
            cam_event.clear() #stop recording
            print("Done", time.time()) #want to see time
            time.sleep(1) #wait a little bit
            break #break out - go back to main

        
        #sleep time between motion, serial process should be the same
        #i2c auto frequency for smbus is 100kHz, that is a period of 0.00001
        #conversion fs of ADC is 1us, but that is not needed 
        time.sleep(0.01) #need to sleep so that not overloading everything
        #takes time for things to even update 
        read(pir_flags, bus_pir, set_and_status) #check PIR again
        record.check_flags(pir_flags.motion_flag, pir_flags.motion_time) #check recording status based on pir 
    
    print("Done") #let log know that recording is done
    print(record.output_name) #let log know recording name 

    record.recording_just_started = False 




