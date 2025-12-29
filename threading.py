import threading
import time
import serial
import pynmea2
import mpu6050
from gpiozero import MCP3008
from time import sleep

# ---------------- GPS Thread ----------------
def gps_loop():
    try:
        ser = serial.Serial("/dev/ttyAMA0", baudrate=9600, timeout=1)
    except Exception as e:
        print(f"GPS Serial Error: {e}")
        return

    while True:
        try:
            newdata = ser.readline().decode('utf-8', errors='replace')
            if newdata.startswith("$GPRMC"):
                newmsg = pynmea2.parse(newdata)
                lat = newmsg.latitude
                lng = newmsg.longitude
                print(f"GPS -> Latitude: {lat}, Longitude: {lng}")
        except pynmea2.ParseError:
            continue
        except Exception as e:
            print(f"GPS Error: {e}")

# ---------------- MPU6050 Thread ----------------
def mpu_loop():
    try:
        mpu = mpu6050.mpu6050(0x68)
    except Exception as e:
        print(f"MPU6050 Init Error: {e}")
        return

    while True:
        try:
            accel_data = mpu.get_accel_data()
            gyro_data = mpu.get_gyro_data()
            temp = mpu.get_temp()
            print(f"MPU -> Accel: {accel_data}, Gyro: {gyro_data}, Temp: {temp}")
        except Exception as e:
            print(f"MPU Error: {e}")
        time.sleep(1)

# ---------------- Voltage Sensor Thread ----------------
def voltage_loop():
    try:
        adc = MCP3008(channel=0)
        VREF = 3.3
        DIVIDER_FACTOR = 4.41
    except Exception as e:
        print(f"Voltage Sensor Init Error: {e}")
        return

    while True:
        try:
            raw = adc.value
            voltage_at_adc = raw * VREF
            actual_voltage = voltage_at_adc * DIVIDER_FACTOR
            print(f"Voltage -> ADC: {raw:.4f}, Battery: {actual_voltage:.3f} V")
        except Exception as e:
            print(f"Voltage Error: {e}")
        sleep(1)

# ---------------- Main ----------------
if __name__ == "__main__":
    # Create threads for each sensor
    gps_thread = threading.Thread(target=gps_loop, daemon=True)
    mpu_thread = threading.Thread(target=mpu_loop, daemon=True)
    voltage_thread = threading.Thread(target=voltage_loop, daemon=True)

    # Start all threads
    gps_thread.start()
    mpu_thread.start()
    voltage_thread.start()

    # Keep main thread alive
    while True:
        time.sleep(0.1)