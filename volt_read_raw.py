from gpiozero import MCP3008
from time import sleep

# ADC on channel 0
adc = MCP3008(channel=0)

VREF = 3.3            # MCP3008 reference voltage
DIVIDER = 5.0         # Theoretical divider of the 0â€“25V sensor

while True:
    raw = adc.value                      # 0.0 â†’ 1.0
    v_adc = raw * VREF                   # voltage at ADC pin
    battery_voltage = v_adc * DIVIDER    # true voltage before divider

    print(f"ADC: {raw:.4f} | V_ADC: {v_adc:.3f} V | Battery: {battery_voltage:.3f} V")

    sleep(1)
