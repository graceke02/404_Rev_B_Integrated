import cv2
import numpy as np
import time
from smbus2 import SMBus
import datetime
import serial
import csv
import RPi.GPIO as GPIO
import signal
import threading
from flask import Flask
import multiprocessing
from accel_functions import basis, accel_flag_write


#global frame_streaming

class property_lines:
    points = []
    height = 480
    width = 640

    #eventually should be able to initialize, which will define points and the mask
    '''
    def __init__(self):
        #need to define points before creating the polygon
        mask = np.zeros((self.height,self.width), dtype=np.uint8) #set up so cv2 can use
        self.poly = cv2.fillPoly(mask, [self.points], (255,255,255)) #make a filled polygon
    '''

    def define_points(self): #, file_name):
         #p = np.array([['346', '99'], ['491', '26'], ['576', '154'], ['442', '244'], ['250', '221'], ['427', '155']], dtype = np.int32)
         #self.points = p.reshape((-1,1,2)) #reshape format
        
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

        self.points = points
        #print(points)
        

    
    '''
    def define_mask(self):
        self.mask = np.zeros((self.height,self.width), dtype=np.uint8) #set up so cv2 can use
        cv2.fillPoly(self.mask, [self.points], (255,255,255)) #make a filled polygon
    '''


#define a class to use for a recording/video parameters  
class recording:
    fourcc = cv2.VideoWriter_fourcc(*'mp4v') #video format
    min_record_time = 10
    fps = 15 #frames per second
    height = 480
    width = 640
    
    record_flag = False
    output_name = r'/home/camcs/server/uploads/videos/' #initialize with just the folder name
    #output_name = r'/home/camcs/uploads/videos/'

    record_start_time = 0 #initialize at zero #may not need this 
    #@min_record_time = 10
    #out = 0 #video writer variable
    done_videoing = False

    no_correct_prop_lines = True

    #live video variable
    live_video = False

    #if in setup
    in_setup = False

    #movement
    camera_matrix = None
    dist_coeffs = None
    new_camera_matrix = None
    roi = None

    #camera variables 
    fov = 56.07
    imgwidth = None
    mingle = None
    maxgle = None
    panfov = None #maxgle-mingle
    panwidth = None #int((panfov/fov)*imgwidth)
    recording_just_started = False

    #may just put this in a 
    def check_flags(self, motion_flag, motion_time):
        #print("record check")
        #print("Record flag", self.record_flag)
        #print("motion flag", motion_flag)
        #record flag needs to be set to false if going to start setup
        if (motion_flag or self.live_video) and not(self.record_flag) and not(self.in_setup): #motion just detected - set up new recording
            print("Start recording")
            self.record_flag = True #set record to true
            self.setup_andname() #set up name 
            print(self.output_name)
            self.record_start_time = time.time() #may not need this 
            self.recording_just_started = True
            self.done_videoing = False
            #return True #return true - want to record
        elif ((self.record_flag and not(self.in_setup) and ((time.time() - motion_time) < self.min_record_time))) or self.live_video: #check if record flag is true - if need to keep filming 
            #keep recording - record_flag still true
            #live_video still true 
            #print("\n\n",(self.record_flag and not(self.in_setup))
            #print(((time.time() - motion_time) < self.min_record_time))
            #print(self.live_video)
            #print("\n\n")
            self.record_flag = True
            self.recording_just_started = False
            #print("Keep recording", (time.time() - motion_time))
            #return True
        #now check if record_flag true and reached min recording time - need to stop recording
        elif self.record_flag and not((time.time() - motion_time) < self.min_record_time) and not(self.live_video): # and not(self.live_video):
            #record flag is true, but over time and not doing live video --> finishing videoing 
            if not(self.live_video):
                self.record_flag = False #want to stop recording 
                self.done_videoing = True
                self.live_video = False
                print("Done recording")
            #return False
        """ else:
            self.record_flag = False
            self.recording_just_started = False
            self.done_videoing = False  """

        #else:
            #record_flag is false, and no motion detected 
            #return False
    
    def check_live(self):
        print("\n\nChecking\n\n")
        
        fn = r'/home/camcs/server/uploads/live_streaming/LiveVideoOnOffStatus.csv'

        rows = []
        with open(fn, newline = '') as f:
                fread = csv.reader(f)
                for row in fread:
                    rows.append(row)

        if int(rows[1][0]) == 0:
            self.live_video = False
            print("Changed")
        if int(rows[1][0]) == 1:
            self.live_video = True
        else:
            self.live_video = False
            
        
    
    #def check_time(self, min_record_time, motion_time):
     #   if motion < 
    
    #set up name 
    def setup_andname(self):
        #file name convention: X_MMDDYYYY HHMMSS.file type
        #X is if there is an identified user or not
        #print("name")
        print("\n\nNAME THIS BITCH\n\n")
        x = str(datetime.datetime.now())
        s = x.split(" ")
        date = s[0].split('-')
        time_h = s[1].split(":")
        sec = time_h[2].split(".")
        l = date[1] + date[2] + date[0] + ' ' + time_h[0] +time_h[1] + sec[0] + '.mp4'
        #self.output_name = r'/home/camcs/uploads/videos/' + repr(l)[1:-1]
        self.output_name = r'/home/camcs/server/uploads/raw_videos/' + repr(l)[1:-1]
        

