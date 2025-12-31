import threading
import time
import json
import base64
import cv2
import smbus
import mediapipe as mp
import paho.mqtt.client as mqtt
import numpy as np
import serial # Import serial for potential future GPS use

# ==========================================
# 1. CONFIGURATION
# ==========================================
BROKER_IP = "ae5709c5e4ad47cc9b914be36a7c8179.s1.eu.hivemq.cloud"
BROKER_PORT = 8883
MQTT_USER = "omarradwan"
MQTT_PASS = "Omar1234"

TOPIC_ALERT = "fleet/truck1/alert"
TOPIC_CAM   = "fleet/truck1/cam"

# AI Sensitivity
EAR_THRESHOLD = 0.21
CONSEC_FRAMES = 10

# ==========================================
# 2. MQTT CONNECTION
# ==========================================
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="truck-edge-unit")
client.tls_set()
client.username_pw_set(MQTT_USER, MQTT_PASS)

def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        print("✅ SYSTEM READY: Online & Waiting for Drowsiness...")
        client.publish(TOPIC_ALERT, "System Armed (Silent Mode)", qos=1)
    else:
        print(f"❌ Connection Failed: {rc}")

client.on_connect = on_connect

try:
    client.connect(BROKER_IP, BROKER_PORT, 60)
    client.loop_start()
except Exception as e:
    print(f"Connection Error: {e}")

# ==========================================
# 3. AI LOGIC (OFFLINE UNTIL ALERT)
# ==========================================
def webcam_ai_loop():
    # 1. Setup Camera (Standard Resolution is fine now!)
    cap = cv2.VideoCapture(0)
    cap.set(3, 320) # 320x240 is clear enough for evidence
    cap.set(4, 240)

    # 2. Setup AI
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True)
    
    LEFT_EYE = [362, 385, 387, 263, 373, 380]
    RIGHT_EYE = [33, 160, 158, 133, 153, 144]
    
    def calculate_ear(landmarks, indices):
        p1 = landmarks[indices[0]]; p4 = landmarks[indices[3]]
        p2 = landmarks[indices[1]]; p6 = landmarks[indices[5]]
        p3 = landmarks[indices[2]]; p5 = landmarks[indices[4]]
        v1 = np.linalg.norm(np.array(p2)-np.array(p6))
        v2 = np.linalg.norm(np.array(p3)-np.array(p5))
        h = np.linalg.norm(np.array(p1)-np.array(p4))
        return (v1 + v2) / (2.0 * h)

    frame_count = 0
    alert_active = False # Flag to prevent spamming alerts

    print("📷 Monitoring Driver (Silent Mode)...")

    while True:
        if cap.isOpened():
            ret, frame = cap.read()
            if not ret: continue

            # --- AI PROCESSING (LOCAL) ---
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)
            h, w, _ = frame.shape
            
            drowsy = False
            
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    lm = [(int(p.x * w), int(p.y * h)) for p in face_landmarks.landmark]
                    left = calculate_ear(lm, LEFT_EYE)
                    right = calculate_ear(lm, RIGHT_EYE)
                    avg = (left + right) / 2.0
                    
                    if avg < EAR_THRESHOLD:
                        frame_count += 1
                    else:
                        frame_count = 0
                        alert_active = False # Reset flag when eyes open
                    
                    # --- TRIGGER LOGIC ---
                    if frame_count >= CONSEC_FRAMES:
                        # Driver is sleeping!
                        if not alert_active:
                            print("⚠️ DROWSINESS DETECTED! UPLOADING ALERT...")
                            
                            # 1. Send Text Alert FIRST (Fastest)
                            client.publish(TOPIC_ALERT, "CRITICAL: DRIVER SLEEPING!", qos=2)
                            
                            # 2. Capture Evidence Photo
                            # Compress heavily to ensure it arrives
                            _, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 20])
                            b64 = base64.b64encode(jpg).decode()
                            
                            # 3. Upload Photo
                            payload = {"image": b64, "status": "DROWSY_EVIDENCE"}
                            client.publish(TOPIC_CAM, json.dumps(payload), qos=0)
                            
                            print("✅ Alert & Photo Sent!")
                            alert_active = True # Stop sending until eyes open again

        # Run fast locally
        time.sleep(0.05)

# ==========================================
# 4. MAIN
# ==========================================
if __name__ == "__main__":
    print("🚀 Truck Guardian Starting...")
    threading.Thread(target=webcam_ai_loop, daemon=True).start()
    
    while True:
        time.sleep(1)