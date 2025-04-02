import multiprocessing.queues
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
import threading


from flask_Server import app, a_int, a_lock, gpio_loop_running
from pir_functions import *
from accel_functions import *
from setup import *
from gimbal import *
from variables import ser, bus_pir, bus_accel, a, prop_lines, pir_flags, record, set_and_status#, frame_streaming#, accel_int_pin, pir_int_pin
from auto_delete import del_videos
from cam_simple import cam, ai_loop_event#, recording_name_queue #, cam_img_event
#from ai_fake import ai_fake_funciton
from i_cap_proc import image_capture_and_processing
from variables import shared_array, lock
from variables import new_setup
from variables import s_move_time

import sys
sys.path.append(r'/home/camcs/server/Facial_Detection_Model5')
#sys.path.insert(0, '/home/camcs/server/Facial_Detection_Model5')
import Model_with_jetson
#from Facial_Detection_Model5.Model_with_jetson import model_with_jetson_main

from variables import cam_event
from variables import c_queue
from variables import ai_video_queue

GPIO.cleanup()
#set up interrupts
GPIO.setmode(GPIO.BOARD)
accel_int_pin = 29
GPIO.setup(accel_int_pin, GPIO.IN)

pir_int_pin = 7
GPIO.setup(pir_int_pin, GPIO.IN)

battery_pin = 33 #31 or 33, just depends on what we do 
GPIO.setup(battery_pin, GPIO.IN)


def accel_event():
    #if there is an event - monitor for a bit and then decide
    aint = True 
    i = 0
    while i < 5:
        #check_accel(a, bus_accel, set_and_status)
        time.sleep(0.1)
        i += 1



#setup initial server files
accel_flag_write(a.accel_flag)


def run_flask():
    #app.run(host='0.0.0.0', port=5000, use_reloader=False)
    app.run(host="0.0.0.0", port=5000, use_reloader=False, debug=False)


def gpio_event_loop(s_move_time,lock):#output_name, cam_event):
    global a_int
    
    print("Wait")

    gpio_loop_running.clear()
    print(gpio_loop_running)
    time.sleep(3)

    #bus_accel.write()
    
    reset = True
    try:

        #check_accel(a, bus_accel, set_and_status)
        print(a.x_val, a.y_val, a.z_val)
        #need to clear any alert regs now. Alert only goes to zero when a 1 is written to flag
        bus_pir.write_byte_data(0x50,0x01, 0x03)
        bus_pir.write_byte_data(0x54,0x01, 0x03)
        bus_pir.write_byte_data(0x55,0x01, 0x03)
        while True:
                if datetime.date.today() != set_and_status.last_del_date:
                    del_videos() 
                gpio_loop_running.wait()
                while not(gpio_loop_running.is_set()):
                    check_accel(a, bus_accel, set_and_status)
                    if a.accel_flag:
                        #GPIO.remove_event_detect(accel_int_pin)
                        accel_flag_write(a.accel_flag)
                        gpio_loop_running.clear()
                        with a_lock:
                            a_int = True
                        reset = True #property lines are no longer correct - need to go into reset 
                    time.sleep(0.1)
                #if in setup - start new sensor setup 
                if (reset == True) and not(record.live_video):
                    #trigger a new setup 
                    print("new setup reset")
                    new_setup()
                    reset = False
                    record.in_setup = False
                #gpio_loop_running.wait()
                if gpio_loop_running.is_set():
                    #continue
                    read(pir_flags, bus_pir, set_and_status)
                    if pir_flags.motion_flag or record.live_video: #f there has been motion or want to do live recording
                        cam(s_move_time,lock) #start camera event 
                        #need to clear any alert regs now. Alert only goes to zero when a 1 is written to flag
                        bus_pir.write_byte_data(0x50,0x01, 0x03)
                        bus_pir.write_byte_data(0x54,0x01, 0x03)
                        bus_pir.write_byte_data(0x55,0x01, 0x03)
                    if a.accel_flag:
                        #GPIO.remove_event_detect(accel_int_pin)
                        accel_flag_write(a.accel_flag)
                        gpio_loop_running.clear()
                        with a_lock:
                            a_int = True
                        reset = True #property lines are no longer correct - need to go into reset 
                    if record.no_correct_prop_lines:
                        gpio_loop_running.clear()
                
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("Program interrupted.")



