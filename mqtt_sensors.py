import json
import time
import base64
import cv2
import paho.mqtt.client as mqtt
from mpu6050 import mpu6050
from gps import gps, WATCH_ENABLE

# ---------------- MQTT CONFIG ----------------
BROKER_IP = "localhost"
BROKER_PORT = 1883

TOPIC_MPU = "lab08/mpu6050"
TOPIC_GPS = "lab08/gps"
TOPIC_CAM = "lab08/webcam"
TOPIC_STAT = "lab08/status"

# ---------------- MQTT SETUP ----------------
client = mqtt.Client(client_id="lab08-sensor-node", clean_session=True)

def on_connect(client, userdata, flags, rc):
    print("Connected rc =", rc)
    client.publish(TOPIC_STAT, "SENSORS READY", qos=1, retain=True)

client.on_connect = on_connect
client.connect(BROKER_IP, BROKER_PORT, 60)

# ---------------- MPU6050 ----------------
sensor = mpu6050(0x68)

# ---------------- GPS ----------------
gpsd = gps(mode=WATCH_ENABLE)

# ---------------- CAMERA ----------------
cap = cv2.VideoCapture(0)

# ---------------- MAIN LOOP ----------------
try:
    while True:
        # ---- MPU6050 ----
        accel = sensor.get_accel_data()
        gyro = sensor.get_gyro_data()

        mpu_payload = {
            "accel": accel,
            "gyro": gyro
        }

        client.publish(TOPIC_MPU, json.dumps(mpu_payload), qos=0)

        # ---- GPS ----
        gpsd.next()
        if gpsd.fix.mode >= 2:
            gps_payload = {
                "lat": gpsd.fix.latitude,
                "lon": gpsd.fix.longitude,
                "alt": gpsd.fix.altitude
            }
            client.publish(TOPIC_GPS, json.dumps(gps_payload), qos=0)

        # ---- WEBCAM ----
        ret, frame = cap.read()
        if ret:
            _, jpeg = cv2.imencode(".jpg", frame)
            jpg_base64 = base64.b64encode(jpeg).decode()

            cam_payload = {
                "image": jpg_base64
            }

            client.publish(TOPIC_CAM, json.dumps(cam_payload), qos=0)

        time.sleep(1)

except KeyboardInterrupt:
    print("Stopping...")

finally:
    cap.release()
    client.disconnect()