class settings_and_status:
    auto_delete = 35

    cam_status = True #camera working
    pir_status = True #pir are working
    accel_status = True #accel is working
    motor_status = True #motor is working 


    position = 0
    
    #
    camera_on = True #camera on or off from server

    #camera movement on or off
    camera_movement = True

    #battery status 
    bat_status = False

    #last time videos were delted
    last_del_date = 0

    def set_delete_time(self):
        rows = []

        file_name = r'/home/camcs/server/uploads/autodelete/SettingsVideoAutoDeleteOutput.csv'

        with open(file_name, newline = '') as f:
            fread = csv.reader(f)
            for row in fread:
                rows.append(row)

        
        for i in range(1,len(rows)):
            #####FOR NOW ONLY TESTING, SO 
            #CHECK HEADERS TO GET CORRECT DATA
            if rows[0][0] == 'Video Delete Time (Days):':
                self.auto_delete = rows[1][0]
        
        print(self.auto_delete)
    
    def get_cam_movement_status(self):
        rows = []

        file_name = r'/home/camcs/server/uploads/camera_motion/camera_motion_status.csv'

        with open(file_name, newline = '') as f:
            fread = csv.reader(f)
            for row in fread:
                rows.append(row)

        if int(rows[1][0]) == 0:
            self.camera_movement = False
        if int(rows[1][0]) == 1:
            self.camera_movement = True
        else:
            self.camera_movement = False
    
    def get_cam_status_on_off(self):
        rows = []

        file_name = r'/home/camcs/server/uploads/camera_status/camera_status.csv'

        with open(file_name, newline = '') as f:
            fread = csv.reader(f)
            for row in fread:
                rows.append(row)

        print(rows, rows[1][0])
        if int(rows[1][0]) == 0:
            self.cam_status = False
        if int(rows[1][0]) == 1:
            self.cam_status = True
        else:
            self.cam_status = False

    def set_battery_status(self):
        if self.bat_status:
            x = 1
        else:
            x = 0
        
        file_name = r'/home/camcs/server/uploads/battery_status/battery_status.csv'

        rows = [["Battery Status:"], [x]]
        with open(file_name, 'w', newline='') as f:
            fwrite = csv.writer(f, delimiter = ',')
            for i in range(len(rows)):
                fwrite.writerow(rows[i])

class pir:

    motion_flag = False
    motion_time = 0

    pir1_flag = False #pir 1 motion flag
    pir2_flag = False #pir 2 motion flag
    pir3_flag = False #pir 3 motion flag
    
    pir1_motion_time = 0
    pir2_motion_time = 0
    pir3_motion_time = 0

    motion_threshold = 148 #1.9V - ADC value. val = (1.9/3.3)*256
    #motion_ended_threshold = 0.5 #so this value is kind of unknown - but from observing this is good
    motion_ended_threshold = 39 #0.5V - ACD value. val = (0.5/3.3)*256



