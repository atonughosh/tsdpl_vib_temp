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
from machine import SPI, Pin
import time
import gc
from umqtt.simple import MQTTClient
import max31865

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

    while True:
        if client is None:
            print("Attempting to connect to MQTT broker...")
            client = await connect_mqtt()
            if client is None:
                print("Failed to connect to MQTT broker. Retrying in 5 seconds...")
                await asyncio.sleep(5)
                continue

        try:
            # Read temperature and format for MQTT
            temperature = await read_temperature()
            data = f"Temperature: {temperature:.2f} C"
            client = await publish_data(client, data)  # Update client if reconnection happens
            await asyncio.sleep(10)  # Delay between readings

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