def ai_event_loop():
    while True:
        #ai_loop_event.wait()
        #print("start ai loop")
        #ai_fake_funciton()
        if not(ai_video_queue.empty()):
            video_path = ai_video_queue.get()
            time.sleep(1)
            #print("sent",record.output_name)
            #ai_loop_event.clear() 
            Model_with_jetson.model_with_jetson_main(video_path)

        #ai_loop_event.clear()
        time.sleep(0.1)

def cam_img_processing(shared_array, lock):#output_name, cam_event):
    print("Start cam img")
    cam_properties = None
    while True:
        #cam_img_event.wait()
        cam_event.wait()
        if not(c_queue.empty()):
            cam_properties = c_queue.get()
        
        if cam_properties == None:
            cam_event.clear()

        time.sleep(3)
        print("\n\n\n\n\START AJDJSJFJJJFDJJSDAJFJD\n\n\n\n")
        image_capture_and_processing(cam_properties, shared_array, lock)#output_name, cam_event)

def serial_process(s_move_time,lock):#command_queue, response_queues):
    """
    The worker process that handles serial communication.
    It continuously reads from the command_queue, sends the command over serial,
    reads the response, and sends the response back via the appropriate response queue.
    """
    # Setup the serial port if needed.
    # For example: ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
    
    while True:
        # Expecting a tuple: (process_id, command)
        while command_queue.empty():
            time.sleep(0.0005)
        
        process_id, command = command_queue.get()

        if process_id == 'motion_detection' or process_id == 'app_movement':
            #s_move_queue.put(time.time())
            with lock:
                s_move_time.value = time.time()
        
        
        #print(f"Serial worker received command from {process_id}: {command}")
        
        # Send the command over serial.
        # Uncomment if using an actual serial port:
        ser.write(command.encode('UTF-8'))
        response = ser.readline()
        hexpos= int(response.strip(), 16)
        #time.sleep(0.5)

        #print(f"Serial worker sending response to {process_id}: {hexpos}")
        
        # Put the response into the corresponding response queue.
        response_queues[process_id].put(hexpos)
        time.sleep(0.0005)


def bat_status_loop():
    #GPIO.add_event_detect(battery_pin, GPIO.RISING, callback=on_battery())
    on_batt = False
    file_name = r'/home/camcs/server/uploads/battery_status/battery_status.csv'
    while True:
        b_l = []
        for i in range(20):
            b = GPIO.input(battery_pin)
            b_l.append(b)
            #print("bat")
            time.sleep(0.01)

        if 0 in b_l:
            if on_batt != True:
                on_batt = True
                print("Battery:", b)
                rows = [["Battery Status:"], [1]]
                with open(file_name, 'w', newline='') as f:
                    fwrite = csv.writer(f, delimiter = ',')
                    for i in range(len(rows)):
                        fwrite.writerow(rows[i])
        else:
            if on_batt != False:
                on_batt = False
                rows = [["Battery Status:"], [0]]
                with open(file_name, 'w', newline='') as f:
                    fwrite = csv.writer(f, delimiter = ',')
                    for i in range(len(rows)):
                        fwrite.writerow(rows[i])
        

        time.sleep(10) #check every 2 min
    #this will be for battery status pin checking 

if __name__ == '__main__':

    print("start threading")

    serial_worker = multiprocessing.Process(target=serial_process, args = (s_move_time,lock,)) #process for serial 
    serial_worker.start() #start serial - infinite loop

    gpio_thread = threading.Thread(target=gpio_event_loop, args = (s_move_time,lock,)) #gpio loop
    gpio_thread.daemon = True #if this ends - dont end process
    gpio_thread.start() #start. this is infinite loop

    cam_img_processing_thread = multiprocessing.Process(target=cam_img_processing, args=(shared_array, lock,))#image capture and processing
    cam_img_processing_thread.daemon = True #don't end program if this ends
    cam_img_processing_thread.start() #start - infinite lopop

    #ai_thread = multiprocessing.Process(target=ai_event_loop)
    ai_thread = threading.Thread(target=ai_event_loop) #ai processing loop
    ai_thread.daemon = True #don't end program if this ends
    ai_thread.start() #start - infinite loop

    #bat_checking_thread = threading.Thread(target=bat_status_loop)
    bat_checking_thread = multiprocessing.Process(target=bat_status_loop) #looking at if using battery or not 
    bat_checking_thread.daemon = True #don't end process if this ends
    bat_checking_thread.start() #start the infinite loop

    # Run Flask in the main thread
    run_flask()

bus_accel.close()
bus_pir.close()
GPIO.cleanup()