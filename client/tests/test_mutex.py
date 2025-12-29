import win32event
import win32api
import time
import multiprocessing
import os
import sys

# Define constant if not available
try:
    from win32con import ERROR_ALREADY_EXISTS
except ImportError:
    ERROR_ALREADY_EXISTS = 183

def hold_mutex():
    mutex_name = "Supervise3_Client_SingleInstance_Mutex_v1"
    print(f"Subprocess {os.getpid()} attempting to create mutex: {mutex_name}")
    try:
        # CreateMutex(security_attributes, initial_owner, name)
        mutex = win32event.CreateMutex(None, False, mutex_name)
        err = win32api.GetLastError()
        if err == ERROR_ALREADY_EXISTS:
            print("Subprocess found mutex already exists")
        else:
            print("Subprocess created mutex")
        
        # Keep it alive
        while True:
            time.sleep(1)
    except Exception as e:
        print(f"Subprocess failed: {e}")

def main():
    mutex_name = "Supervise3_Client_SingleInstance_Mutex_v1"
    
    # 1. Ensure we can create it initially
    print("Main process attempting to create mutex first time...")
    try:
        mutex1 = win32event.CreateMutex(None, False, mutex_name)
        last_error = win32api.GetLastError()
        print(f"First create result: error={last_error}")
        
        if last_error == ERROR_ALREADY_EXISTS:
            print("WARNING: Mutex already existed before test started! Closing it.")
        
        win32api.CloseHandle(mutex1)
        print("Closed first mutex")
    except Exception as e:
        print(f"Failed to create mutex: {e}")
        return

    # 2. Start a subprocess to hold it
    p = multiprocessing.Process(target=hold_mutex)
    p.start()
    time.sleep(2) # Wait for subprocess to acquire
    
    # 3. Try to acquire it again in main process
    print("Main process attempting to create mutex while subprocess holds it...")
    try:
        mutex2 = win32event.CreateMutex(None, False, mutex_name)
        last_error = win32api.GetLastError()
        print(f"Second create result: error={last_error}")
        
        if last_error == ERROR_ALREADY_EXISTS:
            print("SUCCESS: Detected existing mutex.")
        else:
            print(f"FAILURE: Did NOT detect existing mutex. Error code: {last_error}")
            
        win32api.CloseHandle(mutex2)
    except Exception as e:
        print(f"Failed to create mutex 2: {e}")

    p.terminate()

if __name__ == "__main__":
    main()
