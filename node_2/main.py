# main.py
import machine
machine.freq(240000000)
# This is version number 24
# Do NOT update following lines
NODE_ID = 2
firmware_url = "https://github.com/atonughosh/tsdpl_vib_temp"

# Wi-Fi credentials (to be written into WIFI_CONFIG.py)
SSID = "Ramniwas"
PASSWORD = "lasvegas@007"

# Function to create or overwrite WIFI_CONFIG.py
def create_wifi_config_file():
    with open('WIFI_CONFIG.py', 'w') as f:
        f.write(f'SSID = "{SSID}"\n')
        f.write(f'PASSWORD = "{PASSWORD}"\n')

# Function to create or overwrite boot.py with custom contents
def create_boot_file():
    with open('boot.py', 'w') as f:
        # Specify the full contents of boot.py here
        boot_code = f"""
import os
import gc
import uasyncio as asyncio

# Import SSID and PASSWORD from WIFI_CONFIG.py
try:
    from WIFI_CONFIG import SSID, PASSWORD
except ImportError:
    print("Error: WIFI_CONFIG.py not found!")
    SSID = ""
    PASSWORD = ""

# Your boot actions: 

from ota import OTAUpdater
from WIFI_CONFIG import SSID, PASSWORD
import gc
NODE_ID = "2"

gc.collect()
firmware_url = "https://github.com/atonughosh/tsdpl_vib_temp"

async def boot_time_ota():
    try:
        ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py", NODE_ID)
        
        # Check if an update is available
        if await ota_updater.check_for_updates():
            # If there's a new version, perform the update
            ota_updater.update_and_reset()
        else:
            print("No update available.")
    except:
        print(f"Error during OTA update")


# Start the async update process
async def boot():
    gc.collect()
    await boot_time_ota()  # Await the update process

# Execute the boot process using uasyncio
asyncio.run(boot())

gc.collect()

# You can add more boot actions here if needed
"""
        f.write(boot_code)

# First, create the WIFI_CONFIG.py file
create_wifi_config_file()

# Then, create the boot.py file with your custom content
create_boot_file()

# Import SSID and PASSWORD from WIFI_CONFIG.py for use in the main script
from WIFI_CONFIG import SSID, PASSWORD

# Update below this

from ota import OTAUpdater
import uasyncio as asyncio
from machine import SPI, Pin, I2C
import time
import gc
from umqtt.simple import MQTTClient
import max31865
import json

# Constants for your RTD sensor
RTD_NOMINAL = 100.0       # Resistance of RTD at 0°C
RTD_REFERENCE = 402.0     # Reference resistor on the PCB
RTD_WIRES = 3             # 3-wire configuration

# SPI setup specific to your configuration
sck = machine.Pin(18, machine.Pin.OUT)
mosi = machine.Pin(23, machine.Pin.OUT)
miso = machine.Pin(19, machine.Pin.IN)
spi = machine.SPI(baudrate=50000, sck=sck, mosi=mosi, miso=miso, polarity=0, phase=1)

# Chip select setup for the sensor
cs1 = machine.Pin(5, machine.Pin.OUT, value=1)
css = [cs1]

# Initialize the MAX31865 sensor
sensors = [
    max31865.MAX31865(
        spi, cs, wires=RTD_WIRES, rtd_nominal=RTD_NOMINAL, ref_resistor=RTD_REFERENCE
    )
    for cs in css
]

# Set up pin for the LED
led = Pin(2, Pin.OUT)  # Most ESP32 boards have an onboard LED on GPIO 2

# Set up the MQTT broker details
BROKER = "13.232.192.17"  # AWS Mosquitto broker endpoint
PORT = 1883  # Standard MQTT port
TOPIC = "esp32/data"  # Topic to publish to

# I2C setup for communication with MPU6050
scl_pin = machine.Pin(22)  # Set the SCL pin (clock line)
sda_pin = machine.Pin(21)  # Set the SDA pin (data line)
i2c = I2C(0, scl=scl_pin, sda=sda_pin, freq=400000)  # Initialize I2C with high frequency

# Asynchronous function to read firmware version from version.json
async def get_firmware_version():
    try:
        gc.collect()
        with open("version.json", "r") as f:
            print("Opened version.json successfully")  # Debugging line
            version_data = json.load(f)
            print("Loaded JSON data:", version_data)  # Debugging line
            return version_data.get("version", "unknown")
    except Exception as e:
        print(f"Failed to read version file: {e}")
        return "unknown"

# Function to connect to MQTT broker with error handling
async def connect_mqtt():
    client = MQTTClient("esp32_client", BROKER, port=PORT, keepalive=60)
    try:
        client.connect()
        print("Connected to MQTT broker")
        return client
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        return None

async def publish_data(client, data):
    try:
        # Check if the client or socket is disconnected
        if client is None:
            print("Client is disconnected. Attempting to reconnect...")
            client = await connect_mqtt()  # Attempt to reconnect
            if client is None:
                print("Failed to reconnect. Will retry on next cycle.")
                return client  # Return client if data was successfully published

        # Only attempt to publish if the client is connected
        client.publish(TOPIC, data)
        print(f"Published data: {data}")
        await asyncio.sleep(0) # Yield control to allow other tasks to run
        return client  # Return client if data was successfully published

    except Exception as e:
        print(f"Error publishing data: {e}")
        await asyncio.sleep(2)  # Short delay before trying agai
        return None  # Return the client for retry logic

###############

# Function to calculate RMS from a list of 100 readings
def calculate_rms_multiple(readings):
    squared_sum = sum([reading ** 2 for reading in readings])
    return (squared_sum / len(readings)) ** 0.5

