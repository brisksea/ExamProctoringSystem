
import cv2
import numpy as np
import os

def final_verify():
    print("OpenCV Version:", cv2.__version__)
    filename = "final_test_h264.mp4"
    # Use avc1 as it is the most standard for .mp4
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    width, height = 640, 480
    fps = 20
    
    writer = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    
    if not writer.isOpened():
        print("Error: VideoWriter could not be opened with avc1.")
        return
    
    print("Success: VideoWriter opened with avc1. Writing frames...")
    for i in range(40): # 2 seconds
        frame = np.zeros((height, width, 3), np.uint8)
        color = (0, 255, 0) if i % 2 == 0 else (0, 0, 255)
        cv2.circle(frame, (320, 240), 100, color, -1)
        writer.write(frame)
    
    writer.release()
    
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        print(f"Final Verification PASSED! File created: {filename} ({os.path.getsize(filename)} bytes)")
    else:
        print("Final Verification FAILED! File is missing or empty.")

if __name__ == "__main__":
    final_verify()
