import gc
import time

import machine
import network
import urequests
import webrepl
import json
from config import *


import dht

dht_pin = machine.Pin(12)  # D6 on board
sensor = dht.DHT22(dht_pin)  # Use dht.DHT11(dht_pin) for a DHT11 sensor
adc = machine.ADC(0)


def do_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        if ENABLE_VERBOSE:
            print("Connecting to network...")
        wlan.ifconfig(("192.168.1.41", "255.255.255.0", "192.168.1.1", "192.168.1.50"))

        wlan.connect("home-guest", "homehome")
        while not wlan.isconnected():
            status = wlan.status()
            if status == network.STAT_WRONG_PASSWORD:
                if ENABLE_VERBOSE:
                    print("Failed: Wrong password")
                break
            elif status == network.STAT_NO_AP_FOUND:
                if ENABLE_VERBOSE:
                    print("Failed: No access point found")
                break
            elif status == network.STAT_CONNECT_FAIL:
                if ENABLE_VERBOSE:
                    print("Failed: Connection failure")
                break
            elif status == network.STAT_IDLE:
                if ENABLE_VERBOSE:
                    print("Status: Idle, retrying in 1 sec...")
            elif status == network.STAT_CONNECTING:
                if ENABLE_VERBOSE:
                    print("Status: Connecting, retrying in 1.5 sec...")
            machine.lightsleep(1500)
    if wlan.isconnected():
        if ENABLE_VERBOSE:
            print("Network connected!")
            print("Network config:", wlan.ifconfig())
    else:
        if ENABLE_VERBOSE:
            print("Failed to connect to the network")


#  Map a value from one range to another
def map_value(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


# NOTE: you MUST connect GPIO16 (D0) to the RST pin for the board to wake after deep sleep
# for a NodeMCU, using the micro USB for power will not work and put your board into flash mode.
# you must power the ESP8266 with a 3.3v power source
# See https://esphome.io/components/deep_sleep.html
def deep_sleep(msecs):
    # configure RTC.ALARM0 to be able to wake the device
    rtc = machine.RTC()
    rtc.irq(trigger=rtc.ALARM0, wake=machine.DEEPSLEEP)

    rtc.alarm(rtc.ALARM0, msecs)

    machine.deepsleep()


def send_to_adafruit_io(data):
    url_template = "https://io.adafruit.com/api/v2/{}/feeds/{}/data"
    headers = {"Content-Type": "application/json", "X-AIO-Key": AIO_KEY}

    for feed, value in data.items():
        url = url_template.format(AIO_USERNAME, feed)
        # Convert value to string to ensure correct format
        try:
            value = str(value)
        except ValueError:
            value = "0"
        payload = {"value": value}

        if ENABLE_VERBOSE:
            print(f"Sending payload for feed {feed}: {payload} \n")
        try:
            response = urequests.post(url, headers=headers, json=payload, timeout=10)

            if response.status_code == 200:
                if ENABLE_VERBOSE:
                    print(f"Data sent successfully for {feed}")
                time.sleep(1)
            else:
                if ENABLE_VERBOSE:
                    print(response.text)
                    print(payload)
                raise Exception(f"Failed to send data for {feed} ")

        except Exception as e:
            print(
                f"Error sending data to {feed}: {e} Status code: {response.status_code}"
            )
            if ENABLE_VERBOSE:
                print(response.text)
                print(f"Payload: {payload}")


def read_dht(sensor, max_retries=5):
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
        time.sleep(2)
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
            time.sleep(2)
    except OSError as e:
        if ENABLE_VERBOSE:
            print(f"Failed to read ADC sensor. {e}")
    return sensor_voltage, soil_moisture_percent


def read_adc_avg(adc):
    total_adc_value = 0
    valid_readings_count = 0
    sensor_voltage = None
    soil_moisture_percent = None

    try:
        for _ in range(5):
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


do_connect()
webrepl.start()
gc.collect()


while True:
    try:
        # Read from sensors
        temperature, humidity = read_dht(sensor)

        sensor_voltage, soil_moisture_percent = read_adc_avg(adc)

        gc.collect()
        if ENABLE_VERBOSE:
            print(
                f"Temperature: {temperature}°C | Humidity: {humidity}% | Voltage: {sensor_voltage:.2f}V | Soil Moisture Percent: {soil_moisture_percent:.2f}%"
            )

        if SEND_DATA_TO_NET:
            data = {
                "temperature": temperature if temperature is not None else 0,
                "humidity": humidity if humidity is not None else 0,
                "sensor-voltage": "{:.1f}".format(sensor_voltage)
                if sensor_voltage is not None
                else 0,
                "soil-percentage": "{:.1f}".format(soil_moisture_percent)
                if soil_moisture_percent is not None
                else 0,
            }

            send_to_adafruit_io(data)

    except Exception as e:
        print(f"Error: {e}")

    finally:
        gc.collect()
        if ENABLE_VERBOSE:
            print(f"Going to light sleep for {ms_sleep_before_ds} milliseconds")

        machine.lightsleep(ms_sleep_before_ds)

        if ENABLE_DEEP_SLEEP:
            if ENABLE_VERBOSE:
                print(f"Going to deep sleep for {ms_sleep_time} milliseconds")
            deep_sleep(ms_sleep_time)
