
import cv2
import os
import numpy as np

def test_h264():
    print("OpenCV Version:", cv2.__version__)
    
    # Try different combinations of backends and FourCC codes
    tests = [
        (cv2.CAP_ANY, 'avc1'),
        (cv2.CAP_ANY, 'H264'),
        (cv2.CAP_FFMPEG, 'avc1'),
        (cv2.CAP_MSMF, 'H264'),
        (cv2.CAP_MSMF, 'avc1'),
        (cv2.CAP_MSMF, 'mp4v'),
    ]
    width, height = 640, 480
    fps = 20
    
    for backend, codec in tests:
        backend_name = "FFMPEG/ANY" if backend == cv2.CAP_ANY or backend == cv2.CAP_FFMPEG else "MSMF"
        filename = f'test_{backend_name}_{codec}.mp4'
        print(f"\nTesting Backend: {backend_name}, Codec: {codec}")
        try:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            writer = cv2.VideoWriter(filename, backend, fourcc, fps, (width, height))
            
            if writer.isOpened():
                print(f"Success! {codec} is supported on {backend_name}.")
                # Write a few dummy frames
                for _ in range(10):
                    frame = np.zeros((height, width, 3), np.uint8)
                    cv2.putText(frame, f"Test {codec} {backend_name}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    writer.write(frame)
                writer.release()
                print(f"File created: {filename} ({os.path.getsize(filename)} bytes)")
                # os.remove(filename)  # Keep it for a moment to check
            else:
                print(f"Failed: {codec} is not supported on {backend_name}.")
        except Exception as e:
            print(f"Error testing {codec} on {backend_name}: {e}")

if __name__ == "__main__":
    test_h264()
