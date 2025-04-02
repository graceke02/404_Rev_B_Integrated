import cv2
import numpy as np
import time
from smbus2 import SMBus
import datetime
import serial
import csv
import RPi.GPIO as GPIO

#from accel_functions import basis


def somethings_wrong(s):
    print("Error reading from sensors", s.cam_status, s.pir_status, s.accel_status, s.motor_status)




def turn_off(bus_accel, s):
    try:
        bus_accel.write_byte_data(0x18, 0x15, 0x00) #0x15 is a config reg, 0x00 sets to standby. 0x18 is accel address
        if not(s.accel_status): #check if accel was not working, but now is 
                s.accel_status = True #set to working 
                somethings_wrong(s) #rewrite file, accel workign now
    except:
        s.accel_status = False
        somethings_wrong(s) #write to file - accel is not working right




    
