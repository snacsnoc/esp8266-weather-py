import time

from config import *


def read_dht(sensor, max_retries=3):
    temperature = None
    humidity = None

    for attempt in range(max_retries):
        try:
            if ENABLE_VERBOSE:
                print(f"Reading from DHT sensor... Attempt {attempt + 1}/{max_retries}")

            # TODO: Fix DHT11 first sensor read ETIMEDOUT error on boot.
            #       Subsequent reads are fine. DHT22 does not experience this issue
            sensor.measure()
            temperature = sensor.temperature()
            humidity = sensor.humidity()
            if temperature is not None and humidity is not None:
                if ENABLE_VERBOSE:
                    print("Read from DHT successful")
                break
        except OSError as e:
            if ENABLE_VERBOSE:
                print(f"Failed to read DHT11 sensor: {e}")
        time.sleep(1)
    if temperature is None or humidity is None:
        if ENABLE_VERBOSE:
            print("Failed to get valid DHT11 readings after maximum retries.")
    return temperature, humidity


def read_adc(adc):
    sensor_voltage = None
    soil_moisture_percent = None
    try:
        for _ in range(5):
            if ENABLE_VERBOSE:
                print("Reading from ADC...")
            adc_value = adc.read()
            if adc_value is not None:
                voltage = adc_value * (1.0 / 1023.0)  # use 1.8 for 5V
                sensor_voltage = voltage * 3  # 5v use (11 / 5)

                if ENABLE_VERBOSE:
                    print(f"Raw ADC value: {adc_value}")
                soil_moisture_percent = map_value(
                    adc_value, air_value, water_value, 0, 100
                )
                break
            time.sleep(1)
    except OSError as e:
        if ENABLE_VERBOSE:
            print(f"Failed to read ADC sensor. {e}")
    return sensor_voltage, soil_moisture_percent


def read_adc_avg(adc, num_samples=3):
    total_adc_value = 0
    valid_readings_count = 0
    sensor_voltage = None
    soil_moisture_percent = None

    try:
        for _ in range(num_samples):

            if ENABLE_VERBOSE:
                print("Reading from ADC...")
            adc_value = adc.read()
            if adc_value is not None:
                total_adc_value += adc_value
                valid_readings_count += 1
                if ENABLE_VERBOSE:
                    print(f"Raw ADC value: {adc_value}")
            time.sleep(2)  # Sleep between readings to reduce noise impact
    except OSError as e:
        if ENABLE_VERBOSE:
            print(f"Failed to read ADC sensor. {e}")

    if valid_readings_count > 0:
        average_adc_value = total_adc_value / valid_readings_count
        sensor_voltage = (
            average_adc_value * (1.0 / 1023.0)
        ) * 3  # Adjust multiplier for voltage scaling
        soil_moisture_percent = map_value(
            average_adc_value, air_value, water_value, 0, 100
        )
        if ENABLE_VERBOSE:
            print(f"Average adc value. {average_adc_value}")

    return sensor_voltage, soil_moisture_percent


#  Map a value from one range to another
def map_value(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
