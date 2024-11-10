# main.py
import machine
machine.freq(240000000)
# This is version number 3
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
from machine import Pin
import time
import gc
from umqtt.simple import MQTTClient


# Set up the MQTT broker details
BROKER = "13.232.192.17"  # AWS Mosquitto broker endpoint
PORT = 1883  # Standard MQTT port
TOPIC = "esp32/data"  # Topic to publish to

# Set up pin for the LED
led = Pin(2, Pin.OUT)  # Most ESP32 boards have an onboard LED on GPIO 2

# Function to connect to MQTT broker
def connect_mqtt():
    client = MQTTClient("esp32_client", BROKER, port=PORT)
    client.connect()
    print("Connected to MQTT broker")
    return client

# Function to connect to MQTT broker with error handling
def connect_mqtt():
    client = MQTTClient("esp32_client", BROKER, port=PORT)
    try:
        client.connect()
        print("Connected to MQTT broker")
        return client
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        return None

# Function to publish data to MQTT broker
def publish_data(client, data):
    try:
        client.publish(TOPIC, data)
        print(f"Published data: {data}")
    except Exception as e:
        print(f"Error publishing data: {e}")


async def mqtt_publish_task():
    client = None
    while True:
        # Attempt to connect to MQTT broker
        while client is None:
            print("Attempting to connect to MQTT broker...")
            client = connect_mqtt()
            if client is None:
                print("Failed to connect. Retrying in 5 seconds...")
                await asyncio.sleep(5)  # Retry connection after 5 seconds
        
        # Once connected, publish data
        try:
            # Publish dummy data (replace this with actual sensor data)
            publish_data(client, "Hello from ESP32")
            await asyncio.sleep(5)  # Publish data every 2 minutes
        except Exception as e:
            print(f"Error in MQTT publishing: {e}")
            client.disconnect()  # Disconnect if error occurs
            client = None  # Reset client to None so it reconnects
            await asyncio.sleep(5)  # Retry connection after 5 seconds

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
    await asyncio.gather(mqtt_publish_task(), ota_task(), led_blink_task())  # Run both tasks concurrently

# Start the main event loop
asyncio.run(main())  # This will start the asynchronous loop
