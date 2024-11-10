# main.py
import machine
machine.freq(240000000)
# This is version number 23
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
NODE_ID = "1"

gc.collect()
firmware_url = "https://github.com/atonughosh/tsdpl_vib_temp"

async def check_and_install_update():
    try:
        # Initialize OTAUpdater
        ota_updater = OTAUpdater(SSID, PASSWORD, firmware_url, "main.py", NODE_ID)
        # Await the update check and installation
        await ota_updater.download_and_install_update_if_available()
    except:
        print(f"Error during OTA update")


# Start the async update process
async def boot():
    gc.collect()
    await check_and_install_update()  # Await the update process

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
        # Await the async method download_and_install_update_if_available
        await ota_updater.download_and_install_update_if_available()  # Await this async function
        gc.collect()
        await asyncio.sleep(120)  # Allow the loop to yield control for a while

async def task2():
    while True:
        led.value(1)  # Turn on the LED
        await asyncio.sleep(1)  # Delay for 500ms
        led.value(0)  # Turn off the LED
        await asyncio.sleep(1)  # Delay for 500ms
        await asyncio.sleep(1)  # Additional delay before repeating the task

async def main():
    await asyncio.gather(task1(), task2())  # Run both tasks concurrently

# Start the main event loop
asyncio.run(main())  # This will start the asynchronous loop

