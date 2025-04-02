import cv2
import numpy as np
import time
from smbus2 import SMBus
import datetime
import serial
import csv
import RPi.GPIO as GPIO

from setup import somethings_wrong


def read(pir_flags, bus_pir, s):
    pir1 = 0x54
    pir2 = 0x50
    pir3 = 0x55

    try: #see if can read motion
        #write 0 to them
        
        ADC_out1 =  bus_pir.read_i2c_block_data(pir1, 0x00, 2) #0x00 is the data reg. Read two bytes
        ADC_out2 =  bus_pir.read_i2c_block_data(pir2, 0x00, 2)
        ADC_out3 =  bus_pir.read_i2c_block_data(pir3, 0x00, 2)
        #output is a list with two data points 

        #ADC_out 0 is MSB of data. ADC_out 2 contains lsb 
        #Output is odd - 0x0'value'0. First and last 4 bits are reserved values
        #Value is actually only 8 bits
        #MSB nibble - need to bitshift left by 4
        #LSB nibble - need to bitshift right by 4
        data1 = ADC_out1[0]*16 + ADC_out1[1]/16 #transform, PIR1
        data2 = ADC_out2[0]*16 + ADC_out2[1]/16 #transform, PIR2
        data3 = ADC_out3[0]*16 + ADC_out3[1]/16 #transform, PIR3

        #0xFFF = 3.3V (ref voltage)
        #motion_threshold = 148 #1.9V - ADC value. val = (1.9/3.3)*256
        motion_threshold = 110
        #motion_ended_threshold = 0.5 #so this value is kind of unknown - but from observing this is good
        motion_ended_threshold = 39 #0.5V - ACD value. val = (0.5/3.3)*256
        
        
        #add logic to make motor movement smoother. Analog volotage fluctuates wildly, so with out logic motor movement is erratic 
        
        #now compare 
        if (data1 >  motion_threshold) or (data1 <  motion_ended_threshold): #over/unter threshold actively
            pir_flags.pir1_flag = True
            pir_flags.pir1_motion_time = time.time()
            #need to clear any alert regs now. Alert only goes to zero when a 1 is written to flag
            bus_pir.write_byte_data(0x50,0x01, 0x03)
        elif (time.time() - pir_flags.pir1_motion_time) < 0.5: #logic to reduce changes/spiking in behairo.
            pir_flags.pir1_flag = True
        else:
            pir_flags.pir1_flag = False
        
        if (data2 >  motion_threshold) or (data2 <  motion_ended_threshold): #actively high/low
            pir_flags.pir2_flag = True
            pir_flags.pir2_motion_time = time.time()
            bus_pir.write_byte_data(0x54,0x01, 0x03) #clear alert reg
        elif (time.time() - pir_flags.pir2_motion_time) < 0.5:  #logic to reduce changes/spiking in behairo.
            pir_flags.pir2_flag = True
        else:
            pir_flags.pir2_flag = False
        
        if (data3 >  motion_threshold) or (data3 <  motion_ended_threshold): #actively high/low
            pir_flags.pir3_flag = True
            pir_flags.pir3_motion_time = time.time()
            bus_pir.write_byte_data(0x55,0x01, 0x03) #clear alert reg
        elif (time.time() - pir_flags.pir3_motion_time) < 0.5:  #logic to reduce changes/spiking in behaior
            pir_flags.pir3_flag = True
        else:
            pir_flags.pir3_flag = False

        
        #set overall pir flags 
        if  pir_flags.pir1_flag or  pir_flags.pir2_flag or  pir_flags.pir3_flag:
            pir_flags.motion_flag = True
            pir_flags.motion_time = time.time()
            #print("Motion",time.time())
        else:
            pir_flags.motion_flag = False 


        bus_pir.write_byte_data(0x50, 0x01, 0x03)  #clear alert register
        bus_pir.write_byte_data(0x54, 0x01, 0x03)  #clear alert register
        bus_pir.write_byte_data(0x55, 0x01, 0x03)  #clear alert register
    
        
        if not(s.pir_status):
            s.pir_status = True #pir were not wrking, now are
            somethings_wrong(s)
            print("PIRs now working")

    except IOError: #not reading PIR correctly 
        s.pir_status = False
        somethings_wrong(s)
        print("Error reading form PIRs") #let user know


