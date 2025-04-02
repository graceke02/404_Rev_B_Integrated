import cv2
import numpy as np
import time
from smbus2 import SMBus
import datetime
import serial
import csv
import RPi.GPIO as GPIO

from setup import somethings_wrong

'''
bus_num_accel = 1 
#start the bus
bus_accel = SMBus(bus_num_accel)

#set up interrupts
GPIO.setmode(GPIO.BOARD)
accel_int_pin = 29
GPIO.setup(accel_int_pin, GPIO.IN)

pir_int_pin = 31
GPIO.setup(pir_int_pin, GPIO.IN)
'''

'''
class accel:
    address = 0x18
    #accel accounting for instability
    not_random_count = 3 #number of consecutive triggers to be not random

    #accel basis
    x_basis = 0
    y_basis = 0
    z_basis = 0

    #3 std deviations from mean - tolerance
    x_tol_u = 0 #x tolerance, upper bound
    y_tol_u = 0 #y tolerance, upper bound
    z_tol_u = 0 #z tolerance, upper bound

    x_tol_l = 0 #x tolerance, lower bound
    y_tol_l = 0 #y tolerance, lower bound
    z_tol_l = 0 #z tolerance, lower bound

    #values - current
    x_val = 0
    y_val = 0
    z_val = 0
    
    #interrupt counts
    int_count = 0


    #accelertometer flag
    accel_flag = False
    
    #registers
    Out_X_LSB = 0x04 #LSB of x-axis accelerometer 
    Out_X_MSB = 0x05 #MSB of x-axis accelerometer 
    Out_Y_LSB = 0x06 #LSB of y-axis accelerometer 
    Out_Y_MSB = 0x07 #MSB of y-axis accelerometer 
    Out_Z_LSB = 0x08 #LSB of z-axis accelerometer 
    Out_Z_MSB = 0x09 #MSB of z-axis accelerometer 

    def compare(self):
        #need to build in motion check 
        
        if abs(self.x_val) >  self.x_tol_u:
            self.int_count += 1
        elif abs(self.y_val) > self.y_tol_u:
            self.int_count += 1 
        elif abs(self.z_val) > self.z_tol_u:
            self.int_count += 1 
        elif abs(self.x_val) < self.x_tol_l:
            self.int_count += 1 
        elif abs(self.y_val) < self.y_tol_l:
            self.int_count += 1 
        elif abs(self.z_val) < self.z_tol_l:
            self.int_count += 1 
        else:
            #no accel movement detected - set everything to zero 
            self.int_count = 0

'''


def convert(lsb,msb):
    #takes two bytes in. 16 bits, but only 12 are relevant
    #combine:
    #get rid of sign bits on msb first 
    signed = False #automatically asume false
    if msb < 16:
        #15:12 are zero (sign extended)
        big = msb* 256 #shift by 8
        signed = False #if msb_nibble < 16 - not signed 
    else:
        #15:12 are not zero (sign extened), but do not care about actual value
        h_11_8 = msb % 16 #signed - get 11 to 8 by getting remainder 

        big =  256*h_11_8 #shift by 8
        signed = True #set to true

    # LSB_b is already good
    val = lsb + big #full value 

    #for binary, the first two are 0b, then the actual binary number
    max_unsigned = 2**12 #12 bit data 
    if signed: #convert signed value
        val -= max_unsigned #signed, so need to deduct max_unsigned value 

    to_devide = 1024 #to devide: 2=2048, 1=1024, so each signed bit is 1/1024 g
    #grav = 9.81
    #val = grav*val/to_devide #convert to value based on m/s^2

    val = val/to_devide #convert to value based on g (1g = 9.81)
    return val #return converted value 


