from flask import Flask, request, jsonify, send_from_directory, render_template_string, Response
from flask_socketio import SocketIO
import os
import sqlite3
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import multiprocessing
import cv2
import numpy as np
#from flask_cors import CORS
from queue import Queue

import RPi.GPIO as GPIO
#from main import new_setup
from variables import record, set_and_status, bus_pir, ser, prop_lines #, frame_streaming
from gimbal import app_pan
from cam_simple import cam#, frame_queue
from variables import frame_queue
from setup_pano import pan_setup

from gimbal import write_pan_position

from variables import shared_array, lock
from variables import new_setup


# Initialize Flask app
app = Flask(__name__)
#CORS(app)

#global a_int #if accel interrupt 
a_int = False
a_lock = multiprocessing.Lock()

#run the gpio loop event
gpio_loop_running = multiprocessing.Event()
gpio_loop_running.clear()

# Initialize Flask app
app = Flask(__name__)
#CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# Configure the base upload folder
app.config['UPLOAD_FOLDER'] = 'uploads'  # Base upload directory
subfolders = {
    'USER_UPLOAD_FOLDER': 'users',
    'VIDEO_UPLOAD_FOLDER': 'videos',
    'ENCODER_UPLOAD_FOLDER': 'encoder_status',
    'XYPIXELCOLOR_UPLOAD_FOLDER': 'xypixelcolor',
    'AUTO_DELETE_FOLDER': 'autodelete',
    'CAMERA_STATUS_FOLDER' : 'camera_status',
    'CAMERA_MOTION_FOLDER' : 'camera_motion',
    'BATTERY_STATUS_FOLDER' : 'battery_status',
    'RAW_VIDEO_FOLDER': 'raw_videos',
    'LIVE_STREAMING_FOLDER' : 'live_streaming',
    'IP_ADDRESS_FOLDER' : 'ip_address',
    'START_SETUP_FOLDER' : 'start_setup'
    #'SENSOR_MOVEMENT_FOLDER' : 'sensor_movement',
}

# Set subfolder paths dynamically
for key, subfolder in subfolders.items():
    app.config[key] = os.path.join(app.config['UPLOAD_FOLDER'], subfolder)

# Ensure all folders exist
for key, folder in app.config.items():
    if key.endswith('_FOLDER') and isinstance(folder, str):  # Ensure we're only working with folder paths
        print(f"Creating folder: {folder}")
        os.makedirs(folder, exist_ok=True)

# Define allowed extensions
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov', 'csv', 'xlsx','xls'}

