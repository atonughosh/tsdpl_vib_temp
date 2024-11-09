# main.py

# This is version number 11
# Do NOT update following lines
NODE_ID = 1
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
NODE_ID = "1"

gc.collect()
firmware_url = "https://github.com/atonughosh/tsdpl_vib_temp"

ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py", NODE_ID)

ota_updater.download_and_install_update_if_available()
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

import uasyncio as asyncio
from machine import Pin
import time
import gc

# Set up pin for the LED
led = Pin(2, Pin.OUT)  # Most ESP32 boards have an onboard LED on GPIO 2

async def task1():
    while True:
        gc.collect()
        from ota import OTAUpdater
        ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py", NODE_ID)
        ota_updater.download_and_install_update_if_available()
        gc.collect()
        await asyncio.sleep(0.5)

async def task2():
    while True:
        led.value(1)  # Turn on the LED
        time.sleep(0.5)  # Delay for 500ms
        led.value(0)  # Turn off the LED
        time.sleep(0.5)  # Delay for 500ms
        await asyncio.sleep(0.5)

async def main():
    await asyncio.gather(task1(), task2())

# Start the main event loop
asyncio.run(main())

