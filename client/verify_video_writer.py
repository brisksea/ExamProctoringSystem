
import cv2
import os
import time

def verify_video_writer():
    print("OpenCV Version:", cv2.__version__)
    
    # Parameters
    filename = 'test_output.mp4'
    fps = 10
    width, height = 1920, 1080
    quality = 80
    bitrate = 200000  # 200kbps
    
    # Codec
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    
    print(f"Creating VideoWriter: {filename}, {fps}fps, {width}x{height}")
    writer = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    
    if not writer.isOpened():
        print("Failed to open VideoWriter")
        return
        
    print("VideoWriter opened successfully")
    
    # Test Quality
    print(f"Attempting to set QUALITY to {quality}...")
    success_quality = writer.set(cv2.VIDEOWRITER_PROP_QUALITY, quality)
    print(f"Set QUALITY result: {success_quality}")
    
    # Test Bitrate
    print(f"Attempting to set BITRATE to {bitrate}...")
    success_bitrate = writer.set(cv2.VIDEOWRITER_PROP_BITRATE, bitrate)
    print(f"Set BITRATE result: {success_bitrate}")
    
    writer.release()
    
    if os.path.exists(filename):
        os.remove(filename)
        print("Cleaned up test file")

if __name__ == "__main__":
    verify_video_writer()
