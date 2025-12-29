import serial
import time
import pynmea2

# FIX 1: Open the serial port OUTSIDE the while loop
# We only want to open the connection once, not every millisecond.
ser = serial.Serial("/dev/ttyAMA0", baudrate=9600, timeout=1)

while True:
    try:
        # FIX 2: Decode the bytes to a string
        # Serial reads 'bytes' (b'..'), but pynmea2 needs a 'string'.
        newdata = ser.readline().decode('utf-8', errors='replace')
        
        # Check if the line is valid and is the RMC sentence (Location data)
        if newdata.startswith("$GPRMC"):
            newmsg = pynmea2.parse(newdata)
            lat = newmsg.latitude
            lng = newmsg.longitude
            
            gps = "Latitude=" + str(lat) + " and Longitude=" + str(lng)
            print(gps)
            
    except serial.SerialException as e:
        print(f"Device error: {e}")
        break
    except pynmea2.ParseError:
        # Sometimes the GPS sends incomplete lines; ignore them.
        continue
    except Exception as e:
        print(f"Error: {e}")
