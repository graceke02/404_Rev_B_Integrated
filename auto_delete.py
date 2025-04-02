import os, shutil
import datetime
import csv

from variables import set_and_status

def extract_datetime(f):
    month = (f[2:4])
    day = (f[4:6])
    year = (f[6:10])
    time = (f[11:17])
    
    datetime_str = f"{year}-{month}-{day} {time[:2]}:{time[2:4]}:{time[4:]}"
    return datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")

def sort_filenames(filenames):
    return sorted(filenames, key=extract_datetime)


def del_videos():
    #folder = '/home/camcs/Videos/'
    folderraw = '/home/camcs/server/uploads/raw_videos/'
    folder_final = '/home/camcs/server/uploads/videos/'
    today_date = datetime.date.today()

    print("Checking to delete videos")

    #set_and_status.last_del_date = today_date
    
    for filename in os.listdir(folderraw):
        file_path = os.path.join(folderraw, filename)
        #if video is named wrong - just want to delte it 
        #if int(filename[0]) != 0 or int(filename[0]) != 1:
         #   continue
        '''
        try:
            filename_month = int(filename[:2])
            filename_day = int(filename[2:4])
            filename_year = int(filename[4:9])
        except:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        '''
        try:
            #check if date is more than current 
            #@print(filename)
            filename_month = int(filename[:2])
            filename_day = int(filename[2:4])
            filename_year = int(filename[4:9])
            video_date = datetime.date(filename_year, filename_month, filename_day)
            del_date = today_date - datetime.timedelta(days=set_and_status.auto_delete)
            if video_date < del_date:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
        except: # Exception as e:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        
            #print('Failed to delete %s. Reason: %s' % (file_path, e))
    
    video_file_n_keep = [] #video file names to keep
    
    for filename in os.listdir(folder_final):
        file_path = os.path.join(folder_final, filename)
        
        try:
            #check if date is more than current 
            #@print(filename)
            filename_month = int(filename[2:4])
            filename_day = int(filename[4:6])
            filename_year = int(filename[6:11])
            #print(filename)
            video_date = datetime.date(filename_year, filename_month, filename_day)
            del_date = today_date - datetime.timedelta(days=set_and_status.auto_delete)
            if video_date < del_date:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            else:
                video_file_n_keep.append(filename)
        except: # Exception as e:
            #check if not the csv
            if filename == 'RecordedVideoNames.csv':
                continue
            else:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                #print('Failed to delete %s. Reason: %s' % (file_path, e))

    sorted_files = sort_filenames(video_file_n_keep)

    #delete from csv too
    video_name_file = r'/home/camcs/server/uploads/videos/RecordedVideoNames.csv'  
    with open(video_name_file, 'w', newline='') as file:
        writer = csv.writer(file)
        for row in sorted_files:
            writer.writerow([row])

    set_and_status.last_del_date = datetime.date.today()