# Initialize the webserver
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            photo_path TEXT UNIQUE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_path TEXT UNIQUE NOT NULL,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Check if the file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route('/')
def home():
     """Render the homepage with embedded video stream."""
     return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Live Video Stream</title>
    </head>
    <body>
        <h1>Live Video Stream</h1>
        <img src="/video_feed" width="640" height="480">
    </body>
    </html>
    '''
@app.route('/video_feed')
def video_feed():
    """Return the streaming response."""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    #return jsonify({'message': 'Video'}), 400
camera = None
streaming = False
#lock = multiprocessing.Lock()


def generate_frames():
    #cam(frame_queue)
    #cap = cv2.VideoCapture(0) #, cv2.CAP_V4L2)
   #if not(cap.isOpened()):
    #    print("Cap not open")
    #global a_int, set_and_status, ser, prop_lines
    record.live_video = True
    print("generate")
    if not(record.record_flag):
        gpio_loop_running.set()
    
    #record.live_video = True
    
    while True:
        with lock:
            # Copy the shared frame to avoid holding the lock while displaying
            frame = np.frombuffer(shared_array, dtype=np.uint8).reshape((480,640,3)).copy()
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n\r\n')
            
        """ if not frame_queue.empty():
            frame = frame_queue.get()
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n\r\n')
            
            print("got frame")
        else:
            print(frame_queue.empty())
            print("No frame") """
        
        time.sleep(0.01)
    


# Route for serving uploaded files
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        return jsonify({'message': 'File not found'}), 404


# Route for uploading photos
@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    if 'photo' not in request.files:
        return jsonify({'message': 'No file part'}), 400

    photo = request.files['photo']
    if photo.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    if photo and allowed_file(photo.filename):
        # Save the file in the "users" folder (Primary storage)
        filename = photo.filename
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolders['USER_UPLOAD_FOLDER'], filename)
        
        # Prevent duplicate photo uploads
        if os.path.exists(save_path):
            return jsonify({'message': 'Photo already exists', 'photo_path': save_path}), 409

        photo.save(save_path)

        # Store only the filename in the database
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (name, photo_path) VALUES (?, ?)", ("User", filename))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'message': 'Photo already exists in the database'}), 409
        conn.close()



        return jsonify({'message': 'Photo uploaded successfully', 'photo_path': save_path}), 201
    else:
        return jsonify({'message': 'Invalid file format'}), 400


@app.route('/upload_video', methods=['POST'])
def upload_video():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    allowed_extensions = {'avi', 'mov', 'mp4', 'csv', 'xlsx', 'xls'}
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return jsonify({'message': 'Invalid file format'}), 400

    # Save the file in the video upload folder
    filename = file.filename
    save_path = os.path.join(app.config['VIDEO_UPLOAD_FOLDER'], filename)

    if os.path.exists(save_path) and filename.endswith('.csv'):
        # Overwrite the existing CSV file
        file.save(save_path)
        return jsonify({'message': 'Successfully overwritten and updated', 'file_path': save_path}), 200

    if os.path.exists(save_path):
        return jsonify({'message': 'File already exists', 'file_path': save_path}), 409

    file.save(save_path)

    # Store only the filename in the database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO files (file_name, timestamp) VALUES (?, ?)", (filename, timestamp))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'message': 'File already exists in the database'}), 409
    conn.close()

    return jsonify({'message': 'File uploaded successfully', 'file_path': filename}), 201

@app.route('/upload_raw_video', methods=['POST'])
def upload_raw_video():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    allowed_extensions = {'mp4'}
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return jsonify({'message': 'Invalid file format'}), 400

    # Save the file in the raw video folder
    filename = file.filename
    save_path = os.path.join(app.config['RAW_VIDEO_FOLDER'], filename)

    if os.path.exists(save_path):
        return jsonify({'message': 'File already exists', 'file_path': save_path}), 409

    file.save(save_path)

    # Store only the filename in the database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO files (file_name, timestamp) VALUES (?, ?)", (filename, timestamp))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'message': 'File already exists in the database'}), 409
    conn.close()

    return jsonify({'message': 'Raw video uploaded successfully', 'file_path': filename}), 201

@app.route('/get_photo/<filename>', methods=['GET'])
def get_photo(filename):
    try:
        return send_from_directory(app.config['USER_UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        return jsonify({'message': 'Photo not found'}), 404

@app.route('/get_video/<filename>', methods=['GET'])
def get_video(filename):
    # Validate video file extensions
    valid_video_extensions = {'avi', 'mov', 'mp4', 'xlsx' , 'csv', 'xls'}
    if '.' not in filename or filename.rsplit('.', 1)[1].lower() not in valid_video_extensions:
        return jsonify({'message': 'Invalid video file type'}), 400

    # Path to the video file
    video_path = os.path.join(app.config['VIDEO_UPLOAD_FOLDER'], filename)

    # Check if the file exists
    if not os.path.exists(video_path):
        return jsonify({'message': 'Video not found'}), 404

    # Stream the video
    def generate():
        with open(video_path, 'rb') as video_file:
            while chunk := video_file.read(1024 * 1024):  # Read in chunks (1 MB)
                yield chunk

    # Set the correct MIME type for video streaming
    mime_type = 'video/' + filename.rsplit('.', 1)[1].lower()
    return Response(generate(), mimetype=mime_type)

@app.route('/get_raw_video/<filename>', methods=['GET'])
def get_raw_video(filename):
    valid_video_extensions = {'avi', 'mov', 'mp4'}
    if '.' not in filename or filename.rsplit('.', 1)[1].lower() not in valid_video_extensions:
        return jsonify({'message': 'Invalid raw video file type'}), 400

    video_path = os.path.join(app.config['RAW_VIDEO_FOLDER'], filename)

    if not os.path.exists(video_path):
        return jsonify({'message': 'Raw video not found'}), 404

    # Stream the raw video
    def generate():
        with open(video_path, 'rb') as video_file:
            while chunk := video_file.read(1024 * 1024):  # Read in chunks (1 MB)
                yield chunk

    mime_type = 'video/' + filename.rsplit('.', 1)[1].lower()
    return Response(generate(), mimetype=mime_type)

@app.route('/upload_excel/<folder_name>', methods=['POST'])
def upload_excel(folder_name):
    folder_mapping = {
        'autodelete': app.config['AUTO_DELETE_FOLDER'],
        'encoder_status': app.config['ENCODER_UPLOAD_FOLDER'],
        'xypixelcolor': app.config['XYPIXELCOLOR_UPLOAD_FOLDER'],
        'camera_status': app.config['CAMERA_STATUS_FOLDER'],
        'camera_motion': app.config['CAMERA_MOTION_FOLDER'],
        'battery_status': app.config['BATTERY_STATUS_FOLDER'],     # Needs notification
        'live_streaming' : app.config['LIVE_STREAMING_FOLDER'],
        'ip_address' : app.config['IP_ADDRESS_FOLDER'],
        'start_setup' : app.config['START_SETUP_FOLDER']
    }
    global a_int, set_and_status, ser, prop_lines #bus_pir

    #new_setup()
    #gpio_loop_running.set()

    if folder_name not in folder_mapping:
        return jsonify({'message': 'Invalid folder name'}), 400

    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    filename = file.filename
    save_path = os.path.join(folder_mapping[folder_name], filename)

    # Check if a CSV file is being reuploaded (overwritten)
    if os.path.exists(save_path) and filename.lower().endswith('.csv'):
        file.save(save_path)
        print("##########################################",filename)
        print("##########################################",save_path)
        if filename.lower() == 'propertylinesetupxypixelcolorfile.csv':
            with a_lock: #lock a 
                a_int = False 
            #new_setup()
            print("#################################################################")
            prop_lines.define_points()
            record.in_setup = False #only false once accel basis is taken. done in setup one
            gpio_loop_running.set()
            record.no_correct_prop_lines = False
            
        if filename.lower() == 'camerarotationencoderstatus.csv':
            #should be able to pan even if movement is turned off 
            app_pan()
        if filename.lower() == 'camera_status.csv':
            set_and_status.get_cam_status_on_off()
        if filename.lower() == 'camera_motion_status.csv':
            set_and_status.get_cam_movement_status()
        if filename == 'LiveVideoOnOffStatus.csv':
            record.check_live()
        if filename.lower() == 'start_setup.csv':
            record.in_setup = True
            f_path = '/home/camcs/server/uploads/xypixelcolor/pano.jpg'
            if os.path.exists(f_path):
                os.remove(f_path)
            #if os.path.exists(save_path):
             #   return jsonify({'message': 'File already exists', 'file_path': save_path}), 409
            #pan_setup()
            pano_process = multiprocessing.Process(target=pan_setup)
            pano_process.start()
            pano_process.join()
            new_setup()


        return jsonify({'message': 'Successfully overwritten and updated', 'file_path': save_path}), 200

    # Prevent duplicate non-CSV file uploads (optional)
    if os.path.exists(save_path):
        return jsonify({'message': 'File already exists', 'file_path': save_path}), 409

    # Save any type of file
    file.save(save_path)
    return jsonify({'message': 'File uploaded successfully', 'file_path': save_path}), 201


#####define button click receiving 
@app.route('/moveLeft', methods=['POST'])
def move_left():
    #one move left 150
    move = 150
    app_pan('left', move)
    return jsonify({'message': 'Moved Left'})


@app.route('/moveRight', methods=['POST'])
def move_right():
    #one move left 150
    move = 150
    app_pan('right', move)
    return jsonify({'message': 'Moved Right'})

# Add routes to retrieve Excel files
@app.route('/get_excel/<folder_name>/<filename>', methods=['GET'])
def get_excel(folder_name, filename):
    # Map folder names to their paths
    folder_mapping = {
        'autodelete': app.config['AUTO_DELETE_FOLDER'],
        'encoder_status': app.config['ENCODER_UPLOAD_FOLDER'],
        'xypixelcolor': app.config['XYPIXELCOLOR_UPLOAD_FOLDER'],
        'camera_status': app.config['CAMERA_STATUS_FOLDER'],
        'camera_motion': app.config['CAMERA_MOTION_FOLDER'],
        'battery_status': app.config['BATTERY_STATUS_FOLDER'],
        'live_streaming' : app.config['LIVE_STREAMING_FOLDER'],
        'ip_address' : app.config['IP_ADDRESS_FOLDER'],
        'start_setup' : app.config['START_SETUP_FOLDER']
    }
    
    if folder_name not in folder_mapping:
        return jsonify({'message': 'Invalid folder name'}), 400
    if filename.lower() == 'camerarotationencoderstatus.csv':
        write_pan_position()
        time.sleep(0.5)
    # Fetch the file
    folder_path = folder_mapping[folder_name]
    try:
        return send_from_directory(folder_path, filename)
    except FileNotFoundError:
        return jsonify({'message': 'File not found'}), 404


# Route to delete a missing file that was previosuly added
@app.route('/delete_missing_files', methods=['DELETE'])
def delete_missing_files():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()


    # Remove missing photos
    cursor.execute("SELECT id, photo_path FROM users")
    photos = cursor.fetchall()
    for photo_id, photo_path in photos:
        if not os.path.exists(photo_path):
            cursor.execute("DELETE FROM users WHERE id = ?", (photo_id,))


    # Remove missing videos
    cursor.execute("SELECT id, video_path FROM videos")
    videos = cursor.fetchall()
    for video_id, video_path in videos:
        if not os.path.exists(video_path):
            cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))


    conn.commit()
    conn.close()


    return jsonify({'message': 'Missing files removed from the database'}), 200

@app.route('/delete_file', methods=['POST'])
def delete_file():
    data = request.get_json()
    folder = data.get('folder')
    file_name = data.get('file')
    base_path = "C:/Users/denni/Flask_database/app/uploads"  # Update to your correct base path

    # Construct full path
    folder_path = os.path.join(base_path, folder)
    file_path = os.path.join(folder_path, file_name)

    if not os.path.exists(file_path):
        return jsonify({"message": "File not found"}), 404

    try:
        os.remove(file_path)
        return jsonify({"message": f"{file_name} deleted successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Error deleting file: {str(e)}"}), 500


# Initialize the database when the app starts
if __name__ == '__main__':
    init_db()  # Initialize the database
    app.run(host="127.0.0.1", port=5000, debug=True)
