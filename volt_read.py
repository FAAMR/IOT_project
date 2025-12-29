from gpiozero import MCP3008
from time import sleep

adc = MCP3008(channel=0)

VREF = 3.3

# Calibrated divider (based on your real measurement)
DIVIDER_FACTOR = 4.41   # instead of 5.0

while True:
    raw = adc.value
    voltage_at_adc = raw * VREF
    actual_voltage = voltage_at_adc * DIVIDER_FACTOR

    print(f"ADC: {raw:.4f} | V_ADC: {voltage_at_adc:.3f} V | Battery: {actual_voltage:.3f} V")
    sleep(1)

