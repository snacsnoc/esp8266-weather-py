import gc
import time

import dht
import network
import urequests
import webrepl
from machine import Pin, RTC, ADC, lightsleep, deepsleep, DEEPSLEEP

from config import *
from read_sensors import read_dht, read_adc

dht_pin = Pin(12)  # D6 on board
dht_sensor = dht.DHT22(dht_pin)  # Use dht.DHT11(dht_pin) for a DHT11 sensor
adc_sensor = ADC(0)


led = Pin(2, Pin.OUT)
led.value(0)


def do_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    network.WLAN(network.AP_IF).active(False)
    # Always disconnect first to ensure a clean state
    if wlan.isconnected():
        if ENABLE_VERBOSE:
            print("Already connected to Wi-Fi.")
        return
    else:
        if ENABLE_VERBOSE:
            print("Disconnecting from previous Wi-Fi state...")
        wlan.disconnect()
        wlan.active(False)
        time.sleep(0.5)
        wlan.active(True)

    if not wlan.isconnected():
        if ENABLE_VERBOSE:
            print("Connecting to network...")
        wlan.ifconfig(("192.168.1.41", "255.255.255.0", "192.168.1.1", "192.168.1.1"))

        wlan.connect("home", "")
        while not wlan.isconnected():

            if wlan.status() == network.STAT_CONNECTING:
                if ENABLE_VERBOSE:
                    print("Status: Connecting, retrying in 1 sec...")
                    led.value(0)
                    led.value(1)
                    time.sleep(0.05)
                    led.value(0)
                    time.sleep(0.05)
                    led.value(1)
                    time.sleep(0.05)
                    led.value(0)
                    time.sleep(0.05)
                    led.value(1)
                    time.sleep(0.05)
            lightsleep(1000)

        if ENABLE_VERBOSE:
            if wlan.isconnected():
                print("Connected to Wi-Fi!")
                print("Network config:", wlan.ifconfig())
            else:
                print("Failed to connect to the network.")


def disconnect_wifi():
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        if ENABLE_VERBOSE:
            print("Disconnecting from WiFi...")
        wlan.disconnect()
        wlan.active(False)
        if ENABLE_VERBOSE:
            print("WiFi disconnected")


# NOTE: you MUST connect GPIO16 (D0) to the RST pin for the board to wake after deep sleep
# for a NodeMCU, using the micro USB for power will not work and put your board into flash mode.
# you must power the ESP8266 with a 3.3v power source
# See https://esphome.io/components/deep_sleep.html
def deep_sleep(msecs):
    # configure RTC.ALARM0 to be able to wake the device
    rtc = RTC()
    rtc.irq(trigger=rtc.ALARM0, wake=DEEPSLEEP)

    rtc.alarm(rtc.ALARM0, msecs)

    deepsleep()


def send_to_adafruit_io(data):
    url_template = "https://io.adafruit.com/api/v2/{}/feeds/{}/data"
    headers = {"Content-Type": "application/json", "X-AIO-Key": AIO_KEY}
    for feed, value in data.items():
        url = url_template.format(AIO_USERNAME, feed)

        # Convert value to string to ensure correct format
        payload = {"value": str(value)}

        if ENABLE_VERBOSE:
            print(f"Sending payload for feed {feed}: {payload} \n")

        attempt = 0
        while attempt < 3:  # Retry up to 3 times
            try:
                response = urequests.post(
                    url, headers=headers, json=payload, timeout=10
                )
                # To prevent low memory errors, close the response after use
                response.close()
                gc.collect()
                if response.status_code == 200:
                    print(f"Data sent successfully for {feed} at time {time.time()}")
                    # Exit retry loop after success
                    break

                else:
                    print(f"Failed to send data for {feed}: {response.status_code}")
                    print(response.text)

                    if response.status_code == 429:
                        print("Rate limit exceeded. Waiting before retrying...")
                        time.sleep(60)
                    if attempt == 2:
                        print(f"Failed to send {feed}")
                    time.sleep(2)

            except OSError as e:
                print(f"Timeout error sending data to {feed}: {e}, retrying...")
                attempt += 1

        if attempt >= 3:
            print(f"Failed to send data for {feed} after 3 attempts. Giving up.")


def main():

    while True:

        try:

            # Read from sensors
            temperature, humidity = read_dht(dht_sensor)
            gc.collect()
            sensor_voltage, soil_moisture_percent = read_adc(adc_sensor)

            if ENABLE_VERBOSE:
                print(
                    f"Temperature: {temperature}°C | Humidity: {humidity}% | Voltage: {sensor_voltage:.2f}V | Soil Moisture Percent: {soil_moisture_percent:.2f}%"
                )

            if SEND_DATA_TO_NET:
                data = {
                    "temperature": temperature if temperature is not None else 0,
                    "humidity": humidity if humidity is not None else 0,
                    "sensor-voltage": "{:.2f}".format(sensor_voltage)
                    if sensor_voltage is not None
                    else 0,
                    "soil-percentage": "{:.1f}".format(soil_moisture_percent)
                    if soil_moisture_percent is not None
                    else 0,
                }

                send_to_adafruit_io(data)
                gc.collect()
        except OSError as e:

            print(f"Sensor read or Wi-Fi issue: {e}")

            time.sleep(1)

        except Exception as e:

            print(f"Unexpected error: {e}")

        finally:

            print(f"Going to light sleep for {ms_sleep_before_ds} milliseconds")
            gc.collect()

            lightsleep(ms_sleep_before_ds)

            if ENABLE_DEEP_SLEEP:
                if ENABLE_VERBOSE:
                    print(f"Going to deep sleep for {ms_sleep_time} milliseconds")
                deep_sleep(ms_sleep_time)


do_connect()
webrepl.start()
main()