#get basis to compare values 
def basis(accel, bus_accel, s): #accel is the class object
    #read data
    #start accelerometer
    bus_accel.write_byte_data(0x18, 0x15, 0x01) #0x15 is a config reg, 0x01 sets to active. 0x18 is accel address
    
    #print("get basis")
    x = [] #list to collect variable
    y = [] #list to collect variable
    z = [] #list to collect variable

    i = 0 #iteration variable 
    try:
        while i<10: #collect data till x - will take x seconds 
            #x_lsb = bus_accel.read_byte_data(accel.address, accel.Out_X_LSB) #read LSB of x-axis accelerometer 
            #x_msb = bus_accel.read_byte_data(accel.address, accel.Out_X_MSB) #read MSB of x-axis accelerometer 
            y_lsb = bus_accel.read_byte_data(accel.address, accel.Out_Y_LSB) #read LSB of y-axis accelerometer 
            y_msb = bus_accel.read_byte_data(accel.address, accel.Out_Y_MSB) #read MSB of y-axis accelerometer 
            z_lsb = bus_accel.read_byte_data(accel.address, accel.Out_Z_LSB) #read LSB of z-axis accelerometer 
            z_msb = bus_accel.read_byte_data(accel.address, accel.Out_Z_MSB) #read MSB of z-axis accelerometer 


            #x.append(convert(x_lsb,x_msb)) #convert raw value to more useable one 
            y.append(convert(y_lsb,y_msb)) #convert raw value to more useable one 
            z.append(convert(z_lsb,z_msb)) #convert raw value to more useable one 


            time.sleep(1) #sleep for one second
            i += 1 #increment 
            print("accel basis, i=", i) #let user know still going 
        
        if not(s.accel_status): #check if accel was not working, but now is 
                s.accel_status = True #set to working 
                somethings_wrong(s) #rewrite file, accel workign now
    
    except:
        s.accel_status = False
        somethings_wrong(s) #write to file - accel is not working right

    
    #accel.x_basis = np.average(x) #average all values collected - this is basis
    accel.y_basis = np.average(y) #average all values collected - this is basis
    accel.z_basis = np.average(z) #average all values collected - this is basis

    #print(accel.x_basis)
    #use absolute value of mean and std dev to simplify comparisions 
    #abs(mean) + abs(2*std) < abs(value) 
    #accel.x_tol_u = abs(accel.x_basis) + abs(5*np.std(x)) #get 3 std dev of x values, upper bound 
    accel.y_tol_u = (accel.y_basis) + abs(10*np.std(y)) #get 3 std dev of y values, upper bound
    accel.z_tol_u = (accel.z_basis) + abs(10*np.std(z)) #get 3 std dev of z values, upper bound

    #accel.x_tol_l = abs(accel.x_basis) - abs(5*np.std(x)) #get 3 std dev of x values, lower bound 
    accel.y_tol_l = (accel.y_basis) - abs(10*np.std(y)) #get 3 std dev of y values, lower bound 
    accel.z_tol_l = (accel.z_basis) - abs(10*np.std(z)) #get 3 std dev of z values, lower bound 


def check_accel(accel, bus_accel, s, bound_multiplier):
    #read all the values 
    try:
        #x_lsb = bus_accel.read_byte_data(accel.address, accel.Out_X_LSB)  #read LSB of x-axis accelerometer 
        #x_msb = bus_accel.read_byte_data(accel.address, accel.Out_X_MSB) #read MSB of x-axis accelerometer 
        y_lsb = bus_accel.read_byte_data(accel.address, accel.Out_Y_LSB) #read LSB of y-axis accelerometer 
        y_msb = bus_accel.read_byte_data(accel.address, accel.Out_Y_MSB) #read MSB of y-axis accelerometer 
        z_lsb = bus_accel.read_byte_data(accel.address, accel.Out_Z_LSB) #read LSB of z-axis accelerometer 
        z_msb = bus_accel.read_byte_data(accel.address, accel.Out_Z_MSB) #read MSB of z-axis accelerometer 

        #now convert, so useable 
        #accel.x_val = convert(x_lsb,x_msb) #convert value
        accel.y_val = convert(y_lsb,y_msb) #convert value
        accel.z_val = convert(z_lsb,z_msb) #convert value

        #now compare 
        accel.compare(bound_multiplier)

        #now see if need to set flag 
        if accel.int_count >= 1: #changing to 1 for now to z. not using noisy x axis
            accel.accel_flag = True
            print("Accelerometer motion")
            print("Accel Basis:", accel.y_basis, accel.z_basis)
            print("Accel upper tolerance:",accel.y_tol_u, accel.z_tol_u)
            print("Accel lower tolerance:",accel.y_tol_l, accel.z_tol_l)
            print("Accel values:",accel.y_val, accel.z_val)
            accel_flag_write(True)
    
        if not(s.accel_status): #check if accel was not working, but now is 
                s.accel_status = True #set to working 
                somethings_wrong(s) #rewrite file, accel workign now
    
    except:
        s.accel_status = False
        somethings_wrong(s) #write to file - accel is not working right
    



def accel_flag_write(accel_int_flag):
    name = r'/home/camcs/server/uploads/camera_motion/sensor_status.csv'
    if accel_int_flag:
        x = 1
    else:
        x = 0
    rows = [["Camera Sensor Status"], [x]]
    with open(name, 'w', newline='') as f:
        fwrite = csv.writer(f, delimiter = ',')
        for i in range(len(rows)):
            fwrite.writerow(rows[i])

