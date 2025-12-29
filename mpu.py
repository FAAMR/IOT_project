import mpu6050
import time

mpu = mpu6050.mpu6050(0x68)

def read_sensor_data():
    # Read the accelerometer values
    accelerometer_data = mpu.get_accel_data()

    # Read the gyroscope values
    gyroscope_data = mpu.get_gyro_data()

    # Read temp
    temperature = mpu.get_temp()

    return accelerometer_data, gyroscope_data, temperature

# Start a while loop
while True:
    # Read the sensor data
    accelerometer_data, gyroscope_data, temperature = read_sensor_data()

    # Print the sensor data
    print("Accelerometer data:", accelerometer_data)
    print("Gyroscope data:", gyroscope_data)
    print("Temp:", temperature)

    # Wait for 1 second
    time.sleep(1)
