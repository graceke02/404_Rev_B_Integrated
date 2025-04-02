import time
import serial
#import matplotlib
import numpy as np
import cv2
import math
from variables import record, set_and_status,ser, bus_pir, prop_lines

from variables import c_queue, cam_properties
from variables import command_queue, response_queues

focalLength = 600

panWidth = 640
panHeight = 480

#ser = serial.Serial('/dev/ttyTHS1', 4800, timeout=1)

def getPano(angInit, angFinal, step):
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    images = []
    angles = []
    setAngle = angInit
    
    #img = image.capture
    #images.append(img)
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)

    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
    cap.set(cv2.CAP_PROP_FPS,15)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    camera_matrix = np.load("camera_matrix.npy")
    print(camera_matrix)
    dist_coeffs = np.load("dist_coeff.npy")
    readAngle()
    print(writeAngle(setAngle))
    print(setAngle)
    print(writeAngle(setAngle))
    print("x")
    time.sleep(5)
    # Get optimal new camera matrix
    for i in range(10):
        ret, frame = cap.read()
        cv2.waitKey(1)

    #a = readAngle()
    h, w = frame.shape[:2]
    new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(camera_matrix, dist_coeffs, (w, h), 0.75, (w, h))

    #frame = cv2.flip(frame,-1)
        
    # Undistort the frame
    undistorted = cv2.undistort(frame, camera_matrix, dist_coeffs, None, new_camera_matrix)
    #height,width = frame.shape[:2]
    # Crop to ROI
    x, y, w, h = roi
    undistorted = undistorted[y:y+h, x:x+w]
    undistorted = undistorted[:480, :640]
    undistorted = cv2.flip(undistorted, -1)
    #images.append(undistorted)
    ser.reset_input_buffer()
    #angles.append(readAngle())
    
    while (setAngle <= angFinal):
        setAngle += step
        print(writeAngle(setAngle))
        time.sleep(2)
        for i in range(10):
            ret, frame = cap.read()
        a = readAngle()
        #h, w = frame.shape[:2]
        #new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(camera_matrix, dist_coeffs, (w, h), 0.75, (w, h))

        #frame = cv2.flip(frame,0)
            
        # Undistort the frame
        undistorted = cv2.undistort(frame, camera_matrix, dist_coeffs, None, new_camera_matrix)
        #height,width = frame.shape[:2]
        # Crop to ROI
        x, y, w, h = roi
        undistorted = undistorted[y:y+h, x:x+w]
        undistorted = undistorted[:480, :640]
        undistorted = cv2.flip(undistorted, -1)
        #imaimage.capture
        images.append(undistorted)
        
        angles.append(a)
        
    cap.release()
    writeAngle(0x400)
    #p = ser.readline()
    return images, angles

def writeAngle(angle):
    command = "CO0" + hex(angle)[2:] + '\n'
    command_queue.put(("pano", command))
    while response_queues["pano"].empty():
        time.sleep(0.001)
    hexpos = response_queues["pano"].get()
    #ser.write(command.encode('utf-8'))
    return hexpos #ser.readline()
def readAngle():
    #global pan_position
    prefix = '0000' #prefix of what to send to motor control
    command = f"CR{prefix}\n" #full command value
    command_queue.put(("pano", command))
    while response_queues["pano"].empty():
        time.sleep(0.001)
    angle = response_queues["pano"].get()
    #ser.write(command.encode('utf-8'))
    #ser.write(command.encode('UTF-8')) #send to motor controller
    print("sent command", command)
    return angle

def pan_setup():
    images, angles = getPano(600,1400,150)
    #print(angles)
    mingle, maxgle = 400, 0
    pixAngles=[]

    for i,img in enumerate(images):
        file = str(i) + "out.jpg"
        cv2.imwrite(file, img)

    for i, img in enumerate(images):
        columnAngles=[]
        pangle = float(angles[i]*float(360/4096))
        print(pangle)
        #img = cv.imread(os.path.join(imagefolder, item))
        xlen = img.shape[1]
        centx = (xlen - 1) / 2.0
        #print(centx)
        for col in range(xlen):
            angle = math.degrees(math.atan((col - centx) / focalLength)) + pangle
            if angle < mingle:
                mingle = angle
            if angle > maxgle:
                maxgle = angle
            columnAngles.append(angle)
        pixAngles.append(columnAngles)
    print("MINGLE:", mingle, maxgle)
    columnBins = np.linspace(mingle, maxgle, panWidth + 1)

    # Initialize panorama with float32 to handle fractional weights
    panorama = np.zeros((panHeight, panWidth, 4), dtype=np.float32)

    print("About to start pano creation")
    t_pan = time.time()
    for i, img in enumerate(images):
        print("another i", i)
        #img = cv.imread(os.path.join(imagefolder, item))
        if img is None:
            continue
        img_float = img.astype(np.float32)  # Convert to float for weighting
        xlen, ylen = img.shape[1], img.shape[0]
        centx = (xlen - 1) / 2.0
        max_distance = centx

        # Calculate weights for each column (triangular weighting)
        columns = np.arange(xlen)
        distances = np.abs(columns - centx)
        weights = 1.0 - 1*(distances / max_distance)
        weights = np.clip(weights, 0.0, 1.0)  # Ensure non-negative
        #print(weights)
        bindices = np.searchsorted(columnBins, pixAngles[i], side='right') - 1
        bindices = np.clip(bindices, 0, panWidth - 1)

        #print(bindices)

        
        for col in range(xlen):
            #print(col)
            bin_idx = bindices[col]
            weight = weights[col]
            # Accumulate weighted contributions
            panorama[:, bin_idx, :3] += img_float[:, col, :] * weight
            panorama[:, bin_idx, 3] += weight

    # Normalize by the accumulated weights
    total_weights = panorama[:, :, 3]
    total_weights_safe = np.where(total_weights == 0, 1.0, total_weights)
    panorama[:, :, :3] = panorama[:, :, :3] / total_weights_safe[:, :, np.newaxis]

    # Convert to uint8 for saving/display
    panorama_rgb = np.clip(panorama[:, :, :3], 0, 255).astype(np.uint8)

    maxgle = maxgle
    mingle = mingle
    imgwidth = 640
    panfov = maxgle - mingle 
    panwidth = int((panfov/56.07)*imgwidth)
    print("time for creating pano:", time.time()-t_pan)
    #print(record.panfov)
    #print("width", record.panwidth)
    #print("fov", record.fov)
    #print("imgwidth", record.imgwidth)
    # Save the panorama
    #cv2.imshow('pano',panorama_rgb)
    cv2.imwrite('/home/camcs/server/uploads/xypixelcolor/pano.jpg', panorama_rgb)
    time.sleep(1)
    print("\n\nDone with Pano\n\n")
    #print(mingle,maxgle)    
    record.in_setup = False
    #time.sleep(5)
    #Scv2.destroyAllWindows()

    c = cam_properties
    #c = c_queue.get()
    c["maxgle"] = maxgle
    c["mingle"] = mingle
    c["imgwidth"] = imgwidth
    c["panfov"] = panfov
    c["panwidth"] = panwidth

    c_queue.put(c)