class accel:
    address = 0x18
    #accel accounting for instability
    not_random_count = 3 #number of consecutive triggers to be not random

    #accel basis
    x_basis = 1000
    y_basis = 1000
    z_basis = 1000

    #3 std deviations from mean - tolerance
    x_tol_u = 1000 #x tolerance, upper bound
    y_tol_u = 1000 #y tolerance, upper bound
    z_tol_u = 1000 #z tolerance, upper bound

    x_tol_l = -1000 #x tolerance, lower bound
    y_tol_l = -1000 #y tolerance, lower bound
    z_tol_l = -1000 #z tolerance, lower bound

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
        
        """ if abs(self.x_val) >  self.x_tol_u:
            self.int_count += 1 """
        if (self.y_val) > self.y_tol_u:
            self.int_count += 1 
        elif (self.z_val) > self.z_tol_u:
            self.int_count += 1 
        elif (self.y_val) < self.y_tol_l:
            self.int_count += 1 
        elif (self.z_val) < self.z_tol_l:
            self.int_count += 1 
        else:
            #no accel movement detected - set everything to zero 
            self.int_count = 0
        """ elif abs(self.x_val) < self.x_tol_l:
            self.int_count += 1  """
        



def new_setup(): #reset all variables 
    global a, prop_lines, pir_flags, record, set_and_status 
    print("new setup")
    #prop_lines.define_points()
    #a.accel_flag = False
    basis(a, bus_accel, set_and_status)
    accel_flag_write(False)
    a.accel_flag = False
    pir_flags.pir1_flag = False
    pir_flags.pir2_flag = False
    pir_flags.pir3_flag = False
    print("Bais", a.x_basis,a.y_basis, a.z_basis)

    #GPIO.add_event_detect(pir_int_pin, GPIO.RISING, callback=cam) 
    #GPIO.add_event_detect(accel_int_pin, GPIO.RISING, callback=accel_event)



#global ser, bus_pir, bus_accel
#global a, prop_lines, pir_flags, record, set_and_status 

global ser
ser = serial.Serial('/dev/ttyTHS1', 38400, timeout=1)
#time.sleep(2)

global bus_pir
bus_num_pir = 7
bus_pir  = SMBus(bus_num_pir)

global bus_accel
bus_num_accel = 1 
#start the bus
bus_accel = SMBus(bus_num_accel)

global a
a = accel()
#basis(a, bus_accel)

global prop_lines
prop_lines = property_lines()
prop_lines.define_points()

global pir_flags
pir_flags = pir()

global set_and_status 
set_and_status = settings_and_status()
set_and_status.set_battery_status()

global record
record = recording()


output_name_que = multiprocessing.Queue()

cam_event = multiprocessing.Event()
cam_event.clear()


camera_matrix = np.load("camera_matrix.npy")
dist_coeffs = np.load("dist_coeff.npy")
# Get optimal new camera matrix
#ret, frame = cap.read()
#h, w = frame.shape[:2]
new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(camera_matrix, dist_coeffs, (1920, 1080), 0.75, (1920, 1080))
cam_properties = {"roi":roi, "camera_matrix":camera_matrix, "new_camera_matrix":new_camera_matrix, "dist_coeffs":dist_coeffs, "fov":56.07, "imgwidth":640, "mingle":None, "maxgle":None, "panfov":None, "panwidth":None} 

#for initial testing:
######################################################DELETE - ONLY FOR TESTING
cam_properties["maxgle"] = 180
cam_properties["mingle"] = 0
cam_properties["imgwidth"] = 640
cam_properties["panfov"] = cam_properties["maxgle"] - cam_properties["mingle"]
cam_properties["panwidth"] = int((cam_properties["panfov"]/cam_properties["fov"])*cam_properties["imgwidth"])
####################################################################


c_queue = multiprocessing.Queue()
c_queue.put(cam_properties)

frame_queue = multiprocessing.Queue()
ai_video_queue = multiprocessing.Queue()

shared_array = multiprocessing.Array('B', 480*640*3, lock=False)

s_move_time = multiprocessing.Value('d', 0.0)


lock = multiprocessing.Lock()

position_que = multiprocessing.Queue()


command_queue = multiprocessing.Queue()
    
# Create dedicated response queues for each client process.
response_queues = {
    'img_blocking': multiprocessing.Queue(),
    'pano': multiprocessing.Queue(),
    'motion_detection' : multiprocessing.Queue(),
    'app_movement' : multiprocessing.Queue()
}