# Function to read multiple accelerometer data (100 samples)
async def read_multiple_accel(i2c, num_samples=100):
    ax_readings = []
    ay_readings = []
    az_readings = []

    for _ in range(num_samples):
        ax, ay, az = await read_accel(i2c)
        if ax is not None and ay is not None and az is not None:
            ax_readings.append(ax)
            ay_readings.append(ay)
            az_readings.append(az)
        else:
            print("Error reading accelerometer data.")
        await asyncio.sleep(0)  # Yield control to allow other tasks to run

    # Calculate RMS for each axis from the collected readings
    rms_accel_x = calculate_rms_multiple(ax_readings)
    rms_accel_y = calculate_rms_multiple(ay_readings)
    rms_accel_z = calculate_rms_multiple(az_readings)

    return rms_accel_x, rms_accel_y, rms_accel_z

# Function to read accelerometer data from MPU6050
async def read_accel(i2c):
    try:
        ax = await read_i2c_word(i2c, 0x3B)
        ay = await read_i2c_word(i2c, 0x3D)
        az = await read_i2c_word(i2c, 0x3F)

        # If any reading fails, return 0.0 as default
        if ax is None or ay is None or az is None:
            print("Error: Failed to read accelerometer data, using default values (0.0).")
            return 0.0, 0.0, 0.0

        return ax, ay, az
    except Exception as e:
        print(f"Error reading accelerometer: {e}")
        return 0.0, 0.0, 0.0  # Default values in case of exception

# Function to read I2C word from MPU6050
async def read_i2c_word(i2c, register):
    try:
        data = i2c.readfrom_mem(0x68, register, 2)
        value = (data[0] << 8) | data[1]
        if value >= 0x8000:
            value -= 0x10000
        return value
    except Exception as e:
        print(f"Error reading I2C word: {e}")
        return None

# Function to handle sensor errors and attempt reinitialization
async def handle_sensor_error(i2c):
    print("Sensor error detected, reinitializing MPU6050...")
    retries = 0
    while retries < 5:
        if await initialize_mpu6050(i2c):
            print("MPU6050 reinitialized successfully")
            return True
        retries += 1
        print(f"Retrying... attempt {retries}")
        await asyncio.sleep(2)  # Non-blocking sleep between retries
    print("Failed to reinitialize MPU6050 after multiple attempts.")
    return False

# Function to initialize the MPU6050 sensor
async def initialize_mpu6050(i2c):
    try:
        i2c.writeto(0x68, bytearray([0x6B, 0]))  # Wake up the MPU6050
        print("MPU6050 initialized successfully")
        return True
    except Exception as e:
        print(f"MPU6050 Initialization Error: {e}")
        return False
    
##################

# Asynchronous function to read temperature
async def read_temperature():
    """Asynchronously read temperature from MAX31865 sensor."""
    # Simulate asynchronous I/O (no real delay needed here, just yielding control)
    await asyncio.sleep(0)  # Yield control to allow other tasks to run
    
    # Read temperature from the sensor
    temperature = [sensor.temperature for sensor in sensors]
    
    return float(temperature[0])  # Return temperature as a float

# Asynchronous task to publish temperature to MQTT
async def temperature_task():
    client = None
    firmware_version = await get_firmware_version()  # Get firmware version once

    while True:
        if client is None:
            print("Attempting to connect to MQTT broker...")
            client = await connect_mqtt()
            if client is None:
                print("Failed to connect to MQTT broker. Retrying in 5 seconds...")
                await asyncio.sleep(5)
                continue

        try:
            # 1. Read 100 accelerometer data points (ax, ay, az)
            rms_accel_x, rms_accel_y, rms_accel_z = await read_multiple_accel(i2c)

            # 2. Read temperature asynchronously
            temperature = await read_temperature()
            
            # 3. Prepare the data to be published (RMS values for each axis, temperature, version)
            data = f"AccX RMS: {rms_accel_x:.2f}, AccY RMS: {rms_accel_y:.2f}, AccZ RMS: {rms_accel_z:.2f}, Temp: {temperature:.2f}C, Firmware Version: {firmware_version}"

            # 4. Prepare the data to be published (RMS values for each axis, temperature, version)
            data = f"AccX RMS: {rms_accel_x:.2f}, AccY RMS: {rms_accel_y:.2f}, AccZ RMS: {rms_accel_z:.2f}, Temp: {temperature:.2f}C, Firmware Version: {firmware_version}"
            
            # Attempt to publish the data
            client = await publish_data(client, data)
            await asyncio.sleep(5)  # Adjust the sleep time as necessary

        except OSError as e:
            print(f"Error in temperature task/MQTT publishing: {e}")
            # Attempt to disconnect and reconnect
            if client:
                client.disconnect()  # Disconnect on error
            client = None  # Reset client to force reconnection
            await asyncio.sleep(5)
            
async def ota_task():
    while True:
        gc.collect()
        #from ota import OTAUpdater
        ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py", NODE_ID)
        # Await the async method download_and_install_update_if_available
        #await ota_updater.download_and_install_update_if_available()  # Await this async function
        # Check if an update is available
        if await ota_updater.check_for_updates():
            # If there's a new version, perform the update
            ota_updater.update_and_reset()
        else:
            print("No update available.")
            
        gc.collect()
        await asyncio.sleep(120)  # Allow the loop to yield control for a while

async def led_blink_task():
    while True:
        led.value(1)  # Turn on the LED
        await asyncio.sleep(1)  # Delay for 500ms
        led.value(0)  # Turn off the LED
        await asyncio.sleep(1)  # Delay for 500ms
        await asyncio.sleep(1)  # Additional delay before repeating the task

async def main():
    await asyncio.gather(ota_task(), led_blink_task(), temperature_task())  # Run both tasks concurrently

# Start the main event loop
asyncio.run(main())  # This will start the asynchronous loop
