import threading
import time
import json
import base64
import cv2
import serial
import pynmea2
import smbus
import requests
import mediapipe as mp
import paho.mqtt.client as mqtt
import numpy as np

# ---------------- CONFIGURATION ----------------
BROKER_IP = "localhost"
BROKER_PORT = 1883

# MQTT Topics
TOPIC_MPU   = "fleet/truck1/mpu"
TOPIC_GPS   = "fleet/truck1/gps"
TOPIC_CAM   = "fleet/truck1/cam"
TOPIC_ALERT = "fleet/truck1/alert"  # New Alert Topic

# Roboflow Configuration (Drowsiness)
EAR_THRESHOLD = 0.21    # Below this = Eye Closed
CONSEC_FRAMES = 10      # How many frames closed before alert

# ---------------- MEDIAPIPE SETUP ----------------
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# ---------------- MPU6050 SETUP ----------------
PWR_MGMT_1   = 0x6B
SMPLRT_DIV   = 0x19
CONFIG       = 0x1A
ACCEL_XOUT_H = 0x3B
ACCEL_YOUT_H = 0x3D
ACCEL_ZOUT_H = 0x3F

bus = smbus.SMBus(1)
DEVICE_ADDR = 0x68

def mpu_init():
    try:
        bus.write_byte_data(DEVICE_ADDR, PWR_MGMT_1, 0)
        bus.write_byte_data(DEVICE_ADDR, SMPLRT_DIV, 7)
        bus.write_byte_data(DEVICE_ADDR, CONFIG, 0)
    except:
        pass

def read_raw_data(addr):
    try:
        high = bus.read_byte_data(DEVICE_ADDR, addr)
        low = bus.read_byte_data(DEVICE_ADDR, addr+1)
        value = ((high << 8) | low)
        if(value > 32768): value = value - 65536
        return value
    except:
        return 0

# ---------------- EAR FUNCTION ----------------
def calculate_ear(landmarks, indices):
    # Euclidean distance helper
    def dist(p1, p2):
        return np.linalg.norm(np.array(p1) - np.array(p2))

    # Get coordinates of the 6 eye points
    # P1, P4 are corners. P2, P6 and P3, P5 are top/bottom pairs.
    p1 = landmarks[indices[0]]
    p2 = landmarks[indices[1]]
    p3 = landmarks[indices[2]]
    p4 = landmarks[indices[3]]
    p5 = landmarks[indices[4]]
    p6 = landmarks[indices[5]]

    # Calculate vertical distances
    v1 = dist(p2, p6)
    v2 = dist(p3, p5)
    # Calculate horizontal distance
    h = dist(p1, p4)

    # EAR Formula
    ear = (v1 + v2) / (2.0 * h)
    return ear
# ---------------- MQTT SETUP ----------------
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="truck-ai-node")
client.connect(BROKER_IP, BROKER_PORT, 60)
client.loop_start()

# ---------------- THREADS ----------------

def gps_loop():
    try:
        ser = serial.Serial("/dev/ttyAMA0", baudrate=9600, timeout=1)
    except:
        return
    while True:
        try:
            line = ser.readline().decode(errors="ignore")
            if line.startswith("$GPRMC"):
                msg = pynmea2.parse(line)
                if msg.status == 'A':
                    payload = {"lat": msg.latitude, "lon": msg.longitude, "speed": float(msg.speed or 0)}
                    client.publish(TOPIC_GPS, json.dumps(payload), qos=0)
        except: pass

def mpu_loop():
    mpu_init()
    while True:
        try:
            ax = read_raw_data(ACCEL_XOUT_H) / 16384.0
            ay = read_raw_data(ACCEL_YOUT_H) / 16384.0
            az = read_raw_data(ACCEL_ZOUT_H) / 16384.0
            payload = {"ax": round(ax, 2), "ay": round(ay, 2), "az": round(az, 2)}
            client.publish(TOPIC_MPU, json.dumps(payload), qos=0)
        except: pass
        time.sleep(0.5)

def webcam_ai_loop():
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    
    # Landmark indices for Left and Right eyes (MediaPipe standard)
    LEFT_EYE = [362, 385, 387, 263, 373, 380]
    RIGHT_EYE = [33, 160, 158, 133, 153, 144]
    
    frame_counter = 0
    alert_active = False

    while True:
        if cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                continue

            # 1. Preprocess for AI
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_frame)
            h, w, _ = frame.shape
            
            status = "Awake"
            color = (0, 255, 0) # Green

            # 2. Run Detection
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    # Convert normalized landmarks to pixel coordinates
                    landmarks = [(int(p.x * w), int(p.y * h)) for p in face_landmarks.landmark]

                    # Calculate EAR for both eyes
                    left_ear = calculate_ear(landmarks, LEFT_EYE)
                    right_ear = calculate_ear(landmarks, RIGHT_EYE)
                    avg_ear = (left_ear + right_ear) / 2.0

                    # 3. Drowsiness Logic
                    if avg_ear < EAR_THRESHOLD:
                        frame_counter += 1
                        status = "Closing Eyes..."
                        color = (0, 255, 255) # Yellow
                    else:
                        frame_counter = 0
                        status = "Awake"
                        color = (0, 255, 0)
                        alert_active = False

                    # 4. Trigger Alert
                    if frame_counter >= CONSEC_FRAMES:
                        status = "DROWSY ALERT!"
                        color = (0, 0, 255) # Red
                        
                        # Send alert ONLY once per event to avoid spamming
                        if not alert_active:
                            client.publish(TOPIC_ALERT, "DROWSY_DRIVER_DETECTED", qos=1)
                            print("⚠️ ALERT: Driver is Drowsy!")
                            alert_active = True

            # 5. Overlay Text on Image (Optional - useful for debugging)
            cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            # 6. Send Image to Dashboard (Throttled)
            # We resize to make it faster over 4G
            small_frame = cv2.resize(frame, (320, 240))
            _, jpg = cv2.imencode(".jpg", small_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
            encoded = base64.b64encode(jpg).decode()
            client.publish(TOPIC_CAM, json.dumps({"image": encoded}), qos=0)
            
        # Run at ~15 FPS
        time.sleep(0.06)
# ---------------- MAIN ----------------
if __name__ == "__main__":
    threading.Thread(target=gps_loop, daemon=True).start()
    threading.Thread(target=mpu_loop, daemon=True).start()
    threading.Thread(target=webcam_ai_loop, daemon=True).start()
    while True:
        time.sleep(1)
