import cv2
import numpy as np
import os
import time
import tensorflow as tf
from cvzone.HandTrackingModule import HandDetector
import math
import json
import sys
import base64

# Print Python version and working directory for debugging
print(f"Python version: {sys.version}", file=sys.stderr)
print(f"Working directory: {os.getcwd()}", file=sys.stderr)

# Custom DepthwiseConv2D layer to handle older model format
class CustomDepthwiseConv2D(tf.keras.layers.DepthwiseConv2D):
    def __init__(self, *args, **kwargs):
        if 'groups' in kwargs:
            del kwargs['groups']
        super().__init__(*args, **kwargs)

def encode_frame(frame):
    try:
        _, buffer = cv2.imencode('.jpg', frame)
        return base64.b64encode(buffer).decode('utf-8')
    except Exception as e:
        print(f"Error encoding frame: {e}", file=sys.stderr)
        return None

# Load the trained model
try:
    model = tf.keras.models.load_model(
        "../model/keras_model.h5",
        compile=False,
        custom_objects={'DepthwiseConv2D': CustomDepthwiseConv2D}
    )
    print("Model loaded successfully", file=sys.stderr)
except Exception as e:
    print(f"Failed to load model: {e}", file=sys.stderr)
    sys.exit(1)

# Load labels
try:
    with open("../model/labels.txt", "r") as f:
        labels = [line.strip().split()[1] for line in f.readlines()]
    print(f"Labels loaded: {labels}", file=sys.stderr)
except Exception as e:
    print(f"Error loading labels: {e}", file=sys.stderr)
    sys.exit(1)

# Constants
offset = 20
imgSize = 224
confidence_threshold = 0.6

def list_cameras():
    """List all available cameras"""
    available_cameras = []
    for i in range(10):  # Check first 10 indexes
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                # Get camera properties
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(cap.get(cv2.CAP_PROP_FPS))
                available_cameras.append({
                    'index': i,
                    'resolution': f"{width}x{height}",
                    'fps': fps
                })
            cap.release()
    return available_cameras

def main():
    # List available cameras
    cameras = list_cameras()
    if not cameras:
        print(json.dumps({"error": "No cameras found"}))
        return

    # Send camera list to the main process
    print(json.dumps({"cameras": cameras}))
    sys.stdout.flush()

    # Wait for camera selection from main process
    selected_camera = 0  # Default to first camera
    for line in sys.stdin:
        try:
            data = json.loads(line)
            if 'camera_index' in data:
                selected_camera = int(data['camera_index'])
                break
        except json.JSONDecodeError:
            continue

    # Initialize camera
    cap = cv2.VideoCapture(selected_camera)
    if not cap.isOpened():
        print(json.dumps({"error": f"Could not open camera {selected_camera}"}))
        return

    # Initialize hand detector
    detector = HandDetector(maxHands=1, detectionCon=0.8)

    while True:
        success, img = cap.read()
        if not success:
            print(json.dumps({"error": "Failed to read frame"}))
            break

        # Find hands
        hands, img = detector.findHands(img)

        output_data = {
            "frame": encode_frame(img),
            "prediction": None,
            "confidence": 0,
            "orientation": "Not detected"
        }

        if hands:
            # Get hand landmarks
            hand = hands[0]
            landmarks = hand["lmList"]
            bbox = hand["bbox"]
            
            try:
                imgCrop = img[max(0, bbox[1]-offset):min(img.shape[0], bbox[1]+bbox[3]+offset),
                             max(0, bbox[0]-offset):min(img.shape[1], bbox[0]+bbox[2]+offset)]
                
                if imgCrop.shape[0] > 0 and imgCrop.shape[1] > 0:
                    imgWhite = np.ones((imgSize, imgSize, 3), np.uint8) * 255
                    imgCropShape = imgCrop.shape

                    aspectRatio = imgCrop.shape[0] / imgCrop.shape[1]
                    if aspectRatio > 1:
                        k = imgSize / imgCrop.shape[0]
                        imgResize = cv2.resize(imgCrop, (0, 0), None, k, k)
                        imgResizeShape = imgResize.shape
                        wGap = math.ceil((imgSize - imgResizeShape[1]) / 2)
                        imgWhite[0:imgResizeShape[0], wGap:wGap+imgResizeShape[1]] = imgResize

                        img_array = tf.keras.preprocessing.image.img_to_array(imgWhite)
                        img_array = tf.expand_dims(img_array, 0)
                        img_array = img_array / 255.0

                        prediction = model.predict(img_array, verbose=0)
                        
                        # Get the predicted label and confidence
                        index = np.argmax(prediction[0])
                        predicted_label = labels[index]
                        confidence = float(prediction[0][index])

                        # Update output data
                        output_data.update({
                            "prediction": predicted_label,
                            "confidence": confidence
                        })

            except Exception as e:
                print(f"Error processing frame: {e}", file=sys.stderr)
                continue

        # Send the complete data object
        print(json.dumps(output_data))
        sys.stdout.flush()

    cap.release()

if __name__ == "__main__":
    main() 