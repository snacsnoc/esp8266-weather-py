# Weather and Soil Moisture Logger

This project logs temperature, humidity, and soil moisture data using an ESP8266 microcontroller and sends the data to Adafruit IO.
Components used
* ESP8266 Microcontroller
* DHT11 or DHT22 temperature & humidity sensor
* Soil moisture sensor ("Capacitive Soil Moisture Sensor V1.2")

### Setup
1. **Hardware connections:**
   - DHT11: Connect to GPIO12 (D6)
   - Soil Moisture Sensor: Connect to A0 (ADC)

2. **Software requirements:**
   - MicroPython installed on ESP8266
3. **Human requirements:**
   - A smile on your face
4. **Configuration:**
   - Update `config.py` with your Adafruit IO username and API key.

### Usage
1. **Upload Code:**
   - Flash the provided MicroPython script to the ESP8266.
   - See https://github.com/wendlers/mpfshell
   - `mpfshell -n -c "open tty.usbserial-529A0037391; put boot.py"`

2. **Run:**
   - Power the ESP8266 and monitor the serial output for data readings and status messages.

3. **Data Logging:**
   - Data is sent to Adafruit IO feeds for neat dashboards you can show your friends and claim you didn't waste an entire weekend working on this project..
