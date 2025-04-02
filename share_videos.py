import numpy as np
from multiprocessing import shared_memory
import threading

memory_lock = threading.Lock()

def create_shared_memory(frame):
    shm = shared_memory.SharedMemory(create=True, size=frame.nbytes)
    np_array = np.ndarray(frame.shape, dtype=frame.dtype, buffer=shm.buf)
    np.copyto(np_array, frame)
    print(f"Shared memory {shm.name} created with size {frame.nbytes}")
    print(f"First 10 values written: {np_array.flatten()[:10]}")
    return shm


def access_shared_memory(shm_name, shape, dtype):
    try:
        with memory_lock:
            print(f"Trying to access shared memory: {shm_name}")
            shm = shared_memory.SharedMemory(name=shm_name)
            expected_size = np.prod(shape) * np.dtype(dtype).itemsize

            if shm.size != expected_size:
                print(f"ERROR: Shared memory size mismatch! Expected {expected_size}, but got {shm.size}")
                return None  # Return None instead of causing a segmentation fault

            print(f"Shared memory {shm_name} found, creating numpy array.")
            np_array = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
            print(f"First 10 Bytes after accessing: {np_array.flatten()[:10]}")
            return np_array
    except FileNotFoundError:
        print(f"Error: Shared memory {shm_name} not found!")
        return None
    except Exception as e:
        print(f"Unexpected error accessing shared memory: {e}")
        return None

#frame = np.zeros((480,640,3), dtype=np.uint8) #set up so cv2 can use
