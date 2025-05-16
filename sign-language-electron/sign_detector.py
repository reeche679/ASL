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

# Initialize camera
print("Attempting to initialize camera...", file=sys.stderr)
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open camera", file=sys.stderr)
    # Try alternative camera index
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("Error: Could not open camera with index 1", file=sys.stderr)
        sys.exit(1)
    else:
        print("Successfully opened camera with index 1", file=sys.stderr)
else:
    print("Successfully opened camera with index 0", file=sys.stderr)

# Set camera properties
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

detector = HandDetector(maxHands=1)

def is_hand_up(lmList, margin=30):
    wrist_y = lmList[0][1]
    middle_finger_y = lmList[12][1]
    index_finger_y = lmList[8][1]
    return (middle_finger_y < wrist_y - margin) or (index_finger_y < wrist_y - margin)

def is_hand_down(lmList, margin=30):
    wrist_y = lmList[0][1]
    middle_finger_y = lmList[12][1]
    index_finger_y = lmList[8][1]
    return (middle_finger_y > wrist_y + margin) or (index_finger_y > wrist_y + margin)

print("Starting video capture...", file=sys.stderr)

while True:
    success, img = cap.read()
    if not success:
        print("Error: Could not read from camera", file=sys.stderr)
        break

    # Flip the image horizontally for a later selfie-view display
    img = cv2.flip(img, 1)
    
    # Convert the image to RGB
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Encode the frame
    frame_encoded = encode_frame(img_rgb)
    if frame_encoded is None:
        continue
    
    hands, img = detector.findHands(img)

    output_data = {
        "frame": frame_encoded,
        "prediction": None,
        "confidence": 0,
        "orientation": "Not detected"
    }

    if hands:
        hand = hands[0]
        lmList = hand["lmList"]
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
                    
                    # Detect orientation
                    is_up = is_hand_up(lmList)
                    is_down = is_hand_down(lmList)
                    
                    # Get the predicted label and confidence
                    index = np.argmax(prediction[0])
                    predicted_label = labels[index]
                    confidence = float(prediction[0][index])
                    
                    # Determine orientation
                    orientation = "UP" if is_up else "DOWN" if is_down else "NEUTRAL"
                    
                    # Update output data
                    output_data.update({
                        "prediction": predicted_label,
                        "confidence": confidence,
                        "orientation": orientation
                    })

        except Exception as e:
            print(f"Error processing frame: {e}", file=sys.stderr)
            continue

    # Print JSON data for Electron to capture
    print(json.dumps(output_data))
    sys.stdout.flush()

    time.sleep(0.1)  # Small delay to prevent overwhelming the system

cap.release()
cv2.destroyAllWindows() 