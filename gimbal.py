import cv2
import numpy as np
import time
from smbus2 import SMBus
import datetime
import serial
import csv
import RPi.GPIO as GPIO

from setup import somethings_wrong
from variables import ser, set_and_status 

from variables import position_que

from variables import command_queue, response_queues

class pan_motion:
    position = 0
    min_pan, max_pan = 0x0, 0x800 #gymbal settings - pan
    min_tilt, max_tilt = 0x0, 0x600 #gymbal settings - tilt
    panval, tiltval = 0x400, 0x200 #gymbal settings - values
    panstep, tiltstep = 0x10, 0x10 #gymbal settings - step values 
    

def pan_to_sensor(pir_flags):
    #logic - determine where to move 
    #62 degree FOV - seperate 180 based on this
    #180/62 = 2.9, so 3 positions will position it so those three have no overlap
    #5 positions will all for greater overlap 

    #0x000 is pir1 (right)
    #0x400 is pir2 (middle)
    #0x800 is pir3 (left)

    
    #first check if all three are triggered
    if pir_flags.pir1_flag and pir_flags.pir2_flag and pir_flags.pir3_flag:
        #pan_val = pan_position #if all three are triggered - don't move 
        print("do nothing")
        p = False
    
      
    #have checked if all 3 are triggered - then 
    #only need to check two (no not(pirx)), as know 3 are not triggered
    #check is 1 and 2 are on
    elif pir_flags.pir1_flag and pir_flags.pir2_flag:
        #pan_val = 0x200 #in between 1 and 2
        pan_val = 800
        p = True
    elif pir_flags.pir3_flag and pir_flags.pir2_flag:
        pan_val = 1200 #in between 3 and 2
        p = True
    elif pir_flags.pir1_flag and pir_flags.pir3_flag:
        #pan_val = pan_position #triggered at 1 and 3 - 
        p = False
        #no way to see both, so for now just stay 
    #motion has been triggered - but now know only 1 has been triggered
    #check each individually
    elif pir_flags.pir1_flag:
        pan_val = 500 #only 1 triggered
        p = True
    elif pir_flags.pir2_flag:
        pan_val = 0x400 #only 1 triggered
        p = True
    elif pir_flags.pir3_flag:
        pan_val = 1500 #only 1 triggered
        p = True
    else:
        p = False


    if p:
        
        hex_value = f"{pan_val:03X}"[-3:] #hex val of pan 
        prefix = '0' #prefix of what to send to motor control
        command = f"CO{prefix}{hex_value}\n" #full command value
        command_queue.put(('motion_detection', command))

        set_and_status.position = pan_val

    return pan_val


def app_pan(direction, m_amount):
    min_pan, max_pan = 0x0, 0x800 #gymbal settings - pan
    min_tilt, max_tilt = 0x0, 0x600 #gymbal settings - tilt
    panval, tiltval = 0x400, 0x200 #gymbal settings - values
    panstep, tiltstep = 0x10, 0x10 #gymbal settings - step values 

    #get_pan_position()
    print("position", set_and_status.position)
    
    if direction == 'right':
        move_to = set_and_status.position + m_amount
    elif direction == 'left':
        move_to = set_and_status.position - m_amount

    print(move_to)
    if move_to < 400:
        move_to = 450
    
    if move_to > 1700:
        move_to = 1650

    panval = move_to
    prefix = '0'
    hex_value = f"{panval:03X}"[-3:]
    command = f"CO{prefix}{hex_value}\n"
    if panval != -1200:
        command_queue.put(('app_movement', command))
        #ser.write(command.encode('UTF-8')) 
        #print(f"Sent command: {command}")
        set_and_status.position = panval
        time.sleep(0.01)


def write_pan_position():
    #get_pan_position()
    file_name = r'/home/camcs/server/uploads/encoder_status/CameraRotationEncoderStatus.csv'
    #row = []
    with open(file_name, 'w', newline = '') as f:
        writer = csv.writer(f)
        writer.writerow(['Camera Encoder'])
        writer.writerow([set_and_status.position])
        #print(set_and_status.position)



